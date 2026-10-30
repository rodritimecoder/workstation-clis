#!/usr/bin/env bash
# Speculative decoding benchmark for Qwen3.6-35B-A3B.
# Compares no speculation, DFlash2, 15 n-gram configurations, and n-gram+DFlash hybrids.
# Target and draft stay fully offloaded to the two Vulkan GPUs.
#
# Notes:
#   - Baseline uses llama-completion, so "prefill" is its prompt eval time.
#   - Speculative runs use llama-speculative-simple, so "prefill" is the
#     "encoded N tokens" line. Its "prompt eval" counter also includes
#     verification batches and is not a pure prefill measurement.
#   - Generate throughput includes the extra token(s) produced by a
#     speculative block, so the generated-token count is logged too.
#   - These are short prompts, so prefill is startup-bound. For steady-state
#     prefill use llama-bench with a combined device pair, e.g.
#     -p 2048 -b 2048 -ub 512 -dev Vulkan0/Vulkan1 -ts 0.5/0.5
#
# Examples:
#   ./bench-qwen36-dflash2-ngram.sh --quick
#   ./bench-qwen36-dflash2-ngram.sh --quick --runs 3
#   ./bench-qwen36-dflash2-ngram.sh --full --workload repeat --runs 3
#   ./bench-qwen36-dflash2-ngram.sh --full --out /run/media/rodri/AI/bench/my-run

set -euo pipefail

DRIVE="${DRIVE:-/run/media/rodri/AI}"
LLAMA_BIN_DIR="${LLAMA_BIN_DIR:-$DRIVE/llama.cpp/build/bin}"
SPEC_BIN="$LLAMA_BIN_DIR/llama-speculative-simple"
BASE_BIN="$LLAMA_BIN_DIR/llama-completion"

DEFAULT_TARGET="$DRIVE/models/unsloth/Qwen3.6-35B-A3B-MTP-GGUF/Qwen3.6-35B-A3B-UD-Q3_K_M.gguf"
DEFAULT_DRAFT="$DRIVE/models/aminya/Qwen3.6-35B-A3B-DFlash2-GGUF/Qwen3.6-35B-A3B-DFlash2-Q4_K_M.gguf"
TARGET="${TARGET_MODEL:-$DEFAULT_TARGET}"
DRAFT="${DRAFT_MODEL:-$DEFAULT_DRAFT}"

CTX="${CTX:-4096}"
BATCH="${BATCH:-2048}"
UBATCH="${UBATCH:-512}"
NGL="${NGL:-all}"
DEVICES="${DEVICES:-Vulkan0,Vulkan1}"
SPLIT_MODE="${SPLIT_MODE:-layer}"
TENSOR_SPLIT="${TENSOR_SPLIT:-0.5,0.5}"
DRAFT_DEVICE="${DRAFT_DEVICE:-Vulkan1}"
DRAFT_N_MAX="${DRAFT_N_MAX:-7}"
SEED="${SEED:-42}"

MATRIX=full
WORKLOAD=both
RUNS=1
FORCE=0
OUT=""

usage() {
    sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
    cat <<'EOF'

Options:
  --quick              baseline, DFlash, best n-gram, best hybrid (4 configs)
  --full               all 20 configurations (default)
  --workload NAME      code | repeat | both (default: both)
  --runs N             repetitions per configuration/workload (default: 1)
  --ctx N              context size (default: 4096)
  --batch N            logical batch size (default: 2048)
  --ubatch N           micro-batch size (default: 512)
  --out DIR            output directory (default: AI/bench/qwen36-spec-TIMESTAMP)
  --target FILE        target GGUF (default: Unsloth Qwen3.6-35B-A3B UD-Q3_K_M)
  --draft FILE         DFlash2 draft GGUF (default: aminya Q4_K_M)
  --force              run even if another GPU process is active
  -h, --help           show this help
EOF
}

while (($#)); do
    case "$1" in
        --quick) MATRIX=quick ;;
        --full) MATRIX=full ;;
        --workload) WORKLOAD="${2:?missing workload}"; shift ;;
        --runs) RUNS="${2:?missing run count}"; shift ;;
        --ctx) CTX="${2:?missing context size}"; shift ;;
        --batch) BATCH="${2:?missing batch size}"; shift ;;
        --ubatch) UBATCH="${2:?missing micro-batch size}"; shift ;;
        --out) OUT="${2:?missing output directory}"; shift ;;
        --target) TARGET="${2:?missing target model}"; shift ;;
        --draft) DRAFT="${2:?missing draft model}"; shift ;;
        --force) FORCE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [[ "$WORKLOAD" != code && "$WORKLOAD" != repeat && "$WORKLOAD" != both ]]; then
    echo "--workload must be code, repeat, or both" >&2
    exit 2
