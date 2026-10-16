#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_VAULT_DIR = Path("/run/media/rodri/AI/creator-vault")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "_", text)[:60]

def get_video_info(url_or_path: str) -> Dict[str, Any]:
    if Path(url_or_path).is_file():
        p = Path(url_or_path)
        return {
            "title": p.stem,
            "creator": "local",
            "upload_date": datetime.date.today().strftime("%Y%m%d"),
            "duration": None,
            "is_local": True,
        }
    cmd = ["yt-dlp", "--dump-json", "--no-warnings", url_or_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            uploader = data.get("uploader") or data.get("channel") or data.get("uploader_id") or "creator"
            title = data.get("fulltitle") or data.get("title") or "video"
            upload_date = data.get("upload_date") or datetime.date.today().strftime("%Y%m%d")
            return {
                "title": title,
                "creator": uploader,
                "upload_date": upload_date,
                "duration": data.get("duration"),
                "is_local": False,
            }
        except Exception:
            pass
    return {
        "title": "video",
        "creator": "creator",
        "upload_date": datetime.date.today().strftime("%Y%m%d"),
        "duration": None,
        "is_local": False,
    }

def update_vault_index(vault_dir: Path) -> None:
    index_file = vault_dir / "INDEX.md"
    rows: List[str] = []
    for creator_dir in sorted(vault_dir.iterdir()):
        if not creator_dir.is_dir() or creator_dir.name.startswith("."):
            continue
        for entry_dir in sorted(creator_dir.iterdir(), reverse=True):
            if not entry_dir.is_dir():
                continue
            notes_file = entry_dir / "notes.md"
            transcript_file = entry_dir / "transcript.md"
            visuals_dir = entry_dir / "visuals"
            num_visuals = len(list(visuals_dir.glob("*.jpg"))) if visuals_dir.is_dir() else 0
            has_notes = "✅" if notes_file.is_file() else "❌"
            has_transcript = "✅" if transcript_file.is_file() else "❌"
            rel_path = f"{creator_dir.name}/{entry_dir.name}/notes.md"
            rows.append(f"| {entry_dir.name[:10]} | `{creator_dir.name}` | [{entry_dir.name[11:]}]({rel_path}) | {has_transcript} | {num_visuals} frames | {has_notes} |")

    header = "# Creator Video Vault Index\n\nCurated archive of mined engineering videos, architectural diagrams, and full transcripts.\n\n"
    table_header = "| Date | Creator | Title | Transcript | Visuals | Notes |\n| :--- | :--- | :--- | :---: | :---: | :---: |\n"
    index_file.write_text(header + table_header + "\n".join(rows) + "\n")


def ocr_frame(image_path: Path) -> str:
    # 1. First attempt fast HTTP API on :8085 if LightOnOCR server is live
    try:
        import base64
        import urllib.request
        img_bytes = image_path.read_bytes()
        b64 = base64.b64encode(img_bytes).decode("ascii")
        payload = json.dumps({
            "model": "LightOnOCR-3-1B",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all diagram labels, text, and architecture flow in markdown."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
            ],
            "max_tokens": 300,
            "temperature": 0.1
        }).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8085/v1/chat/completions", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if content.strip():
                return content.strip()
    except Exception:
        pass

    # 2. Fall back to standalone llama-mtmd-cli
    cli = Path("/run/media/rodri/AI/llama.cpp/build/bin/llama-mtmd-cli")
    model = Path("/run/media/rodri/AI/models/prithivMLmods/LightOnOCR-3-1B-GGUF/LightOnOCR-3-1B.Q4_K_M.gguf")
    mmproj = Path("/run/media/rodri/AI/models/prithivMLmods/LightOnOCR-3-1B-GGUF/LightOnOCR-3-1B.mmproj-q8_0.gguf")
    if not (cli.is_file() and model.is_file() and mmproj.is_file()):
        return ""
    cmd = [
        str(cli),
        "-m", str(model),
        "--mmproj", str(mmproj),
        "--image", str(image_path),
        "-p", "Extract all diagram labels, text, and architecture flow in markdown.",
        "-n", "300", "-ngl", "99", "--temp", "0.1"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        lines = res.stdout.splitlines()
        content: List[str] = []
        started = False
        for line in lines:
            if started:
                content.append(line)
            elif line.startswith("system_info:") or line.startswith("llama_perf_"):
                continue
            elif not line.startswith("llama_") and not line.startswith("load_"):
                started = True
                content.append(line)
        return "\n".join(content).strip()
    return ""

def import_workspace(workspace_dir: Path, creator: str, title: str, vault_dir: Path = DEFAULT_VAULT_DIR, run_ocr: bool = True) -> Path:
    ws = Path(workspace_dir).resolve()
    creator_slug = slugify(creator)
    title_slug = slugify(title)
    date_str = datetime.date.today().strftime("%Y-%m-%d")

    target_dir = vault_dir / creator_slug / f"{date_str}_{title_slug}"
    visuals_dir = target_dir / "visuals"
    target_dir.mkdir(parents=True, exist_ok=True)
    visuals_dir.mkdir(parents=True, exist_ok=True)

    src_video = ws / "stages/01_acquire/output/source_video.mp4"
    if src_video.is_file():
        shutil.copy2(src_video, target_dir / "source.mp4")

    src_transcript = ws / "stages/02_audio_asr/output/transcript.md"
    if src_transcript.is_file():
        shutil.copy2(src_transcript, target_dir / "transcript.md")

    frames_dir = ws / "stages/03_visual_sample/output/frames"
    copied_frames: List[Path] = []
    if frames_dir.is_dir():
        for f in sorted(frames_dir.glob("*.jpg")):
            dst = visuals_dir / f.name
            shutil.copy2(f, dst)
            copied_frames.append(dst)

    transcript_content = (target_dir / "transcript.md").read_text() if (target_dir / "transcript.md").is_file() else ""

    notes_lines = [
        f"# {title}",
        "",
        f"- **Creator:** `{creator}`",
        f"- **Mined Date:** {date_str}",
        f"- **Source:** [source.mp4](source.mp4)",
        f"- **Transcript:** [transcript.md](transcript.md)",
        f"- **Captured Visuals:** {len(copied_frames)} frames",
        "",
        "## Key Visuals & Diagrams (LightOnOCR-3-1B)",
        "",
    ]

    for cf in copied_frames[:6]:
        notes_lines.append(f"### Visual: `{cf.name}`\n")
        notes_lines.append(f"![{cf.name}](visuals/{cf.name})\n")
        if run_ocr:
            ocr_text = ocr_frame(cf)
            if ocr_text:
                notes_lines.append("```markdown")
                notes_lines.append(ocr_text)
                notes_lines.append("```\n")

    notes_lines.extend([
        "## Full Audio Transcript",
        "",
        transcript_content if transcript_content else "_No transcript extracted._",
        "",
    ])

    (target_dir / "notes.md").write_text("\n".join(notes_lines))
    update_vault_index(vault_dir)
    return target_dir

def mine_url(url_or_file: str, creator: Optional[str] = None, title: Optional[str] = None, vault_dir: Path = DEFAULT_VAULT_DIR) -> Path:
    info = get_video_info(url_or_file)
    creator_name = creator or info["creator"]
    title_name = title or info["title"]

    tmp_run = Path(f"/tmp/videomine_run_{int(datetime.datetime.now().timestamp())}")
    try:
        import videomine
    except ImportError:
        import importlib.util
        script_path = Path(__file__).resolve().parent / "videomine.py"
        spec = importlib.util.spec_from_file_location("videomine", script_path)
        videomine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(videomine)

    videomine.init_workspace(tmp_run, url_or_file)
    videomine.run_pipeline(tmp_run, video_source=url_or_file, until_stage="03_visual_sample")

    dest = import_workspace(tmp_run, creator=creator_name, title=title_name, vault_dir=vault_dir)
    shutil.rmtree(tmp_run, ignore_errors=True)
    return dest

def render_table(rows: list[dict], columns: list[str] | None = None, headers: list[str] | None = None) -> str:
    if not rows:
        return "*(no records)*\n"
    if columns is None:
        columns = list(rows[0].keys())
    if headers is None:
        headers = [col.replace("_", " ").title() for col in columns]

    col_widths = [len(h) for h in headers]
    for r in rows:
        for idx, col in enumerate(columns):
            val_str = str(r.get(col, "")).replace("\n", " ").strip()
            if len(val_str) > col_widths[idx]:
                col_widths[idx] = len(val_str)

    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    row_lines = []
    for r in rows:
        row_str = "| " + " | ".join(str(r.get(col, "")).replace("\n", " ").strip().ljust(col_widths[i]) for i, col in enumerate(columns)) + " |"
        row_lines.append(row_str)
    return "\n".join([header_line, sep_line] + row_lines) + "\n"


def list_vault_videos(vault_dir: Path, creator_filter: str | None = None, limit: int = 0) -> list[dict]:
    items = []
    if not vault_dir.is_dir():
        return items
    for creator_dir in sorted(vault_dir.iterdir()):
        if not creator_dir.is_dir() or creator_dir.name.startswith("."):
            continue
        if creator_filter and creator_dir.name.lower() != creator_filter.lower():
            continue
        for entry_dir in sorted(creator_dir.iterdir(), reverse=True):
            if not entry_dir.is_dir():
                continue
            date_str = entry_dir.name[:10]
            title_slug = entry_dir.name[11:]
            notes_file = entry_dir / "notes.md"
            transcript_file = entry_dir / "transcript.md"
            visuals_dir = entry_dir / "visuals"
            num_visuals = len(list(visuals_dir.glob("*.jpg"))) if visuals_dir.is_dir() else 0
            items.append({
                "date": date_str,
                "creator": creator_dir.name,
                "title": title_slug,
                "has_notes": "yes" if notes_file.is_file() else "no",
                "has_transcript": "yes" if transcript_file.is_file() else "no",
                "visuals": num_visuals,
                "path": str(notes_file if notes_file.is_file() else entry_dir)
            })
    if limit and limit > 0:
        items = items[:limit]
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine videos and archive them into the Creator Video Vault.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Mine a video URL or local file into the vault")
    p_add.add_argument("url", help="URL or path to video")
    p_add.add_argument("--creator", help="Creator name / handle")
    p_add.add_argument("--title", help="Video title or slug")
    p_add.add_argument("--vault-dir", default=str(DEFAULT_VAULT_DIR), help="Path to vault root")

    p_import = sub.add_parser("import", help="Import an existing videomine ICM workspace into the vault")
    p_import.add_argument("workspace", help="Path to videomine workspace")
    p_import.add_argument("--creator", required=True, help="Creator name")
    p_import.add_argument("--title", required=True, help="Video title")
    p_import.add_argument("--vault-dir", default=str(DEFAULT_VAULT_DIR), help="Path to vault root")

    p_list = sub.add_parser("list", help="List vaulted videos in a high-density table")
    p_list.add_argument("--creator", help="Filter by creator name")
    p_list.add_argument("--table", "-t", action="store_true", default=True, help="Render as Markdown table")
    p_list.add_argument("--limit", "-n", type=int, default=0, help="Cap number of rows")
    p_list.add_argument("--json", action="store_true", help="Render as JSON")
    p_list.add_argument("--vault-dir", default=str(DEFAULT_VAULT_DIR), help="Path to vault root")

    p_reindex = sub.add_parser("reindex", help="Rebuild vault INDEX.md")
    p_reindex.add_argument("--vault-dir", default=str(DEFAULT_VAULT_DIR), help="Path to vault root")

    args = parser.parse_args()
    v_dir = Path(args.vault_dir)
    v_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "add":
        dest = mine_url(args.url, creator=args.creator, title=args.title, vault_dir=v_dir)
        print(f"✅ Successfully mined and vaulted video to: {dest}")
        return 0
    elif args.cmd == "import":
        dest = import_workspace(Path(args.workspace), creator=args.creator, title=args.title, vault_dir=v_dir)
        print(f"✅ Successfully imported workspace to: {dest}")
        return 0
    elif args.cmd == "list":
        rows = list_vault_videos(v_dir, creator_filter=args.creator, limit=args.limit)
        if args.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            cols = ["date", "creator", "title", "has_notes", "visuals"]
            print(f"### Creator Vault: {v_dir}\n")
            print(render_table(rows, cols))
        return 0
    elif args.cmd == "reindex":
        update_vault_index(v_dir)
        print(f"✅ Updated vault index: {v_dir / 'INDEX.md'}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
