#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent / "scripts"))
from ocr_engine import OCREngine, LIGHTON_LAUNCHER, CRISP_LAUNCHER, LIGHTON_MODEL_DIR, CRISP_MODELS_DIR


def main():
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON format")
    parent_parser.add_argument("--host", default=None, help="OCR server host (default: $OCR_HOST or 127.0.0.1, supports Tailscale *.ts.net)")
    parent_parser.add_argument("--lighton-port", type=int, default=8085, help="LightOnOCR port (default: 8085)")
    parent_parser.add_argument("--crisp-port", type=int, default=8084, help="CrispEmbed port (default: 8084)")

    parser = argparse.ArgumentParser(
        description="ocr — Unified High-Performance OCR Hub (Premier LightOnOCR-3-1B + CrispEmbed Spatial)",
        parents=[parent_parser]
    )
    sub = parser.add_subparsers(dest="command")

    # Primary OCR parser
    p_read = sub.add_parser("read", aliases=["doc", "scan"], parents=[parent_parser], help="Document & Slide OCR via premier LightOnOCR-3-1B")
    p_read.add_argument("file", help="Input document (.pdf) or image (.png/.jpg)")
    p_read.add_argument("--prompt", "-p", default=None, help="Custom extraction prompt")
    p_read.add_argument("--pages", help="PDF page range selection (e.g. 1-3,5)")
    p_read.add_argument("--boxes", "--spatial", dest="spatial_mode", action="store_true", help="Extract spatial 2D bounding boxes via CrispEmbed")
    p_read.add_argument("--output", "-o", help="Write output to text/markdown file")

    # Spatial scene-text parser
    p_spat = sub.add_parser("spatial", aliases=["boxes"], parents=[parent_parser], help="Spatial Scene Text & Bounding Box OCR via CrispEmbed")
    p_spat.add_argument("image", help="Input image file (.png/.jpg)")
    p_spat.add_argument("--min-conf", type=float, default=0.0, help="Minimum confidence cutoff (0.0 - 1.0)")
    p_spat.add_argument("--output", "-o", help="Write JSON or markdown to file")

    # Doctor
    sub.add_parser("doctor", parents=[parent_parser], help="Check LightOnOCR and CrispEmbed hardware, models, and server ports")

    # Server manager
    p_srv = sub.add_parser("server", parents=[parent_parser], help="Manage local OCR server daemons")
    p_srv.add_argument("action", choices=["start", "stop", "status", "restart"], help="Lifecycle action")
    p_srv.add_argument("--engine", choices=["lighton", "crispembed", "all"], default="lighton", help="Target engine (default: lighton)")

    # Support running `ocr file.png` directly without subcommand
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] not in ("read", "doc", "scan", "spatial", "boxes", "doctor", "server"):
        sys.argv.insert(1, "read")

    args = parser.parse_args()
    engine = OCREngine(lighton_port=args.lighton_port, crisp_port=args.crisp_port, host=args.host)

    if args.command in ("read", "doc", "scan", None):
        if not getattr(args, "file", None):
            parser.print_help()
            sys.exit(1)

        file_p = Path(args.file).resolve()
        if not file_p.is_file():
            sys.exit(f"❌ Error: File not found: {args.file}")

        if getattr(args, "spatial_mode", False):
            res = engine.ocr_spatial(file_p)
            if args.output:
                Path(args.output).resolve().write_text(json.dumps(res, indent=2) if args.json else res["markdown"], encoding="utf-8")
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                for item in res["results"]:
                    bbox_str = f"[{item['bbox'][0]:.1f}, {item['bbox'][1]:.1f}, {item['bbox'][2]:.1f}, {item['bbox'][3]:.1f}]"
                    print(f"📍 {bbox_str} ({item['confidence']*100:.1f}%) -> {item['text']}")
            return

        res = engine.ocr_document(file_p, prompt=args.prompt, pages=args.pages)
        if args.output:
            Path(args.output).resolve().write_text(json.dumps(res, indent=2) if args.json else res["text"], encoding="utf-8")

        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(res["text"])

    elif args.command in ("spatial", "boxes"):
        img_p = Path(args.image).resolve()
        if not img_p.is_file():
            sys.exit(f"❌ Error: Image not found: {args.image}")

        res = engine.ocr_spatial(img_p)
        if args.min_conf > 0.0:
            res["results"] = [r for r in res["results"] if r["confidence"] >= args.min_conf]
            res["n_regions"] = len(res["results"])

        if args.output:
            Path(args.output).resolve().write_text(json.dumps(res, indent=2) if args.json else res["markdown"], encoding="utf-8")

        if args.json:
            print(json.dumps(res, indent=2))
        else:
            for item in res["results"]:
                bbox_str = f"[{item['bbox'][0]:.1f}, {item['bbox'][1]:.1f}, {item['bbox'][2]:.1f}, {item['bbox'][3]:.1f}]"
                print(f"📍 {bbox_str} ({item['confidence']*100:.1f}%) -> {item['text']}")

    elif args.command == "doctor":
        lighton_ok = engine.is_lighton_online()
        crisp_ok = engine.is_crisp_online()
        doc = {
            "premier_engine": "LightOnOCR-3-1B",
            "lighton_online": lighton_ok,
            "lighton_port": args.lighton_port,
            "lighton_models_ready": LIGHTON_MODEL_DIR.is_dir(),
            "spatial_engine": "CrispEmbed (PP-OCRv6 DB++)",
            "crisp_online": crisp_ok,
            "crisp_port": args.crisp_port,
            "crisp_models_ready": CRISP_MODELS_DIR.is_dir(),
        }
        if args.json:
            print(json.dumps(doc, indent=2))
        else:
            print("🔍 [ocr] Diagnostic Health Check:")
            print(f"  Premier Engine   : LightOnOCR-3-1B (port {args.lighton_port})")
            print(f"  LightOn Status   : {'🟢 Active' if lighton_ok else '⚪ Inactive (auto-start ready)'}")
            print(f"  Spatial Engine   : CrispEmbed PP-OCRv6 (port {args.crisp_port})")
            print(f"  CrispEmbed Status: {'🟢 Active' if crisp_ok else '⚪ Inactive (direct fallback ready)'}")

    elif args.command == "server":
        target = args.engine
        if args.action == "status":
            st = {
                "lighton": "online" if engine.is_lighton_online() else "offline",
                "crispembed": "online" if engine.is_crisp_online() else "offline",
            }
            if args.json:
                print(json.dumps(st, indent=2))
            else:
                print(f"LightOnOCR (:8085): {st['lighton'].upper()}")
                print(f"CrispEmbed (:8084): {st['crispembed'].upper()}")

        elif args.action == "start":
            if target in ("lighton", "all"):
                ok = engine.ensure_lighton()
                print(f"LightOnOCR (:8085): {'STARTED' if ok else 'FAILED'}")
            if target in ("crispembed", "all"):
                if not engine.is_crisp_online():
                    subprocess.Popen([str(CRISP_LAUNCHER)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                    time.sleep(1.0)
                print(f"CrispEmbed (:8084): {'STARTED' if engine.is_crisp_online() else 'FAILED'}")

        elif args.action == "stop":
            ports = []
            if target in ("lighton", "all"):
                ports.append(args.lighton_port)
            if target in ("crispembed", "all"):
                ports.append(args.crisp_port)
            for p in ports:
                subprocess.run(["fuser", "-k", f"{p}/tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Stopped server daemons on ports: {ports}")


if __name__ == "__main__":
    main()
