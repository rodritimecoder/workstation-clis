#!/usr/bin/env bash
# sync_skills.sh — Synchronize and install workstation-clis
# Works standalone for any cloned instance of workstation-clis.
# Installs into ~/.gemini/config/skills and ~/.pi/agent/skills, and links ~/.local/bin launchers.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEMINI_HARNESS="$HOME/.gemini/config/skills"
PI_HARNESS="$HOME/.pi/agent/skills"
BIN_DIR="$HOME/.local/bin"

EXCLUDES=(
    --exclude "__pycache__"
    --exclude "*.pyc"
    --exclude ".venv"
    --exclude "node_modules"
    --exclude ".git"
    --exclude "README.md"
    --exclude "docs"
    --exclude ".env"
    --exclude ".env*"
    --exclude ".DS_Store"
    --exclude "Thumbs.db"
)

DO_PUSH=false
DO_PULL=false

for arg in "$@"; do
    case "$arg" in
        --push|-p)
            DO_PUSH=true
            ;;
        --pull|-u)
            DO_PULL=true
            ;;
        --status|-s)
            echo "📊 [workstation-sync] Repository Status:"
            git -C "$SCRIPT_DIR" status --short
            exit 0
            ;;
    esac
done

if [ "$DO_PULL" = true ]; then
    echo "📥 [workstation-sync] Pulling latest updates from GitHub..."
    git -C "$SCRIPT_DIR" pull origin main
fi

echo "⚙️ [workstation-sync] Installing Workstation Skills from $SCRIPT_DIR..."

mkdir -p "$GEMINI_HARNESS" "$PI_HARNESS" "$BIN_DIR"

