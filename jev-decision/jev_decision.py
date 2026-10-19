#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "scripts"))
from jev_engine import JevEngine


def main():
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--host", default=None, help="Decision host (default: $JEV_HOST or 127.0.0.1, supports Tailscale *.ts.net)")
    parent_parser.add_argument("--port", type=int, default=8083, help="Decision service port (default: 8083 = vllm-d3-mini, 8086 = OneJev fallback)")
    parent_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # Subparsers re-declare the shared options with SUPPRESS so that a --port
    # given before the subcommand is not silently overwritten by the default.
    sub_parent = argparse.ArgumentParser(add_help=False)
    sub_parent.add_argument("--host", default=argparse.SUPPRESS)
    sub_parent.add_argument("--port", type=int, default=argparse.SUPPRESS)
    sub_parent.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(description="JEV Decision Engine CLI — vllm-d3-mini native /v1/systemone (OneJev fallback)", parents=[parent_parser])
    subparsers = parser.add_subparsers(dest="command", required=True)

    # bool
    p_bool = subparsers.add_parser("bool", parents=[sub_parent], help="Binary boolean decision primitive")
    p_bool.add_argument("--context", required=True, help="Input context or background facts")
    p_bool.add_argument("--question", required=True, help="Binary question to decide (Yes/No)")
    p_bool.add_argument("--image", default=None, help="Optional image path or base64 data for vision decision")

    # choice
    p_choice = subparsers.add_parser("choice", parents=[sub_parent], help="Constrained discrete enum selection primitive")
    p_choice.add_argument("--context", required=True, help="Input context or background facts")
    p_choice.add_argument("--question", required=True, help="Question to decide")
    p_choice.add_argument("--options", nargs="+", required=True, help="Candidate options list")
    p_choice.add_argument("--image", default=None, help="Optional image path or base64 data for vision decision")

    # score
    p_score = subparsers.add_parser("score", parents=[sub_parent], help="Continuous scalar magnitude score primitive (0.0 to 1.0)")
    p_score.add_argument("--context", required=True, help="Input context to score")
    p_score.add_argument("--criteria", required=True, help="Criteria for evaluation")
    p_score.add_argument("--image", default=None, help="Optional image path or base64 data for vision decision")

    # composite
    p_comp = subparsers.add_parser("composite", parents=[sub_parent], help="Composite decision primitive (gate bool + action choice + quality score)")
    p_comp.add_argument("--context", required=True, help="Input context or background facts")
    p_comp.add_argument("--question", required=True, help="Question to decide")
    p_comp.add_argument("--options", nargs="+", required=True, help="Candidate options list")
    p_comp.add_argument("--criteria", default=None, help="Optional quality criteria")
    p_comp.add_argument("--image", default=None, help="Optional image path or base64 data for vision decision")

    # clean-context
    p_clean = subparsers.add_parser("clean-context", parents=[sub_parent], help="Pairwise context de-duplication and superseding prune")
    p_clean.add_argument("--claims-file", required=True, help="JSON file containing array of {timestamp, text} claims")

    # uat
    p_uat = subparsers.add_parser("uat", parents=[sub_parent], help="Frontend acceptance action decider with optional visual grounding")
    p_uat.add_argument("--intent", required=True, help="User test intent (e.g., 'Click the login button')")
    p_uat.add_argument("--dom-file", required=True, help="JSON file containing array of {id, text, tag} clickable elements")
    p_uat.add_argument("--image", default=None, help="Optional UI screenshot for visual UAT")

    args = parser.parse_args()
    args.port = getattr(args, "port", 8083)
    args.json = getattr(args, "json", False)
    engine = JevEngine(host=getattr(args, "host", None), port=args.port)

    if args.command == "bool":
        res = engine.decide_bool(args.context, args.question, image=args.image)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            status = "YES" if res["decision"] else "NO"
            print(f"⚖️ [JEV Bool] -> {status} (Confidence: {res['confidence'] * 100:.1f}%) [{res['source']}]")

    elif args.command == "choice":
        res = engine.decide_choice(args.context, args.question, args.options, image=args.image)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"🎯 [JEV Choice] -> '{res['selection']}' (Confidence: {res['confidence'] * 100:.1f}%) [{res['source']}]")

    elif args.command == "score":
        res = engine.decide_score(args.context, args.criteria, image=args.image)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"📊 [JEV Score] -> {res['score']:.4f} / 1.0000 [{res['source']}]")

    elif args.command == "composite":
        res = engine.decide_composite(args.context, args.question, args.options, criteria=args.criteria, image=args.image)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            gate_status = "PASS" if res["gate"] else "FAIL"
            print(f"🎛️ [JEV Composite] Gate: {gate_status} | Action: '{res['action']}' | Score: {res['quality_score']:.4f} [{res['source']}]")

    elif args.command == "clean-context":
        claims = json.loads(Path(args.claims_file).read_text(encoding="utf-8"))
        res = engine.clean_context_claims(claims)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"🧹 [JEV Context Cleaner] Mined {res['total_input_claims']} claims:")
            print(f"  • Retained active: {res['active_claims_retained']}")
            print(f"  • Superseded/Pruned: {res['superseded_count']}")

    elif args.command == "uat":
        elements = json.loads(Path(args.dom_file).read_text(encoding="utf-8"))
        res = engine.evaluate_uat_target(elements, args.intent, image=args.image)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"🖱️ [JEV UAT] Selected target '{res['selected_id']}' for intent '{args.intent}' (Confidence: {res['confidence'] * 100:.1f}%) [{res['source']}]")


if __name__ == "__main__":
    main()