fi
if ! [[ "$RUNS" =~ ^[1-9][0-9]*$ ]]; then
    echo "--runs must be a positive integer" >&2
    exit 2
fi
for pair in "CTX:$CTX" "BATCH:$BATCH" "UBATCH:$UBATCH"; do
    name="${pair%%:*}"
    value="${pair#*:}"
    if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
        echo "$name must be a positive integer" >&2
        exit 2
    fi
done
if ((UBATCH > BATCH)); then
    echo "UBATCH ($UBATCH) cannot exceed BATCH ($BATCH)" >&2
    exit 2
fi
if ! [[ "$DRAFT_N_MAX" =~ ^[1-9][0-9]*$ ]]; then
    echo "DRAFT_N_MAX must be a positive integer" >&2
    exit 2
fi

for f in "$SPEC_BIN" "$BASE_BIN" "$TARGET" "$DRAFT"; do
    if [[ ! -f "$f" ]]; then
        echo "missing: $f" >&2
        exit 1
    fi
done
spec_help="$("$SPEC_BIN" --help 2>&1 || true)"
grep -q -- '--spec-type' <<< "$spec_help" || {
    echo "$SPEC_BIN does not support --spec-type" >&2
    exit 1
}
grep -q 'draft-dflash' <<< "$spec_help" || {
    echo "$SPEC_BIN does not support draft-dflash" >&2
    exit 1
}

if command -v rocm-smi >/dev/null 2>&1; then
    busy="$(rocm-smi --showpids 2>/dev/null | grep -E '^[[:space:]]*[0-9]+[[:space:]]' || true)"
    if [[ -n "$busy" ]]; then
        echo "GPU processes are active; benchmark results would be polluted:" >&2
        echo "$busy" >&2
        if ((FORCE == 0)); then
            echo "Stop them, or pass --force to run anyway." >&2
            exit 1
        fi
        echo "--force: continuing with active GPU processes" >&2
    fi
fi

if [[ -z "$OUT" ]]; then
    OUT="$DRIVE/bench/qwen36-spec-$(date +%Y%m%d-%H%M%S)"
fi
if [[ -e "$OUT" ]]; then
    echo "output directory already exists: $OUT" >&2
    exit 1
fi
mkdir -p "$OUT/logs" "$OUT/prompts"

cat > "$OUT/prompts/code.txt" <<'EOF'
You are completing a Python utility module. Continue in Python only.

from __future__ import annotations

from collections.abc import Sequence


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def normalize(values: Sequence[float]) -> list[float]:
    total = sum(values)
    if total == 0.0:
        return [0.0 for _ in values]
    return [value / total for value in values]


