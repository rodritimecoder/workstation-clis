#!/usr/bin/env python3
"""
vram_rig_ctl.py — Smart GPU VRAM & Port Switcher with Resident King Architecture
Manages ports 8080-8090 and LiteLLM gateway on port 4000 across Linux and macOS.
"""

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = BASE_DIR / "config" / "port_registry.json"
LITELLM_CONFIG = BASE_DIR / "config" / "litellm_config.yaml"
LOG_DIR = Path("/tmp/local-llm-ports")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_registry():
    if not REGISTRY_PATH.is_file():
        return {
            "total_vram_budget_mb": 32000,
            "pinned_port": "8080",
            "models": {}
        }
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def get_vram_info():
    """Detect total and free VRAM (MB) across Linux AMD DRM, NVIDIA, or macOS Unified Memory."""
    total_mb, used_mb = 0, 0

    # 1. Linux DRM sysfs (AMD RX GPUs / ROCm)
    drm_cards = sorted(Path("/sys/class/drm").glob("card[0-9]/device"))
    found_sysfs = False
    for dev in drm_cards:
        t_file = dev / "mem_info_vram_total"
        u_file = dev / "mem_info_vram_used"
        if t_file.exists() and u_file.exists():
            try:
                total_mb += int(t_file.read_text().strip()) // (1024 * 1024)
                used_mb += int(u_file.read_text().strip()) // (1024 * 1024)
                found_sysfs = True
            except Exception:
                pass
    if found_sysfs and total_mb > 0:
        return {"total_mb": total_mb, "used_mb": used_mb, "free_mb": max(0, total_mb - used_mb), "backend": "amdgpu-sysfs"}

    # 2. NVIDIA SMI
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in out.strip().splitlines():
            t, u = [int(x.strip()) for x in line.split(",")]
            total_mb += t
            used_mb += u
        return {"total_mb": total_mb, "used_mb": used_mb, "free_mb": max(0, total_mb - used_mb), "backend": "nvidia-smi"}
    except Exception:
        pass

    # 3. macOS Apple Silicon (Unified Memory)
    if sys.platform == "darwin":
        try:
            mem_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
            total_mb = mem_bytes // (1024 * 1024)
            # Estimate available memory
            vm = subprocess.check_output(["vm_stat"], text=True)
            page_size = 4096
            free_pages = 0
            for line in vm.splitlines():
                if "Pages free" in line or "Pages speculative" in line:
                    free_pages += int(line.split(":")[1].strip().rstrip("."))
            free_mb = (free_pages * page_size) // (1024 * 1024)
            return {"total_mb": total_mb, "used_mb": total_mb - free_mb, "free_mb": free_mb, "backend": "apple-silicon-unified"}
        except Exception:
            pass

    reg = load_registry()
    budget = reg.get("total_vram_budget_mb", 32000)
    return {"total_mb": budget, "used_mb": 0, "free_mb": budget, "backend": "simulated-budget"}


def get_listening_ports(start_port=8080, end_port=8090):
    """Return dict of {port_str: {'pid': int, 'process': str}} for active TCP listeners."""
    active = {}
    target_ports = set(range(start_port, end_port + 1))

    # Try Linux 'ss -tulpn'
    if sys.platform.startswith("linux"):
        try:
            out = subprocess.check_output(["ss", "-tulpn"], stderr=subprocess.DEVNULL, text=True)
            for line in out.splitlines():
                for port in target_ports:
                    if f":{port} " in line:
                        m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                        if m:
                            active[str(port)] = {"process": m.group(1), "pid": int(m.group(2))}
                        else:
                            active[str(port)] = {"process": "unknown", "pid": None}
            return active
        except Exception:
            pass

    # Try macOS / POSIX 'lsof -nP -iTCP -sTCP:LISTEN'
    try:
        out = subprocess.check_output(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], stderr=subprocess.DEVNULL, text=True)
        for line in out.splitlines():
            for port in target_ports:
                if f":{port} " in line or f":{port}->" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        p_name = parts[0]
                        p_pid = int(parts[1]) if parts[1].isdigit() else None
                        active[str(port)] = {"process": p_name, "pid": p_pid}
        return active
    except Exception:
        pass

    # Fallback socket check
    for port in target_ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.1)
        res = s.connect_ex(("127.0.0.1", port))
        s.close()
        if res == 0:
            active[str(port)] = {"process": "listening", "pid": None}

    return active


def kill_port(port_str):
    p_int = int(port_str)
    active = get_listening_ports(p_int, p_int)
    info = active.get(str(port_str))
    if not info:
        print(f"Port {port_str} is already free.")
        return False

    pid = info.get("pid")
    if pid:
        print(f"Stopping PID {pid} ({info['process']}) on port {port_str}...")
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(10):
                time.sleep(0.3)
                if str(port_str) not in get_listening_ports(p_int, p_int):
                    print(f"✅ Port {port_str} freed.")
                    return True
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
        except ProcessLookupError:
            pass
    else:
        # Try fuser or lsof kill
        subprocess.run(f"lsof -ti:{port_str} | xargs kill -9", shell=True, stderr=subprocess.DEVNULL)

    print(f"✅ Port {port_str} freed.")
    return True


