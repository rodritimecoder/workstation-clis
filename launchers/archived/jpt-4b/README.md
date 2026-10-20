# JPT-4B typed decisions — stock llama.cpp

[JPT-4B](https://huggingface.co/kirp/jpt-4b) (weights from
[prithivMLmods/jpt-4b-GGUF](https://huggingface.co/prithivMLmods/jpt-4b-GGUF)) served as a **classifier**:
a state plus typed questions in, calibrated probabilities per option out. No generation, no chat.

Same interface as the local Jev decision app (`~/Desktop/jev-score`), different model — and unlike the
Jev app this one needs no patched C++ scorer: it runs on an unmodified `llama-server`.

| | |
|---|---|
| model | `jpt-4b.Q4_K_M.gguf` (2.7 GB) + `jpt-4b.mmproj-bf16.gguf` |
| engine | `/home/rodri/Desktop/llama-official/build/bin/llama-server`, Vulkan, `-ngl 99` |
| engine port | `8090` (internal; holds the weights) |
| API port | `8080` → `POST /v1/systemone` (System One wire format, llm2jev-compatible) |
| desktop icon | `~/Desktop/jpt-4b-decision.desktop` |

## Run it

Double-click the desktop icon, or:

```bash
~/Desktop/jpt-4b/start-jpt.sh
```

Starts the engine if it is not already up, starts the JSON API, and opens the REPL. Close the window
(or `:quit`) to stop what it started.

## REPL (same line format as the Jev app)

```
state | question | options
```

```text
jpt> Customer was charged twice and wants a refund for the duplicate. | Which team should handle this? | {"billing":"invoices and refunds","tech":"software bugs","sales":"pricing"}

  answer    : billing   confidence 0.798
    billing                   0.951  #############################
    tech                      0.037  #
    sales                     0.012
  172 ms
```

- options is a JSON **object** → `choice`; a JSON **array** → `score`; empty/`none` → `noul` (P(true))
- `@file.txt` as the state reads that file
- commands: `:info` `:api` `:gpu` `:quit`

## JSON API (the classifier endpoint)

```bash
curl -s localhost:8080/v1/systemone -H 'Content-Type: application/json' -d '{
  "state": "Refund policy: full refund within 30 days; 50% until day 60; none after.\nOrder 1182 bought 3 March, returned 20 April.",
  "questions": {
    "refund":  {"type": "choice", "instructions": "What refund does order 1182 get?",
                "criteria": {"full": "Full refund", "half": "50% refund", "none": "No refund"}},
    "late":    {"type": "noul",   "instructions": "Was the return made after day 30?"},
    "severity":{"type": "score",  "instructions": "How severe is this case?",
                "criteria": ["trivial", "minor", "major", "severe"]}}}'
```

```json
{"answers": {
   "refund":  {"type":"choice","choice":"half","probabilities":{"full":0.156,"half":0.686,"none":0.159},"confidence":0.23},
   "late":    {"type":"noul","noul":0.909, "probabilities":{"true":0.909,"false":0.091}},
   "severity":{"type":"score","score":1.14,"probabilities":{"0":0.283,"1":0.399,"2":0.218,"3":0.100},
               "legend":{"0":"trivial","1":"minor","2":"major","3":"severe"}}},
 "meta": {"temperature": 1.036, "prefix_tokens": 57, "questions": 3}}
```

`GET /health` reports the engine it is bound to. Wrapper: `./jpt "state" "question" '[options]'`.

## How it scores (why no chat)

The model card's recipe: render the question into the model's own chat template with all options in
one prompt, pre-fill the assistant turn with `Answer:`, then read the logprob of each option label
token at that one position and softmax over the labels. One forward pass per question, however many
options (up to 255), regardless of how many options there are.

The prompt is byte-compatible with [llm2jev](https://github.com/tic-top/llm2jev)'s `chat` style,
because JPT-4B was trained on exactly that (`INSTRUCTION`, `A. 0: text` option lines, thinking off,
labels `A`-`Z` then `AA`…). Temperature is the card's fitted `T = 1.036`; pass `"temperature"` in the
request body to override.

Implementation notes (`jpt_llamacpp.py`), all through stock llama-server HTTP endpoints:

- `/apply-template` for the chat template (thinking off), with a marker split so **every question of a
  request shares a byte-identical prefix** — llama-server's prompt cache then prefills the state once.
- `/tokenize` + `/detokenize` to verify each label is **one token** right after the prompt ending
  (whether the model writes `A` or ` A` there is decided by the tokenizer, not guessed).
- `/completion` with `n_probs` for the full-vocab logprobs of that position. `missing_labels` in the
  answer says if a label fell outside the top-N (raise `logprobs_slack` in that case).

Text states only — the model is multimodal and the mmproj is loaded, but nothing here renders images.

## Tests

```bash
cd ~/Desktop/jpt-4b
python3 test_jpt.py                                   # needs the engine on :8090
python3 test_jpt.py --api http://127.0.0.1:8080        # also the HTTP facade
```

38 checks: prompt shape, one-token labels, logprob readout, answer/probability shape, determinism,
prefix sharing (6 questions over one state in 0.9 s), and a 10-item Banking77-style intent
classification run — **9/10 top-1** (the miss is a cash-withdrawal item that is genuinely ambiguous
between `cash_withdrawal` and `cash_withdrawal_not_recognised`). Measured ~115–215 ms per decision.

## Knobs

```bash
JPT_PORT=8099 ./start-jpt.sh        # move the System One API
JPT_ENGINE_PORT=8091 ./start-jpt.sh # move the engine
JPT_GGUF=.../jpt-4b.Q5_K_M.gguf ./start-jpt.sh
JPT_NGL=0 ./start-jpt.sh            # CPU only
JPT_CTX=32768 ./start-jpt.sh        # context (default 16384)
```

The engine log is `/tmp/jpt-4b-server-8090.log`.

## Credits

Weights: [kirp/jpt-4b](https://huggingface.co/kirp/jpt-4b) (CC BY-NC 4.0, Qwen3.5-4B base),
GGUF by [prithivMLmods](https://huggingface.co/prithivMLmods/jpt-4b-GGUF). Prompt format and the
System One wire format follow [llm2jev](https://github.com/tic-top/llm2jev) / TypeSafe AI's
[Jev](https://typesafe.ai) API. Served by [llama.cpp](https://github.com/ggml-org/llama.cpp).