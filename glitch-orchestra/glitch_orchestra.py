#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "scripts"))
from orchestra_conductor import OrchestraConductor


def main():
    parser = argparse.ArgumentParser(description="Glitch Orchestra CLI — Terminal Conductor & Multi-Session Supervisor")
    parser.add_argument("--dir", default=".", help="Workspace directory (default: .)")
    parser.add_argument("--json", action="store_true", help="Output in structured JSON")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # register
    p_reg = subparsers.add_parser("register", help="Register child terminal agent session")
    p_reg.add_argument("--id", required=True, help="Session ID")
    p_reg.add_argument("--task", required=True, help="Task description")
    p_reg.add_argument("--term", default="term_01", help="Terminal label")

    # complete
    p_comp = subparsers.add_parser("complete", help="Mark session completed")
    p_comp.add_argument("--id", required=True, help="Session ID")
    p_comp.add_argument("--summary", default="Finished", help="Completion summary")

    # alert
    p_alt = subparsers.add_parser("alert", help="Trigger completion alert chime")
    p_alt.add_argument("--message", default="All subagent workers finished.", help="Alert announcement message")

    # status
    subparsers.add_parser("status", help="View active and completed conductor sessions")

    args = parser.parse_args()
    conductor = OrchestraConductor(Path(args.dir))

    if args.command == "register":
        s = conductor.register_child_session(args.id, args.task, args.term)
        print(f"🎻 [Conductor] Registered session '{s['session_id']}' on {s['terminal_tag']}")

    elif args.command == "complete":
        c = conductor.mark_session_complete(args.id, args.summary)
        print(f"✓ [Conductor] Completed session '{c['session_id']}'")

    elif args.command == "alert":
        al = conductor.trigger_completion_alert(args.message)
        print(f"🔔 [Alert] {al['alert_message']}")

    elif args.command == "status":
        st = conductor.status()
        if args.json:
            print(json.dumps(st, indent=2))
        else:
            print(f"🎼 Glitch Orchestra Conductor Status:")
            print(f"  • Active Child Sessions ({st['active_count']}): {[s['session_id'] for s in st['active_sessions']]}")
            print(f"  • Completed ({st['completed_count']}): {[s['session_id'] for s in st['completed_sessions']]}")


if __name__ == "__main__":
    main()