def moving_average(values: Sequence[float], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    return [sum(values[max(0, i - window + 1):i + 1]) / min(i + 1, window)
            for i in range(len(values))]


Add a stable softmax(values: Sequence[float]) -> list[float] and three pytest tests. Handle empty input and extreme values. Include type annotations and no prose.
EOF

cat > "$OUT/prompts/repeat.txt" <<'EOF'
Complete only the indicated function in this Python file. Use the same schema-building statements and key order as the examples. Do not add comments or prose.

def parse_user(record: dict) -> dict:
    output = {}
    output["id"] = str(record["id"])
    output["name"] = str(record["name"])
    output["active"] = bool(record.get("active", True))
    return output

def parse_project(record: dict) -> dict:
    output = {}
    output["id"] = str(record["id"])
    output["name"] = str(record["name"])
    output["active"] = bool(record.get("active", True))
    return output

def parse_team(record: dict) -> dict:
    output = {}
    output["id"] = str(record["id"])
    output["name"] = str(record["name"])
    output["active"] = bool(record.get("active", True))
    return output

def parse_invoice(record: dict) -> dict:
    output = {}
EOF

ALL_CONFIGS=(
    baseline
    dflash_n7
    ngram_mod_match12
    ngram_mod_match24
    ngram_mod_match32
    ngram_simple_n4
    ngram_simple_n8
    ngram_simple_n12
    ngram_simple_n16
    ngram_mapk_n4
    ngram_mapk_n8
    ngram_mapk_n12
    ngram_mapk_n16
    ngram_mapk4v_n4
    ngram_mapk4v_n8
    ngram_mapk4v_n12
    ngram_mapk4v_n16
    hybrid_simple_n4
    hybrid_mapk_n4
    hybrid_mapk4v_n4
)
QUICK_CONFIGS=(baseline dflash_n7 ngram_mapk_n4 hybrid_mapk_n4)

if [[ "$MATRIX" == quick ]]; then
    CONFIGS=("${QUICK_CONFIGS[@]}")
else
    CONFIGS=("${ALL_CONFIGS[@]}")
fi

config_setup() {
    local name="$1"
    CFG_EXE="$SPEC_BIN"
    CFG_TYPE=""
    CFG_EXTRA=()

    case "$name" in
        baseline)
            CFG_EXE="$BASE_BIN"
            ;;
        dflash_n7)
            CFG_TYPE="draft-dflash"
            CFG_EXTRA=(-md "$DRAFT" --spec-draft-n-max "$DRAFT_N_MAX" --spec-draft-ngl all --spec-draft-device "$DRAFT_DEVICE")
            ;;
        ngram_mod_match12|ngram_mod_match24|ngram_mod_match32)
            local match="${name##*match}"
            CFG_TYPE="ngram-mod"
            CFG_EXTRA=(--spec-ngram-mod-n-match "$match" --spec-ngram-mod-n-min 1 --spec-ngram-mod-n-max "$DRAFT_N_MAX" --spec-draft-n-max "$DRAFT_N_MAX")
            ;;
        ngram_simple_n4|ngram_simple_n8|ngram_simple_n12|ngram_simple_n16)
            local n="${name##*_n}"
            CFG_TYPE="ngram-simple"
            CFG_EXTRA=(--spec-ngram-simple-size-n "$n" --spec-ngram-simple-size-m "$DRAFT_N_MAX" --spec-ngram-simple-min-hits 1 --spec-draft-n-max "$DRAFT_N_MAX")
            ;;
        ngram_mapk_n4|ngram_mapk_n8|ngram_mapk_n12|ngram_mapk_n16)
            local n="${name##*_n}"
            CFG_TYPE="ngram-map-k"
            CFG_EXTRA=(--spec-ngram-map-k-size-n "$n" --spec-ngram-map-k-size-m "$DRAFT_N_MAX" --spec-ngram-map-k-min-hits 2 --spec-draft-n-max "$DRAFT_N_MAX")
            ;;
        ngram_mapk4v_n4|ngram_mapk4v_n8|ngram_mapk4v_n12|ngram_mapk4v_n16)
            local n="${name##*_n}"
            CFG_TYPE="ngram-map-k4v"
            CFG_EXTRA=(--spec-ngram-map-k4v-size-n "$n" --spec-ngram-map-k4v-size-m "$DRAFT_N_MAX" --spec-ngram-map-k4v-min-hits 2 --spec-draft-n-max "$DRAFT_N_MAX")
            ;;
        hybrid_simple_n4)
            CFG_TYPE="ngram-simple,draft-dflash"
            CFG_EXTRA=(-md "$DRAFT" --spec-draft-n-max "$DRAFT_N_MAX" --spec-draft-ngl all --spec-draft-device "$DRAFT_DEVICE" --spec-ngram-simple-size-n 4 --spec-ngram-simple-size-m "$DRAFT_N_MAX" --spec-ngram-simple-min-hits 1)
            ;;
        hybrid_mapk_n4)
            CFG_TYPE="ngram-map-k,draft-dflash"
            CFG_EXTRA=(-md "$DRAFT" --spec-draft-n-max "$DRAFT_N_MAX" --spec-draft-ngl all --spec-draft-device "$DRAFT_DEVICE" --spec-ngram-map-k-size-n 4 --spec-ngram-map-k-size-m "$DRAFT_N_MAX" --spec-ngram-map-k-min-hits 2)
            ;;
        hybrid_mapk4v_n4)
            CFG_TYPE="ngram-map-k4v,draft-dflash"
            CFG_EXTRA=(-md "$DRAFT" --spec-draft-n-max "$DRAFT_N_MAX" --spec-draft-ngl all --spec-draft-device "$DRAFT_DEVICE" --spec-ngram-map-k4v-size-n 4 --spec-ngram-map-k4v-size-m "$DRAFT_N_MAX" --spec-ngram-map-k4v-min-hits 2)
            ;;
        *)
            echo "unknown config: $name" >&2
            exit 2
            ;;
    esac
}

CSV="$OUT/results.csv"
printf 'workload,config,run,status,prefill_tokens,prefill_seconds,prefill_tps,generated_tokens,decode_seconds,generate_tps,drafted_tokens,accepted_tokens,accept_pct,mean_accept_len,all_layers_gpu,log\n' > "$CSV"

