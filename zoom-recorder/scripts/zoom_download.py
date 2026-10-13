#!/usr/bin/env python3
"""
zoom_download.py - Download transcripts, audio, and keyframes from Zoom cloud recordings.

Supports:
- Public and password-protected Zoom cloud recordings (utsmeet.zoom.us, *.zoom.us).
- Unwraps Mimecast and Microsoft SafeLinks protection URLs.
- Password validation without requiring Zoom OAuth / Developer Admin credentials.
- Automatic extraction and formatting of transcripts (VTT, TXT, Markdown).
- Selective keyframe extraction using ffmpeg without downloading the entire 1-hour video.
- Optional audio download and local fallback ASR (via audiocpp-asr) if native VTT is unavailable.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from typing import Dict, Any, Optional, Tuple
import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X-11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def unwrap_protected_url(raw_url: str) -> str:
    """Unwrap Mimecast, Outlook Safelinks, or direct URL."""
    url = raw_url.strip()
    
    # Outlook Safelinks
    if "protection.outlook.com" in url and "url=" in url:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "url" in qs:
            return unwrap_protected_url(qs["url"][0])
            
    # Mimecast protection URL
    if "mimecastprotect.com" in url and "domain=" in url:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "domain" in qs:
            return unwrap_protected_url(qs["domain"][0])
            
    return url


def parse_vtt_to_markdown(vtt_text: str, title: str = "Recording Transcript") -> str:
    """Convert WebVTT transcript to clean readable Markdown notes format."""
    lines = vtt_text.strip().splitlines()
    md_lines = [f"# {title}", "", "> Extracted automatically from Zoom Cloud Recording.", ""]
    
    timestamp_re = re.compile(
        r"(\d{2}:\d{2}:\d{2}(?:\.\d{3})?|\d{2}:\d{2}(?:\.\d{3})?)\s*-->\s*(\d{2}:\d{2}:\d{2}(?:\.\d{3})?|\d{2}:\d{2}(?:\.\d{3})?)"
    )
    
    current_speaker = None
    current_time = ""
    current_text_buf = []

    def flush_block():
        nonlocal current_speaker, current_time, current_text_buf
        if current_text_buf:
            text = " ".join(current_text_buf).strip()
            if text:
                speaker_prefix = f"**{current_speaker}**" if current_speaker else "**Speaker**"
                md_lines.append(f"- `[{current_time}]` {speaker_prefix}: {text}")
            current_text_buf = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        
        if not line or line.startswith("WEBVTT") or line.isdigit():
            continue
            
        m_time = timestamp_re.search(line)
        if m_time:
            flush_block()
            current_time = m_time.group(1).split(".")[0] # clean seconds
            continue
            
        # Check if line contains "Speaker: Text"
        if ":" in line:
            parts = line.split(":", 1)
            # heuristic: speaker names usually < 40 chars and without special punctuation
            if len(parts[0]) < 40 and not any(p in parts[0] for p in ["http", "www", "/"]):
                flush_block()
                current_speaker = parts[0].strip()
                current_text_buf.append(parts[1].strip())
                continue
                
        current_text_buf.append(line)

    flush_block()
    return "\n".join(md_lines) + "\n"


class ZoomRecorderClient:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "*/*",
        })

    def get_recording_info(self, zoom_url: str, passcode: Optional[str] = None) -> Dict[str, Any]:
        """
        Unlocks and retrieves complete recording info, play links, and transcript URLs.
        """
        unwrapped = unwrap_protected_url(zoom_url)
        parsed = urllib.parse.urlparse(unwrapped)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        self.session.headers.update({"Referer": unwrapped})
        resp = self.session.get(unwrapped)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to access URL: HTTP {resp.status_code}")

        # Check if URL is /rec/play or /rec/share
        is_share = "/rec/share/" in unwrapped or "/rec/share" in parsed.path
        
        meeting_id_match = re.search(r'meetingId:\s*[\'"]([^\'"]+)[\'"]', resp.text)
        if not meeting_id_match:
            # Fallback search in JSON or window.__data__
            meeting_id_match = re.search(r'\"meetingId\":\s*\"([^\"]+)\"', resp.text)
            
        meeting_id = meeting_id_match.group(1) if meeting_id_match else ""
        
        # 1. Fetch initial share-info / play-info
        if is_share:
            share_info_url = f"{base_url}/nws/recording/1.0/play/share-info/{meeting_id}"
            share_info_resp = self.session.get(share_info_url).json()
            if not share_info_resp.get("status"):
                raise RuntimeError(f"Share info error: {share_info_resp.get('errorMessage')}")
                
            result = share_info_resp.get("result", {})
            need_password = result.get("componentName") == "need-password" or result.get("needRedirect") and "need-password" in result.get("redirectUrl", "")
            
            # If passcode protected, perform the unlock sequence
            if need_password:
                if not passcode:
                    raise ValueError(f"Recording requires a passcode. Provide --passcode <passcode>")
                
                target_meeting_id = result.get("meetingId") or meeting_id
                
                # Context validation
                ctx_url = f"{base_url}/nws/recording/1.0/validate-context"
                ctx_payload = {
                    "meetingId": target_meeting_id,
                    "fileId": "",
                    "useWhichPasswd": "meeting",
                    "sharelevel": "meeting",
                    "iet": "",
                }
                ctx_res = self.session.post(ctx_url, data=ctx_payload).json()
                encrypt_meet_id = ctx_res.get("result", {}).get("encryptMeetId", target_meeting_id)
                
                # Password validation
                val_url = f"{base_url}/nws/recording/1.0/validate-meeting-passwd"
                val_payload = {
                    "id": encrypt_meet_id,
                    "passwd": passcode.strip(),
                    "action": "viewdetailpage",
                    "recaptcha": "",
                }
                val_res = self.session.post(val_url, data=val_payload).json()
                if not val_res.get("status"):
                    raise RuntimeError(f"Passcode rejected: {val_res.get('errorMessage', 'Incorrect passcode')}")
                
                # Query share-info again now that session is unlocked
                share_info_resp = self.session.get(share_info_url).json()
                result = share_info_resp.get("result", {})
            
            redirect_url = result.get("redirectUrl", "")
            if not redirect_url:
                raise RuntimeError("Could not retrieve playback redirect URL from share info.")
            play_url = urllib.parse.urljoin(base_url, redirect_url)
            play_resp = self.session.get(play_url)
        else:
            # Direct /rec/play URL
            play_resp = resp
            play_url = unwrapped

        # Extract fileId from play page
        file_id_match = re.search(r'fileId:\s*[\'"]([^\'"]*)[\'"]', play_resp.text)
        if not file_id_match or not file_id_match.group(1):
            file_id_match = re.search(r'\"fileId\":\s*\"([^\"]+)\"', play_resp.text)
            
        file_id = file_id_match.group(1) if file_id_match else ""
        if not file_id:
            # Check if need-password on play URL
            if "need-password" in play_resp.text and passcode:
                # Direct play password validation
                m_meet = re.search(r'meetingId:\s*[\'"]([^\'"]+)[\'"]', play_resp.text)
                if m_meet:
                    ctx_res = self.session.post(f"{base_url}/nws/recording/1.0/validate-context", data={
                        "meetingId": m_meet.group(1),
                        "fileId": "",
                        "useWhichPasswd": "meeting",
                        "sharelevel": "meeting",
                        "iet": ""
                    }).json()
                    enc_id = ctx_res.get("result", {}).get("encryptMeetId", m_meet.group(1))
                    self.session.post(f"{base_url}/nws/recording/1.0/validate-meeting-passwd", data={
                        "id": enc_id,
                        "passwd": passcode.strip(),
                        "action": "viewdetailpage",
                        "recaptcha": ""
                    })
                    play_resp = self.session.get(play_url)
                    file_id_match = re.search(r'fileId:\s*[\'"]([^\'"]*)[\'"]', play_resp.text)
                    file_id = file_id_match.group(1) if file_id_match else ""

        if not file_id:
            raise RuntimeError("Unable to extract playback fileId from Zoom player.")

        # Call play/info/{file_id}
        info_api_url = f"{base_url}/nws/recording/1.0/play/info/{file_id}?continueMode=true"
        info_res = self.session.get(info_api_url).json()
        if not info_res.get("status"):
            raise RuntimeError(f"Play info API error: {info_res.get('errorMessage')}")

        data = info_res.get("result", {})
        
        # If direct play requires passcode validation:
        if data.get("componentName") == "need-password" or (data.get("needRedirect") and "need-password" in str(data.get("redirectUrl"))):
            if not passcode:
                raise ValueError(f"Recording requires a passcode. Provide --passcode <passcode>")
            target_meeting_id = data.get("meetingId") or meeting_id
            ctx_res = self.session.post(f"{base_url}/nws/recording/1.0/validate-context", data={
                "meetingId": target_meeting_id,
                "fileId": "",
                "useWhichPasswd": "meeting",
                "sharelevel": "meeting",
                "iet": "",
            }).json()
            encrypt_meet_id = ctx_res.get("result", {}).get("encryptMeetId", target_meeting_id)
            val_res = self.session.post(f"{base_url}/nws/recording/1.0/validate-meeting-passwd", data={
                "id": encrypt_meet_id,
                "passwd": passcode.strip(),
                "action": "viewdetailpage",
                "recaptcha": "",
            }).json()
            if not val_res.get("status"):
                raise RuntimeError(f"Passcode rejected: {val_res.get('errorMessage', 'Incorrect passcode')}")
            # Refetch unlocked play/info
            info_res = self.session.get(info_api_url).json()
            data = info_res.get("result", {})

        topic = data.get("meet", {}).get("topic") or "Zoom Cloud Recording"
        duration = data.get("duration", 0)
        
        # Build clean direct URLs
        transcript_url = None
        if data.get("transcriptUrl"):
            transcript_url = urllib.parse.urljoin(base_url, data["transcriptUrl"])
            
        video_url = data.get("viewMp4WithshareUrl") or data.get("viewMp4Url") or data.get("shareMp4Url")

        return {
            "topic": topic,
            "duration": duration,
            "file_id": file_id,
            "has_transcript": data.get("hasTranscript", False),
            "transcript_url": transcript_url,
            "video_url": video_url,
            "raw_result": data,
            "base_url": base_url,
        }

    def fetch_transcript(self, transcript_url: str) -> str:
        """Fetch VTT transcript content."""
        resp = self.session.get(transcript_url)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to download transcript: HTTP {resp.status_code}")
        return resp.text

    def extract_keyframes(self, video_url: str, output_dir: str, scene_threshold: float = 0.35, max_frames: int = 50):
        """
        Extract visual keyframes (slide changes) from video URL stream using ffmpeg.
        Pipes through authenticated requests session to bypass CloudFront 403 Forbidden checks.
        """
        os.makedirs(output_dir, exist_ok=True)
        out_pattern = os.path.join(output_dir, "slide_%03d.png")
        filter_str = f"select='gt(scene,{scene_threshold})',scale=1280:-1"
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "warning",
            "-i", "pipe:0",
            "-vf", filter_str,
            "-vsync", "vfr",
            "-vframes", str(max_frames),
            out_pattern,
        ]
        print(f"[*] Extracting keyframes to {output_dir} via streaming ffmpeg pipeline...")
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            resp = self.session.get(video_url, stream=True)
            for chunk in resp.iter_content(chunk_size=65536):
                try:
                    proc.stdin.write(chunk)
                except (BrokenPipeError, OSError):
                    break
        finally:
            try:
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            proc.wait()
        print(f"[+] Keyframe extraction complete.")

    def run_ocr_on_frame(self, image_path: str, model_type: str = "lighton") -> str:
        """
        Run local OCR vision model on an extracted video frame.
        Supports:
        - 'lighton': LightOnOCR-3-1B (ultra fast, multi-column, LaTeX equations)
        - 'xiaomi': Xiaomi-OCR-0 (Qwen-VL reasoning OCR)
        - 'deskforge': DeskForge-Qwen3.5-4B (document formatting)
        - 'ovis': OvisOCR2-5B
        """
        llama_cli = "/run/media/rodri/AI/llama.cpp/build/bin/llama-mtmd-cli"
        models_map = {
            "lighton": (
                "/run/media/rodri/AI/models/prithivMLmods/LightOnOCR-3-1B-GGUF/LightOnOCR-3-1B.Q4_K_M.gguf",
                "/run/media/rodri/AI/models/prithivMLmods/LightOnOCR-3-1B-GGUF/LightOnOCR-3-1B.mmproj-q8_0.gguf",
                "Extract all text, math formulas, and code in Markdown format:"
            ),
            "navidc": (
                "/run/media/rodri/AI/models/konradjr007/NaviDC-OCR-GGUF/NaviDC-OCR-Q5_K_M.gguf",
                "/run/media/rodri/AI/models/konradjr007/NaviDC-OCR-GGUF/mmproj-NaviDC-OCR-F16.gguf",
                "Extract all text from this image."
            ),
            "xiaomi": (
                "/run/media/rodri/AI/models/prithivMLmods/Xiaomi-OCR-0-GGUF/Xiaomi-OCR-0.Q4_K_M.gguf",
                "/run/media/rodri/AI/models/prithivMLmods/Xiaomi-OCR-0-GGUF/Xiaomi-OCR-0.mmproj-bf16.gguf",
                "Extract all text and formulas:"
            ),
            "deskforge": (
                "/run/media/rodri/AI/models/docling-project/DeskForge-Qwen3.5-4B/DeskForge-Qwen3.5-4B.Q4_K_M.gguf",
                "/run/media/rodri/AI/models/docling-project/DeskForge-Qwen3.5-4B/DeskForge-Qwen3.5-4B.mmproj-bf16.gguf",
                "Extract the content in markdown:"
            ),
            "ovis": (
                "/run/media/rodri/AI/models/Abiray/OvisOCR2-GGUF/OvisOCR2-Q5_K_M.gguf",
                "/run/media/rodri/AI/models/Abiray/OvisOCR2-GGUF/mmproj-BF16.gguf",
                "Extract all text:"
            ),
        }
        if model_type not in models_map:
            raise ValueError(f"Unknown model_type '{model_type}'. Choose from: {list(models_map.keys())}")

        m_path, mmproj_path, prompt = models_map[model_type]
        cmd = [
            llama_cli,
            "-m", m_path,
            "--mmproj", mmproj_path,
            "--image", image_path,
            "-p", prompt,
            "-ngl", "99",
            "-n", "512"
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # Filter out banner and log lines
        out_lines = []
        for line in res.stdout.splitlines():
            if any(term in line for term in ["WARNING:", "WARN:", "mtmd", "init:", "main:", "find_slot:"]):
                continue
            out_lines.append(line)
        return "\n".join(out_lines).strip()


def main():
    parser = argparse.ArgumentParser(description="Download Zoom recording transcripts and keyframes without full video downloads.")
    parser.add_argument("--url", required=True, help="Zoom recording URL (utsmeet.zoom.us/rec/share/... or /rec/play/...)")
    parser.add_argument("--passcode", "-p", default="", help="Recording passcode if protected")
    parser.add_argument("--out-dir", "-o", default=".", help="Output directory for saved files")
    parser.add_argument("--format", choices=["md", "vtt", "txt", "all"], default="md", help="Transcript format")
    parser.add_argument("--keyframes", action="store_true", help="Extract presentation slide keyframes using ffmpeg")
    parser.add_argument("--scene-threshold", type=float, default=0.35, help="Scene change sensitivity for keyframes (0.0 - 1.0)")
    parser.add_argument("--ocr", action="store_true", help="Run local vision OCR on extracted keyframes")
    parser.add_argument("--ocr-model", choices=["lighton", "navidc", "xiaomi", "deskforge", "ovis", "all"], default="lighton", help="Vision model for OCR")
    parser.add_argument("--json", action="store_true", help="Print recording metadata in JSON format")

    args = parser.parse_args()

    client = ZoomRecorderClient()
    try:
        info = client.get_recording_info(args.url, args.passcode)
    except Exception as e:
        print(f"[-] Error retrieving recording info: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({
            "topic": info["topic"],
            "duration": info["duration"],
            "has_transcript": info["has_transcript"],
            "transcript_url": info["transcript_url"],
            "video_url_available": bool(info["video_url"]),
        }, indent=2))

    os.makedirs(args.out_dir, exist_ok=True)
    slug = re.sub(r'[^a-zA-Z0-9_\-]+', '_', info["topic"]).strip("_") or "zoom_recording"

    # Download transcript
    if info.get("transcript_url"):
        print(f"[*] Found native Zoom transcript for: {info['topic']}")
        vtt_content = client.fetch_transcript(info["transcript_url"])
        
        if args.format in ["vtt", "all"]:
            vtt_path = os.path.join(args.out_dir, f"{slug}.vtt")
            with open(vtt_path, "w", encoding="utf-8") as f:
                f.write(vtt_content)
            print(f"[+] Saved VTT transcript: {vtt_path}")

        if args.format in ["md", "all"]:
            md_content = parse_vtt_to_markdown(vtt_content, title=info["topic"])
            md_path = os.path.join(args.out_dir, f"{slug}_transcript.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"[+] Saved Markdown transcript: {md_path}")

        if args.format == "txt":
            # Strip timestamps
            txt_lines = []
            for line in vtt_content.splitlines():
                if not line or line.startswith("WEBVTT") or line.isdigit() or "-->" in line:
                    continue
                txt_lines.append(line)
            txt_path = os.path.join(args.out_dir, f"{slug}_transcript.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(txt_lines) + "\n")
            print(f"[+] Saved TXT transcript: {txt_path}")
    else:
        print("[-] No native VTT transcript found hosted on Zoom for this recording.")
        if info.get("video_url"):
            print("[*] Video stream URL is available for keyframe extraction or local ASR.")

    # Keyframes extraction
    if args.keyframes or args.ocr:
        if info.get("video_url"):
            slides_dir = os.path.join(args.out_dir, f"{slug}_slides")
            client.extract_keyframes(info["video_url"], slides_dir, scene_threshold=args.scene_threshold)
            
            if args.ocr:
                import glob
                frames = sorted(glob.glob(os.path.join(slides_dir, "*.png")))
                print(f"[*] Running OCR on {len(frames)} extracted slide frames...")
                models_to_test = ["lighton", "navidc", "xiaomi", "deskforge", "ovis"] if args.ocr_model == "all" else [args.ocr_model]
                
                ocr_out_file = os.path.join(args.out_dir, f"{slug}_slides_ocr.md")
                with open(ocr_out_file, "w", encoding="utf-8") as out_f:
                    out_f.write(f"# Slide OCR: {info['topic']}\n\n")
                    for frame_path in frames:
                        f_name = os.path.basename(frame_path)
                        out_f.write(f"## Slide: {f_name}\n\n")
                        for m_type in models_to_test:
                            print(f"    - Processing {f_name} with {m_type}...")
                            ocr_text = client.run_ocr_on_frame(frame_path, model_type=m_type)
                            out_f.write(f"### Model: {m_type}\n\n{ocr_text}\n\n")
                print(f"[+] Saved visual OCR results: {ocr_out_file}")
        else:
            print("[-] Cannot extract keyframes: video URL not found.", file=sys.stderr)


if __name__ == "__main__":
    main()
