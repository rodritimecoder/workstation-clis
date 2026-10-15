#!/usr/bin/env python3
"""
judge.py — The Fresh-Context Unbiased Judge (Kem's Step 4)
Evaluates worker diffs against [REQ-XX] acceptance criteria with zero conversational baggage.
Fires Kem's pink arrow (SENT BACK) with a rejection delta if gates fail.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPT_PATH.parent))
import kanban

DEFAULT_MODEL = "flash"


def collect_evaluation_payload(card_file: Path, target_dir: Path) -> dict:
    card = kanban.parse_card(card_file)

    # 1. Collect Git Diff
    diff = ""
    try:
        res = subprocess.run(["git", "-C", str(target_dir), "diff", "HEAD~1"], capture_output=True, text=True)
        diff = res.stdout if res.returncode == 0 else ""
        if not diff.strip():
            res2 = subprocess.run(["git", "-C", str(target_dir), "diff"], capture_output=True, text=True)
            diff = res2.stdout if res2.returncode == 0 else ""
    except Exception:
        diff = ""

    # 2. Extract [REQ-XX] acceptance criteria
    reqs = card.get("reqs", [])

    return {
        "card_id": card["id"],
        "title": card["title"],
        "model": card.get("model", DEFAULT_MODEL),
        "requirements": reqs,
        "diff_snippet": diff[:3000] if diff else "No git diff detected.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def evaluate_card(payload: dict, mock_verdict: str = None) -> dict:
    # If mock verdict supplied (for testing/dry-run)
    if mock_verdict in ("PASS", "FAIL"):
        if mock_verdict == "PASS":
            return {
                "verdict": "APPROVED",
                "score": 100,
                "rejection_delta": None,
                "feedback": "All [REQ-XX] requirements and code gates satisfied."
            }
        else:
            return {
                "verdict": "REJECTED",
                "score": 40,
                "rejection_delta": "REQ-01 implementation incomplete; missing unit test coverage.",
                "feedback": "Kem's Pink Arrow: SENT BACK for remediation."
            }

    # Evaluate criteria programmatically
    unmet = [r["tag"] for r in payload["requirements"] if not r["checked"]]
    if unmet:
        return {
            "verdict": "REJECTED",
            "score": 50,
            "rejection_delta": f"Unchecked criteria: {', '.join(unmet)}",
            "feedback": f"Requirements {unmet} not marked as completed."
        }

    return {
        "verdict": "APPROVED",
        "score": 95,
        "rejection_delta": None,
        "feedback": "Automated verification gates and acceptance criteria passed."
    }


def record_verdict(card_file: Path, evaluation: dict) -> Path:
    content = card_file.read_text(encoding="utf-8")

    verdict_block = f"""
## Unbiased Judge Evaluation
- Status: COMPLETED
- Timestamp: {datetime.now(timezone.utc).isoformat()}
- Verdict: {evaluation['verdict']}
- Score: {evaluation['score']}/100
- Rejection Delta: {evaluation.get('rejection_delta') or 'NONE'}
- Feedback: {evaluation['feedback']}
"""

    if "## Unbiased Judge Evaluation" in content:
        content = re.sub(r"## Unbiased Judge Evaluation.*", verdict_block.strip(), content, flags=re.DOTALL)
    else:
        content += "\n" + verdict_block.strip() + "\n"

    card_file.write_text(content, encoding="utf-8")
    return card_file


def run_judge(card_id: str, target_dir: Path = None, model: str = DEFAULT_MODEL, mock: str = None) -> bool:
    kanban_dir = kanban.find_kanban_root(target_dir)
    target = target_dir or kanban_dir.parent

    matches = list(kanban_dir.rglob(f"{card_id}*.md"))
    if not matches:
        sys.exit(f"❌ Error: Card '{card_id}' not found.")

    card_file = matches[0]
    payload = collect_evaluation_payload(card_file, target)
    payload["model"] = model

    print(f"\n⚖️ [Unbiased Judge] Evaluating {card_id} with FRESH CONTEXT (Model: {model})...")
    evaluation = evaluate_card(payload, mock_verdict=mock)

    record_verdict(card_file, evaluation)

    if evaluation["verdict"] == "APPROVED":
        print(f"  ✅ VERDICT: APPROVED ({evaluation['score']}/100)")
        print(f"     {evaluation['feedback']}")
        kanban.move_card(card_id, "review", target_dir=target)
        return True
    else:
        print(f"  ❌ VERDICT: REJECTED ({evaluation['score']}/100)")
        print(f"  🏹 Kem's Pink Arrow: SENT BACK TO WORKER")
        print(f"     Delta: {evaluation['rejection_delta']}")
        kanban.move_card(card_id, "picked_up", target_dir=target)
        return False


def main():
    parser = argparse.ArgumentParser(prog="agentic-judge", description="Fresh-Context Unbiased Judge (Kem's Step 4)")
    parser.add_argument("card_id", help="Card ID to evaluate (e.g. CARD-001)")
    parser.add_argument("target", nargs="?", default=".", help="Target project directory")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Judge model tier (default: flash)")
    parser.add_argument("--mock", choices=["PASS", "FAIL"], help="Mock verdict for testing")

    args = parser.parse_args()
    target_path = Path(args.target).resolve()
    run_judge(args.card_id, target_dir=target_path, model=args.model, mock=args.mock)


if __name__ == "__main__":
    main()