sum_gen_drafts() {
    grep -oP '#gen drafts\s*=\s*\K[0-9]+' "$1" | awk '{s+=$1} END {print s+0}'
}
sum_draft_tokens() {
    grep -oP '#gen tokens\s*=\s*\K[0-9]+' "$1" | awk '{s+=$1} END {print s+0}'
}
sum_accepted() {
    grep -oP '#acc tokens\s*=\s*\K[0-9]+' "$1" | awk '{s+=$1} END {print s+0}'
}

run_one() {
    local workload="$1" config="$2" run="$3"
    local prompt npredict
    if [[ "$workload" == code ]]; then
        prompt="$OUT/prompts/code.txt"
        npredict=256
    else
        prompt="$OUT/prompts/repeat.txt"
        npredict=128
    fi

    config_setup "$config"
    local log="$OUT/logs/${workload}_${config}_run${run}.log"
    local cmd
    if [[ "$config" == baseline ]]; then
        cmd=("$CFG_EXE" -m "$TARGET" -f "$prompt" -n "$npredict" -c "$CTX" -b "$BATCH" -ub "$UBATCH" --temp 0 --top-k 1 --seed "$SEED" -ngl "$NGL" --device "$DEVICES" --split-mode "$SPLIT_MODE" --tensor-split "$TENSOR_SPLIT" --fit off -fa on -lv 4 -no-cnv --no-display-prompt --simple-io)
    else
        cmd=("$CFG_EXE" -m "$TARGET" -f "$prompt" -n "$npredict" -c "$CTX" -b "$BATCH" -ub "$UBATCH" --temp 0 --top-k 1 --seed "$SEED" -ngl "$NGL" --device "$DEVICES" --split-mode "$SPLIT_MODE" --tensor-split "$TENSOR_SPLIT" --fit off -fa on -lv 4 --spec-type "$CFG_TYPE" "${CFG_EXTRA[@]}")
    fi

    printf '%s\n' "=== $workload / $config / run $run ===" >> "$OUT/commands.log"
    printf '%q ' "${cmd[@]}" >> "$OUT/commands.log"
    printf '\n' >> "$OUT/commands.log"

    echo "[$workload] $config (run $run/$RUNS)" >&2
    local started ended status=0
    started="$(date +%s)"
    set +e
    "${cmd[@]}" > "$log" 2>&1
    status=$?
    set -e
    ended="$(date +%s)"

    local prefill_tokens="" prefill_seconds="" prefill_tps=""
    local generated="" decode_seconds="" generate_tps=""
    local drafted="" accepted="" accept_pct="" mean_acc="" gen_drafts=""
    local all_layers="no" target_layers draft_layers

    target_layers="$(grep -oP 'offloaded \K[0-9]+/[0-9]+(?= layers to GPU)' "$log" | head -n1 || true)"
    draft_layers="$(grep -oP 'offloaded \K[0-9]+/[0-9]+(?= layers to GPU)' "$log" | sed -n '2p' || true)"
    if [[ -n "$target_layers" ]]; then
        all_layers="yes"
        IFS=/ read -r a b <<< "$target_layers"
        [[ "$a" == "$b" ]] || all_layers="no"
    fi
    if [[ -n "$draft_layers" ]]; then
        IFS=/ read -r a b <<< "$draft_layers"
        [[ "$a" == "$b" ]] || all_layers="no"
    fi

    if [[ "$config" == baseline ]]; then
        prefill_tokens="$(grep -oP 'prompt eval time =.*/\s*\K[0-9]+(?= tokens)' "$log" | tail -n1 || true)"
        prefill_tps="$(grep -oP 'prompt eval time =.*,\s*\K[0-9.]+(?= tokens per second)' "$log" | tail -n1 || true)"
        generated="$(grep -oP 'eval time =.*/\s*\K[0-9]+(?= runs)' "$log" | tail -n1 || true)"
        generate_tps="$(grep -oP 'eval time =.*,\s*\K[0-9.]+(?= tokens per second)' "$log" | tail -n1 || true)"
        if [[ -n "$prefill_tokens" && -n "$prefill_tps" && "$prefill_tps" != 0 ]]; then
            prefill_seconds="$(awk -v n="$prefill_tokens" -v t="$prefill_tps" 'BEGIN { printf "%.4f", n / t }')"
        fi
        if [[ -n "$generated" && -n "$generate_tps" && "$generate_tps" != 0 ]]; then
            decode_seconds="$(awk -v n="$generated" -v t="$generate_tps" 'BEGIN { printf "%.4f", n / t }')"
        fi
    else
        prefill_tokens="$(grep -oP 'encoded\s+\K[0-9]+(?= tokens)' "$log" | tail -n1 || true)"
        prefill_seconds="$(grep -oP 'encoded\s+[0-9]+ tokens in\s+\K[0-9.]+(?= seconds)' "$log" | tail -n1 || true)"
        prefill_tps="$(grep -oP 'encoded\s+[0-9]+ tokens in\s+[0-9.]+ seconds, speed:\s*\K[0-9.]+' "$log" | tail -n1 || true)"
        generated="$(grep -oP 'decoded\s+\K[0-9]+(?= tokens)' "$log" | tail -n1 || true)"
        decode_seconds="$(grep -oP 'decoded\s+[0-9]+ tokens in\s+\K[0-9.]+(?= seconds)' "$log" | tail -n1 || true)"
        generate_tps="$(grep -oP 'decoded\s+[0-9]+ tokens in\s+[0-9.]+ seconds, speed:\s*\K[0-9.]+' "$log" | tail -n1 || true)"
        drafted="$(sum_draft_tokens "$log")"
        accepted="$(sum_accepted "$log")"
        gen_drafts="$(sum_gen_drafts "$log")"
        if [[ -n "$drafted" && "$drafted" != 0 ]]; then
            accept_pct="$(awk -v a="$accepted" -v d="$drafted" 'BEGIN { printf "%.2f", 100.0 * a / d }')"
        fi
        if [[ -n "$gen_drafts" && "$gen_drafts" != 0 ]]; then
            mean_acc="$(awk -v a="$accepted" -v d="$gen_drafts" 'BEGIN { printf "%.2f", 1.0 + a / d }')"
        fi
    fi

    local wall="$((ended - started))"
    echo "    status=$status wall=${wall}s prefill=${prefill_tps:-?} t/s generate=${generate_tps:-?} t/s layers=${target_layers:-?}${draft_layers:+, draft $draft_layers}" >&2
    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
        "$workload" "$config" "$run" "$status" "$prefill_tokens" "$prefill_seconds" "$prefill_tps" \
        "$generated" "$decode_seconds" "$generate_tps" "$drafted" "$accepted" "$accept_pct" \
        "$mean_acc" "$all_layers" "$log" >> "$CSV"
}