# Discover all skills in this repo (directories with SKILL.md)
for skill_dir in "$SCRIPT_DIR"/*/; do
    if [ -f "$skill_dir/SKILL.md" ]; then
        skill_name="$(basename "$skill_dir")"
        echo "  📦 Syncing skill: $skill_name"
        
        # Sync to Gemini / Antigravity harness
        mkdir -p "$GEMINI_HARNESS/$skill_name"
        rsync -avu "${EXCLUDES[@]}" "$skill_dir" "$GEMINI_HARNESS/$skill_name/" >/dev/null 2>&1
        
        # Sync to Pi harness
        mkdir -p "$PI_HARNESS/$skill_name"
        rsync -avu "${EXCLUDES[@]}" "$skill_dir" "$PI_HARNESS/$skill_name/" >/dev/null 2>&1
    fi
done

# Setup Launchers in ~/.local/bin
echo "🔗 [workstation-sync] Configuring CLI launchers in $BIN_DIR..."

# local-hub & review-hub
[ -f "$SCRIPT_DIR/local-hub/local_hub.py" ] && ln -sf "$SCRIPT_DIR/local-hub/local_hub.py" "$BIN_DIR/local-hub" && chmod +x "$SCRIPT_DIR/local-hub/local_hub.py"
[ -f "$SCRIPT_DIR/local-hub/local_hub.py" ] && ln -sf "$SCRIPT_DIR/local-hub/local_hub.py" "$BIN_DIR/skills-hub"
[ -f "$SCRIPT_DIR/local-hub/local_hub.py" ] && ln -sf "$SCRIPT_DIR/local-hub/local_hub.py" "$BIN_DIR/uber"
[ -f "$SCRIPT_DIR/review-hub/review_hub.py" ] && ln -sf "$SCRIPT_DIR/review-hub/review_hub.py" "$BIN_DIR/review-hub" && chmod +x "$SCRIPT_DIR/review-hub/review_hub.py"

# state-compactor & cgate
[ -f "$SCRIPT_DIR/state-compactor/scripts/cgate.py" ] && ln -sf "$SCRIPT_DIR/state-compactor/scripts/cgate.py" "$BIN_DIR/cgate" && chmod +x "$SCRIPT_DIR/state-compactor/scripts/cgate.py"
[ -f "$SCRIPT_DIR/state-compactor/scripts/compactor.py" ] && ln -sf "$SCRIPT_DIR/state-compactor/scripts/compactor.py" "$BIN_DIR/state-compactor" && chmod +x "$SCRIPT_DIR/state-compactor/scripts/compactor.py"

# agentic-engineering
[ -f "$SCRIPT_DIR/agentic-engineering/agentic.py" ] && ln -sf "$SCRIPT_DIR/agentic-engineering/agentic.py" "$BIN_DIR/agentic" && chmod +x "$SCRIPT_DIR/agentic-engineering/agentic.py"

# github-architect & git-sync
[ -f "$SCRIPT_DIR/github-architect/scripts/github_architect.py" ] && ln -sf "$SCRIPT_DIR/github-architect/scripts/github_architect.py" "$BIN_DIR/github-architect" && chmod +x "$SCRIPT_DIR/github-architect/scripts/github_architect.py"
[ -f "$SCRIPT_DIR/github-architect/scripts/git_sync.py" ] && ln -sf "$SCRIPT_DIR/github-architect/scripts/git_sync.py" "$BIN_DIR/git-sync" && chmod +x "$SCRIPT_DIR/github-architect/scripts/git_sync.py"

# free frontier & nvidia nim
[ -f "$SCRIPT_DIR/openrouter-free/scripts/or_agent.py" ] && ln -sf "$SCRIPT_DIR/openrouter-free/scripts/or_agent.py" "$BIN_DIR/openrouter-free" && chmod +x "$SCRIPT_DIR/openrouter-free/scripts/or_agent.py"
[ -f "$SCRIPT_DIR/nvidia-nim/scripts/nim_client.py" ] && ln -sf "$SCRIPT_DIR/nvidia-nim/scripts/nim_client.py" "$BIN_DIR/nvidia-nim" && chmod +x "$SCRIPT_DIR/nvidia-nim/scripts/nim_client.py"
[ -f "$SCRIPT_DIR/nvidia-nim/scripts/nim_client.py" ] && ln -sf "$SCRIPT_DIR/nvidia-nim/scripts/nim_client.py" "$BIN_DIR/nim"

# guard hooks & test lane
[ -f "$SCRIPT_DIR/guard-hooks/guard_hooks.py" ] && ln -sf "$SCRIPT_DIR/guard-hooks/guard_hooks.py" "$BIN_DIR/guard-hooks" && chmod +x "$SCRIPT_DIR/guard-hooks/guard_hooks.py"
[ -f "$SCRIPT_DIR/parallel-test-lane/parallel_test_lane.py" ] && ln -sf "$SCRIPT_DIR/parallel-test-lane/parallel_test_lane.py" "$BIN_DIR/parallel-test-lane" && chmod +x "$SCRIPT_DIR/parallel-test-lane/parallel_test_lane.py"

# worktree harness
[ -f "$SCRIPT_DIR/worktree-harness/scripts/harness.py" ] && ln -sf "$SCRIPT_DIR/worktree-harness/scripts/harness.py" "$BIN_DIR/worktree-harness" && chmod +x "$SCRIPT_DIR/worktree-harness/scripts/harness.py"

# video miner
[ -f "$SCRIPT_DIR/video-miner/scripts/videomine.py" ] && ln -sf "$SCRIPT_DIR/video-miner/scripts/videomine.py" "$BIN_DIR/video-miner" && chmod +x "$SCRIPT_DIR/video-miner/scripts/videomine.py"

if [ "$DO_PUSH" = true ]; then
    echo "🚀 [workstation-sync] Committing and pushing updates to GitHub..."
    if [ -d "$SCRIPT_DIR/.git" ]; then
        cd "$SCRIPT_DIR"
        if [ -n "$(git status --porcelain)" ]; then
            git add -A
            git commit -m "sync: workstation skills update [$(date -u +'%Y-%m-%dT%H:%M:%SZ')]"
            git push origin main
        else
            echo "✅ Working tree is already clean. Nothing to commit."
        fi
    fi
fi

echo "✅ All workstation skills synchronized into harnesses and ~/.local/bin."
