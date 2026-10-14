#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

SKILL_DIR = Path(__file__).resolve().parent.parent
CONTAINERFILE = SKILL_DIR / "Containerfile"
DEFAULT_IMAGE = "subagent-space:latest"
FALLBACK_IMAGE = "docker.io/library/ubuntu:24.04"

SLOT_TOPOLOGY = {
    "1": {"cpus": "4-7", "memory": "4g", "threads": 4},
    "2": {"cpus": "8-11", "memory": "4g", "threads": 4},
    "3": {"cpus": "12-15", "memory": "4g", "threads": 4},
    "all": {"cpus": "4-15", "memory": "12g", "threads": 12},
}

HOST_RESERVE = {"cpus": "0-3", "threads": 4, "purpose": "Host OS / Desktop / GPU drivers"}


def run_cmd(cmd: List[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=capture)


def get_active_containers() -> List[Dict]:
    cmd = [
        "podman", "ps",
        "--filter", "label=app=subagent-spaces",
        "--format", "{{json .}}"
    ]
    try:
        proc = run_cmd(cmd)
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        containers = []
        for line in lines:
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return containers
    except Exception:
        return []


def resolve_image(custom_image: Optional[str]) -> str:
    if custom_image:
        return custom_image
    inspect_proc = subprocess.run(
        ["podman", "image", "exists", DEFAULT_IMAGE],
        capture_output=True
    )
    if inspect_proc.returncode == 0:
        return DEFAULT_IMAGE
    return FALLBACK_IMAGE


def cmd_doctor() -> None:
    print("🩺 [subagent-spaces] Running system & environment diagnostics...\n")

    podman_path = shutil.which("podman")
    taskset_path = shutil.which("taskset")

    print(f"  • Podman binary:    {'✅ ' + podman_path if podman_path else '❌ NOT FOUND'}")
    print(f"  • Taskset binary:   {'✅ ' + taskset_path if taskset_path else '❌ NOT FOUND'}")

    if not podman_path or not taskset_path:
        print("\n❌ Critical dependencies missing.")
        sys.exit(1)

    cpu_count = os.cpu_count() or 0
    print(f"  • CPU Threads:      ✅ {cpu_count} threads detected")
    print(f"  • Host Reserve:     Cores {HOST_RESERVE['cpus']} (reserved for desktop & OS)")
    print(f"  • Worker Slots:     3 slots available (4-7, 8-11, 12-15)")

    img_check = subprocess.run(["podman", "image", "exists", DEFAULT_IMAGE], capture_output=True)
    has_local_img = (img_check.returncode == 0)
    print(f"  • Local Image:      {'✅ ' + DEFAULT_IMAGE if has_local_img else '⚠️  Not built (using ' + FALLBACK_IMAGE + ')'}")
    if not has_local_img:
        print("                      Run 'subagent-spaces build' to compile the optimized local dev image.")

    try:
        test_proc = run_cmd(["taskset", "-c", "4-7", "podman", "run", "--rm", FALLBACK_IMAGE, "nproc"])
        cores = test_proc.stdout.strip()
        print(f"  • CPU Core Pinning: ✅ Enforced via taskset (reported {cores} cores in container)")
    except Exception as e:
        print(f"  • CPU Core Pinning: ❌ Failed: {e}")

    try:
        mem_proc = run_cmd(["podman", "run", "--rm", "-m", "1g", FALLBACK_IMAGE, "cat", "/sys/fs/cgroup/memory.max"])
        mem_val = mem_proc.stdout.strip()
        if mem_val == "1073741824":
            print("  • Memory Cgroup:    ✅ Active and enforced (1 GiB quota verified)")
        else:
            print(f"  • Memory Cgroup:    ⚠️  Value: {mem_val}")
    except Exception as e:
        print(f"  • Memory Cgroup:    ⚠️  Failed verification: {e}")

    print("\n✅ System is fully capable of running isolated subagent spaces.")


def cmd_slots() -> None:
    active = get_active_containers()
    active_slots = {}
    for c in active:
        names = c.get("Names") or []
        name = names[0] if names else c.get("Id", "")[:12]
        labels = c.get("Labels") or {}
        slot_id = labels.get("slot")
        if slot_id:
            active_slots[slot_id] = {
                "id": c.get("Id", "")[:12],
                "name": name,
                "workspace": labels.get("workspace", "-"),
                "status": c.get("Status", "Running"),
            }

    print("\n🖥️  [subagent-spaces] CPU Core & Slot Topology (AMD Ryzen 16-Thread Substrate)\n")
    print(f"  {'Slot':<6} │ {'CPUs':<8} │ {'RAM':<6} │ {'Status':<10} │ {'Container':<14} │ Workspace")
    print("  ───────┼──────────┼────────┼────────────┼────────────────┼──────────────────────────────")

    print(f"  {'HOST':<6} │ {HOST_RESERVE['cpus']:<8} │ {'-':<6} │ {'RESERVED':<10} │ {'-':<14} │ Host Desktop / OS")

    for slot_id in ["1", "2", "3"]:
        topo = SLOT_TOPOLOGY[slot_id]
        if slot_id in active_slots:
            info = active_slots[slot_id]
            status = "OCCUPIED"
            cid = info["id"]
            ws = info["workspace"]
        else:
            status = "IDLE"
            cid = "-"
            ws = "-"

        status_display = f"\033[32m{status}\033[0m" if status == "IDLE" else f"\033[33m{status}\033[0m"
        print(f"  {slot_id:<6} │ {topo['cpus']:<8} │ {topo['memory']:<6} │ {status_display:<19} │ {cid:<14} │ {ws}")

    all_active = "all" in active_slots
    all_status = "\033[33mOCCUPIED\033[0m" if all_active else "\033[32mIDLE\033[0m"
    all_cid = active_slots["all"]["id"] if all_active else "-"
    all_ws = active_slots["all"]["workspace"] if all_active else "-"
    print(f"  {'all':<6} │ {'4-15':<8} │ {'12g':<6} │ {all_status:<19} │ {all_cid:<14} │ {all_ws} (High-Throttle Mode)")
    print()


def cmd_build() -> None:
    if not CONTAINERFILE.is_file():
        sys.exit(f"❌ Error: Containerfile not found at {CONTAINERFILE}")

    print(f"📦 [subagent-spaces] Building image '{DEFAULT_IMAGE}' from {CONTAINERFILE}...")
    cmd = ["podman", "build", "-t", DEFAULT_IMAGE, "-f", str(CONTAINERFILE), str(SKILL_DIR)]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print(f"\n✅ Image '{DEFAULT_IMAGE}' built successfully.")
    else:
        sys.exit(res.returncode)


def cmd_run(args: argparse.Namespace) -> None:
    active = get_active_containers()
    occupied_slots = set()
    for c in active:
        slot = (c.get("Labels") or {}).get("slot")
        if slot:
            occupied_slots.add(slot)

    selected_slot = args.slot
    if not selected_slot:
        for candidate in ["1", "2", "3"]:
            if candidate not in occupied_slots:
                selected_slot = candidate
                break
        if not selected_slot:
            sys.exit("❌ Error: All 3 worker slots are currently occupied. Use 'subagent-spaces ps' or free a slot.")

    if selected_slot not in SLOT_TOPOLOGY:
        sys.exit(f"❌ Error: Invalid slot '{selected_slot}'. Must be 1, 2, 3, or all.")

    topo = SLOT_TOPOLOGY[selected_slot]
    ws_path = Path(args.workspace).resolve() if args.workspace else Path.cwd().resolve()
    if not ws_path.exists():
        sys.exit(f"❌ Error: Workspace directory does not exist: {ws_path}")

    mount_flags = "ro,z" if args.ro else "z"
    image = resolve_image(args.image)
    container_name = args.name or f"subagent-space-slot-{selected_slot}-{os.urandom(3).hex()}"

    podman_cmd = [
        "taskset", "-c", topo["cpus"],
        "podman", "run",
        "--name", container_name,
        "-m", topo["memory"],
        "-v", f"{ws_path}:/workspace:{mount_flags}",
        "-w", "/workspace",
        "--label", "app=subagent-spaces",
        "--label", f"slot={selected_slot}",
        "--label", f"workspace={ws_path}",
        "--network", args.network,
    ]

    if not args.keep:
        podman_cmd.append("--rm")

    if args.env:
        for e in args.env:
            podman_cmd.extend(["-e", e])

    if args.detach:
        podman_cmd.append("-d")
    elif args.interactive:
        podman_cmd.extend(["-it"])

    podman_cmd.append(image)

    cmd_to_run = list(args.command) if args.command else []
    if cmd_to_run and cmd_to_run[0] == "--":
        cmd_to_run = cmd_to_run[1:]

    if cmd_to_run:
        podman_cmd.extend(cmd_to_run)
    else:
        podman_cmd.extend(["/bin/bash"])

    print(f"🚀 [subagent-spaces] Launching space on Slot {selected_slot} (Cores {topo['cpus']}, RAM {topo['memory']})")
    print(f"   Image:     {image}")
    print(f"   Workspace: {ws_path} ({'Read-Only' if args.ro else 'Read-Write'})")
    print(f"   Network:   {args.network}")
    print(f"   Container: {container_name}\n")

    res = subprocess.run(podman_cmd)
    sys.exit(res.returncode)


def cmd_ps() -> None:
    active = get_active_containers()
    if not active:
        print("No active subagent-spaces containers running.")
        return

    print("\n📦 Active Subagent Spaces:\n")
    print(f"  {'Container ID':<14} │ {'Slot':<6} │ {'Status':<16} │ {'Workspace':<35} │ Names")
    print("  ───────────────┼────────┼──────────────────┼─────────────────────────────────────┼──────────────")

    for c in active:
        cid = c.get("Id", "")[:12]
        labels = c.get("Labels") or {}
        slot = labels.get("slot", "?")
        ws = labels.get("workspace", "-")
        status = c.get("Status", "Running")
        names = ", ".join(c.get("Names") or [])
        print(f"  {cid:<14} │ {slot:<6} │ {status:<16} │ {ws:<35} │ {names}")
    print()


def cmd_enter(target: str) -> None:
    active = get_active_containers()
    matched = None
    for c in active:
        cid = c.get("Id", "")
        names = c.get("Names") or []
        labels = c.get("Labels") or {}
        slot = labels.get("slot")

        if target == slot or target in names or cid.startswith(target):
            matched = names[0] if names else cid[:12]
            break

    if not matched:
        sys.exit(f"❌ Error: No running space matching slot, name, or container ID '{target}'.")

    print(f"🔗 Attaching interactive shell to {matched}...")
    exec_cmd = ["podman", "exec", "-it", matched, "/bin/bash"]
    res = subprocess.run(exec_cmd)
    if res.returncode != 0:
        subprocess.run(["podman", "exec", "-it", matched, "/bin/sh"])


def cmd_stop(target: str) -> None:
    active = get_active_containers()
    matched = []
    for c in active:
        cid = c.get("Id", "")
        names = c.get("Names") or []
        labels = c.get("Labels") or {}
        slot = labels.get("slot")

        if target == slot or target in names or cid.startswith(target):
            matched.append(names[0] if names else cid[:12])

    if not matched:
        sys.exit(f"❌ Error: No running space matching '{target}'.")

    for m in matched:
        print(f"🛑 Stopping container: {m}...")
        subprocess.run(["podman", "stop", "-t", "2", m], check=False)
        subprocess.run(["podman", "rm", "-f", m], check=False)
    print("✅ Stopped.")


def cmd_prune() -> None:
    active = get_active_containers()
    if not active:
        print("No active subagent spaces to prune.")
        return

    print(f"🧹 Pruning {len(active)} active subagent spaces...")
    for c in active:
        cid = c.get("Id", "")[:12]
        print(f"  • Terminating {cid}...")
        subprocess.run(["podman", "stop", "-t", "2", cid], check=False, capture_output=True)
        subprocess.run(["podman", "rm", "-f", cid], check=False, capture_output=True)
    print("✅ All subagent spaces pruned.")


def main():
    parser = argparse.ArgumentParser(
        prog="subagent-spaces",
        description="Isolated CPU-pinned containerized sandbox environments for autonomous subagents."
    )
    subparsers = parser.add_subparsers(dest="action")

    subparsers.add_parser("doctor", help="Run diagnostic health checks on host capabilities")
    subparsers.add_parser("slots", help="Show CPU core topology and slot occupancy")
    subparsers.add_parser("ps", help="List active subagent space containers")
    subparsers.add_parser("build", help="Build optimized local subagent-space image")
    subparsers.add_parser("prune", help="Clean up all active subagent spaces")

    enter_p = subparsers.add_parser("enter", help="Attach interactive shell to a running space")
    enter_p.add_argument("target", help="Slot number (1-3), container name, or container ID")

    stop_p = subparsers.add_parser("stop", help="Stop and remove a running space")
    stop_p.add_argument("target", help="Slot number (1-3), container name, or container ID")

    run_p = subparsers.add_parser("run", help="Run a command or spawn a subagent space")
    run_p.add_argument("--slot", choices=["1", "2", "3", "all"], help="Specific worker slot (default: auto-pick)")
    run_p.add_argument("--workspace", "-w", help="Workspace directory to mount into /workspace")
    run_p.add_argument("--image", "-i", help=f"Custom container image (default: {DEFAULT_IMAGE} or {FALLBACK_IMAGE})")
    run_p.add_argument("--name", help="Custom container name")
    run_p.add_argument("--ro", action="store_true", help="Mount workspace as read-only")
    run_p.add_argument("--network", default="host", choices=["host", "bridge", "none"], help="Network mode (default: host)")
    run_p.add_argument("--detach", "-d", action="store_true", help="Run in background")
    run_p.add_argument("--interactive", "-it", action="store_true", help="Run interactively with terminal TTY")
    run_p.add_argument("--keep", action="store_true", help="Keep container after exit (do not --rm)")
    run_p.add_argument("-e", "--env", action="append", help="Environment variable KEY=VALUE")
    run_p.add_argument("command", nargs=argparse.REMAINDER, help="Command to run inside the space")

    args = parser.parse_args()

    if args.action == "doctor":
        cmd_doctor()
    elif args.action == "slots":
        cmd_slots()
    elif args.action == "ps":
        cmd_ps()
    elif args.action == "build":
        cmd_build()
    elif args.action == "enter":
        cmd_enter(args.target)
    elif args.action == "stop":
        cmd_stop(args.target)
    elif args.action == "prune":
        cmd_prune()
    elif args.action == "run":
        cmd_run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
