#!/usr/bin/env python3
"""
align_pdf_transcript.py - Marry subject PDF lecture/tutorial markdown with Zoom video transcript.

Finds key lecture topics, question sections (e.g. Exercise 9.1, 9.2...), formulas, and definitions
in the course PDF markdown, links each topic to the exact video timestamp from the transcript,
and generates:
1. An annotated Markdown document with clickable video timestamps.
2. A ready-to-render Cornell Notes JSON for active-recall study (`cornell-notes` skill).
"""

import argparse
import json
import os
import re
from typing import List, Dict, Any


def parse_transcript(transcript_path: str) -> List[Dict[str, str]]:
    cues = []
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Match: - `[00:03:20]` **Speaker**: text
            if line.startswith("- `["):
                parts = line.split("`", 2)
                if len(parts) >= 3:
                    time_str = parts[1].strip("[]")
                    rest = parts[2].lstrip(" *:")
                    speaker = "Speaker"
                    text = rest
                    if "**:" in parts[2]:
                        sub = parts[2].split("**:", 1)
                        speaker = sub[0].strip(" *")
                        text = sub[1].strip()
                    cues.append({
                        "time": time_str,
                        "speaker": speaker,
                        "text": text
                    })
    return cues


def find_timestamp_for_keywords(cues: List[Dict[str, str]], keywords: List[str], start_time: str = "00:00:00") -> str:
    """Find the first transcript timestamp where any keyword appears after start_time."""
    for cue in cues:
        if cue["time"] >= start_time:
            text_lower = cue["text"].lower()
            if any(k.lower() in text_lower for k in keywords):
                return cue["time"]
    return start_time


def generate_aligned_notes(pdf_md_path: str, transcript_path: str, out_md_path: str, out_json_path: str, title: str):
    cues = parse_transcript(transcript_path)
    print(f"[*] Parsed {len(cues)} transcript cues from {transcript_path}")

    with open(pdf_md_path, "r", encoding="utf-8") as f:
        pdf_md = f.read()

    # Split PDF md into logical topic blocks / exercises
    # Matches markdown headers (#, ##, ###) or Exercise / Section headers
    blocks = re.split(r'\n(?=#{1,3}\s+|Exercise\s+\d+|Topic\s+\d+|[A-Z][a-zA-Z\s]{4,30}:)', pdf_md)
    blocks = [b.strip() for b in blocks if len(b.strip()) > 30]

    aligned_sections = []
    current_time = "00:00:00"

    for idx, block in enumerate(blocks):
        lines = block.splitlines()
        header = lines[0].strip("# :").strip()
        
        # Determine search keywords from header
        keywords = [header]
        words = [w for w in re.split(r'\W+', header) if len(w) > 3]
        if words:
            keywords.extend(words)

        matched_time = find_timestamp_for_keywords(cues, keywords, start_time=current_time)
        if matched_time != current_time:
            current_time = matched_time

        # Extract cues & explanations
        content_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else block
        
        # Formulate active recall cue
        cue_prompt = f"What is the key principle or formula in {header}?"
        if "exercise" in header.lower():
            cue_prompt = f"How to solve {header} and apply its resonance/filter formulas?"
        elif "formula" in header.lower() or "factor" in header.lower():
            cue_prompt = f"Define and compare {header}"

        aligned_sections.append({
            "heading": f"{header} [Timestamp: {current_time}]",
            "timestamp": current_time,
            "entries": [
                {
                    "cue": cue_prompt,
                    "notes": f"**Video Walkthrough Timestamp**: `[{current_time}]`\n\n{content_text}"
                }
            ],
            "summary": f"Covered at [{current_time}] in recording: Explains core derivation and application of {header}."
        })

    # Save Cornell JSON
    cornell_data = {
        "title": title,
        "source": pdf_md_path,
        "sections": aligned_sections
    }
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(cornell_data, f, indent=2)
    print(f"[+] Saved aligned Cornell Notes JSON: {out_json_path}")

    # Save Annotated Markdown
    with open(out_md_path, "w", encoding="utf-8") as f:
        f.write(f"# {title} (Timestamped Study Guide)\n\n")
        f.write("> **Source**: Marrying course PDF slides/notes directly with Zoom lecture recording timestamps.\n\n")
        for sec in aligned_sections:
            f.write(f"## {sec['heading']}\n\n")
            for ent in sec["entries"]:
                f.write(f"{ent['notes']}\n\n")
    print(f"[+] Saved aligned Markdown notes: {out_md_path}")


def main():
    parser = argparse.ArgumentParser(description="Marry course PDF slides/questions with Zoom lecture transcripts.")
    parser.add_argument("--pdf-md", required=True, help="Path to markdown converted from course PDF")
    parser.add_argument("--transcript", required=True, help="Path to Zoom transcript markdown (_transcript.md)")
    parser.add_argument("--out-md", required=True, help="Path for generated timestamped markdown guide")
    parser.add_argument("--out-json", required=True, help="Path for generated Cornell Notes JSON")
    parser.add_argument("--title", default="Timestamped Course Notes", help="Title of document")

    args = parser.parse_args()
    generate_aligned_notes(args.pdf_md, args.transcript, args.out_md, args.out_json, args.title)


if __name__ == "__main__":
    main()