echo "ROCmFPX Qwen3.6 speculative benchmark"
echo "  matrix:   $MATRIX (${#CONFIGS[@]} configs)"
echo "  workload: $WORKLOAD"
echo "  runs:     $RUNS"
echo "  target:   $TARGET"
echo "  draft:    $DRAFT (max $DRAFT_N_MAX)"
echo "  ctx/batch: $CTX / $BATCH (ubatch $UBATCH)"
echo "  devices:  $DEVICES, split=$SPLIT_MODE $TENSOR_SPLIT, draft=$DRAFT_DEVICE"
echo "  output:   $OUT"
echo

for wl in code repeat; do
    [[ "$WORKLOAD" == both || "$WORKLOAD" == "$wl" ]] || continue
    for ((r = 1; r <= RUNS; r++)); do
        for cfg in "${CONFIGS[@]}"; do
            run_one "$wl" "$cfg" "$r"
        done
    done
done

if command -v rocm-smi >/dev/null 2>&1; then
    busy="$(rocm-smi --showpids 2>/dev/null | grep -E '^[[:space:]]*[0-9]+[[:space:]]' || true)"
    if [[ -n "$busy" ]]; then
        echo "warning: GPU processes still active after benchmark:" >&2
        echo "$busy" >&2
    fi
fi

echo
echo "Per-config mean (prefill t/s, generate t/s, accept %):"
printf "%-8s %-24s %5s %10s %10s %8s %s\n" "workload" "config" "runs" "prefill" "generate" "accept" "gpu"
awk -F, 'NR > 1 {
    key = $1 "|" $2
    n[key]++
    prefill[key] += $7
    generate[key] += $10
    if ($13 != "") {
        accn[key]++
        accept[key] += $13
    }
    if ($15 != "yes") bad[key] = 1
}
END {
    for (key in n) {
        split(key, p, "|")
        gpu = (key in bad) ? "PARTIAL" : "all"
        acc = (key in accn) ? sprintf("%.1f%%", accept[key] / accn[key]) : "-"
        printf "%-8s %-24s %5d %10.2f %10.2f %8s %s\n", p[1], p[2], n[key], prefill[key]/n[key], generate[key]/n[key], acc, gpu
    }
}' "$CSV" | sort -t' ' -k1,1 -k2,2

echo
echo "CSV:  $CSV"
echo "Logs: $OUT/logs"
echo "Commands: $OUT/commands.log"