def cmd_status():
    registry = load_registry()
    vram = get_vram_info()
    active = get_listening_ports(8080, 8090)
    gw_active = get_listening_ports(4000, 4000)

    pinned_port = registry.get("pinned_port", "8080")
    report = {
        "vram": vram,
        "litellm_gateway_4000": "ONLINE" if "4000" in gw_active else "OFFLINE",
        "pinned_king_port": pinned_port,
        "ports_8080_8090": {},
    }
    for p_str, meta in registry.get("models", {}).items():
        state = active.get(p_str)
        report["ports_8080_8090"][p_str] = {
            "alias": meta.get("alias"),
            "pinned": meta.get("pinned", False),
            "est_vram_mb": meta.get("vram_mb"),
            "status": "RUNNING" if state else "STOPPED",
            "pid": state.get("pid") if state else None,
        }
    print(json.dumps(report, indent=2))


def cmd_swap(target_port):
    registry = load_registry()
    models = registry.get("models", {})
    if str(target_port) not in models:
        sys.exit(f"❌ Error: Port {target_port} is not defined in {REGISTRY_PATH}")

    target_meta = models[str(target_port)]
    active = get_listening_ports(8080, 8090)
    if str(target_port) in active:
        print(f"ℹ️  Port {target_port} ({target_meta['alias']}) is already running.")
        return

    needed_mb = target_meta.get("vram_mb", 4000)
    vram = get_vram_info()
    pinned_port = registry.get("pinned_port", "8080")

    # Smart Headroom Check:
    # 1. Evict non-pinned ports first if free VRAM is too low
    if vram["free_mb"] < needed_mb:
        print(f"⚠️ Need {needed_mb} MB VRAM, but only {vram['free_mb']} MB available.")
        print("   Evicting non-pinned auxiliary ports...")
        for p_str in sorted(active.keys()):
            if p_str != pinned_port and p_str != str(target_port):
                kill_port(p_str)
                time.sleep(0.5)
                vram = get_vram_info()
                if vram["free_mb"] >= needed_mb:
                    break

    # 2. If STILL not enough VRAM and target is heavy, only then pause pinned king
    if vram["free_mb"] < needed_mb and pinned_port in active and str(target_port) != pinned_port:
        print(f"⚠️ Heavy task requires {needed_mb} MB. Temporarily evicting pinned King (port {pinned_port})...")
        kill_port(pinned_port)
        time.sleep(1.0)

    # 3. Launch target model
    cmd_str = os.path.expanduser(target_meta["cmd"])
    log_file = LOG_DIR / f"port_{target_port}.log"
    print(f"🚀 Starting {target_meta['alias']} on port {target_port}...")
    with open(log_file, "ab") as out:
        subprocess.Popen(cmd_str, shell=True, stdout=out, stderr=out, start_new_session=True)

    # Wait up to 20s for socket bind
    for _ in range(40):
        time.sleep(0.5)
        if str(target_port) in get_listening_ports(int(target_port), int(target_port)):
            print(f"✅ SUCCESS: {target_meta['alias']} listening on port {target_port}. Logs: {log_file}")
            return

    print(f"Launched process on port {target_port} (still loading weights—check {log_file}).")


def cmd_gateway_up():
    if "4000" in get_listening_ports(4000, 4000):
        print("ℹ️  LiteLLM Gateway is already running on port 4000.")
        return
    log_file = LOG_DIR / "litellm_4000.log"
    cmd = f"litellm --config {LITELLM_CONFIG} --port 4000 --host 0.0.0.0"
    print("🚀 Starting LiteLLM Gateway on port 4000...")
    with open(log_file, "ab") as out:
        subprocess.Popen(cmd, shell=True, stdout=out, stderr=out, start_new_session=True)
    time.sleep(2)
    print(f"✅ LiteLLM Gateway started on http://0.0.0.0:4000 (Logs: {log_file})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPU VRAM & Port Switcher with Resident King Architecture")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("status")
    sub.add_parser("evict-all")
    sub.add_parser("gateway-up")

    p_kill = sub.add_parser("kill")
    p_kill.add_argument("--port", required=True)

    p_swap = sub.add_parser("swap")
    p_swap.add_argument("--port", required=True)

    args = parser.parse_args()
    if args.action == "status":
        cmd_status()
    elif args.action == "kill":
        kill_port(str(args.port))
    elif args.action == "evict-all":
        reg = load_registry()
        pinned = reg.get("pinned_port", "8080")
        for p in list(get_listening_ports(8080, 8090).keys()):
            if p != pinned:
                kill_port(p)
        print("✅ Evicted auxiliary ports. Headroom reclaimed.")
    elif args.action == "swap":
        cmd_swap(str(args.port))
    elif args.action == "gateway-up":
        cmd_gateway_up()
