#!/usr/bin/env python3
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple, Union


def _drive_root() -> Path:
    """The AI volume root: $AI_ROOT, else the nearest ancestor holding models/.

    Launchers, weights and the CrispEmbed build all live under it, so resolving
    from here beats pinning the one mount point this was written for.
    """
    env = os.environ.get("AI_ROOT")
    if env:
        return Path(env).expanduser()
    for parent in Path(__file__).resolve().parents:
        if (parent / "models").is_dir():
            return parent
    return Path("/run/media/rodri/AI")


AI_DIR = Path(os.environ.get("OCR_AI_DIR", _drive_root()))
LIGHTON_LAUNCHER = AI_DIR / "sh" / "lighton-ocr.sh"
LIGHTON_MODEL_DIR = AI_DIR / "models" / "prithivMLmods" / "LightOnOCR-3-0.8B-GGUF"

CRISP_DIR = AI_DIR / "CrispEmbed"
CRISP_LAUNCHER = AI_DIR / "sh" / "crispembed-ocr.sh"
CRISP_VULKAN_DIRECT = CRISP_DIR / "build-vulkan" / "test-ppocrv6-direct"
CRISP_CPU_DIRECT = CRISP_DIR / "build-cpu" / "test-ppocrv6-direct"
CRISP_MODELS_DIR = AI_DIR / "models" / "cstr"
CRISP_DET = CRISP_MODELS_DIR / "PP-OCRv6-small-det-GGUF" / "PP-OCRv6_small_det-f16.gguf"
CRISP_REC = CRISP_MODELS_DIR / "PP-OCRv6_small_rec-GGUF" / "PP-OCRv6_small_rec-q8-head.gguf"

OXR_MODEL = CRISP_MODELS_DIR / "OXR-1.0-GGUF" / "oxr-1.0-f16.gguf"
OXR_LAYOUT = CRISP_MODELS_DIR / "OXR-1.0-DFINE-layout-GGUF" / "oxr-1.0-dfine-layout-f32.gguf"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


def clean_transcript(text: str) -> str:
    cleaned = re.sub(r"\n\nNote:.*$", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"\n\nExplanation:.*$", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


import ssl

class OCREngine:
    def __init__(
        self,
        lighton_port: int = 8085,
        crisp_port: int = 8084,
        host: Optional[str] = None,
        timeout: float = 60.0
    ):
        env_host = os.environ.get("OCR_HOST")
        self.host = host or env_host or "127.0.0.1"
        self.lighton_port = lighton_port
        self.crisp_port = crisp_port
        self.timeout = timeout
        
        self.is_remote = self.host not in ("127.0.0.1", "localhost")
        self.scheme = "https" if (".ts.net" in self.host or os.environ.get("OCR_SCHEME") == "https") else "http"
        
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

        self.lighton_endpoint = f"{self.scheme}://{self.host}:{self.lighton_port}/v1/chat/completions"
        self.lighton_health = f"{self.scheme}://{self.host}:{self.lighton_port}/health"
        self.crisp_endpoint = f"{self.scheme}://{self.host}:{self.crisp_port}/ocr/pipeline"
        self.crisp_health = f"{self.scheme}://{self.host}:{self.crisp_port}/health"

    def is_lighton_online(self) -> bool:
        try:
            req = urllib.request.Request(self.lighton_health)
            ctx = self.ssl_ctx if self.scheme == "https" else None
            with urllib.request.urlopen(req, timeout=0.8, context=ctx) as resp:
                return resp.status == 200
        except Exception:
            return False

    def is_crisp_online(self) -> bool:
        try:
            req = urllib.request.Request(self.crisp_health)
            ctx = self.ssl_ctx if self.scheme == "https" else None
            with urllib.request.urlopen(req, timeout=0.8, context=ctx) as resp:
                return resp.status == 200
        except Exception:
            return False

    def ensure_lighton(self, timeout: float = 12.0) -> bool:
        if self.is_lighton_online():
            return True
        if not LIGHTON_LAUNCHER.is_file():
            return False
        subprocess.Popen([str(LIGHTON_LAUNCHER)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_lighton_online():
                return True
            time.sleep(0.5)
        return False

    def ocr_image_lighton(self, img_bytes: bytes, prompt: Optional[str] = None) -> Tuple[str, float]:
        if not self.is_lighton_online():
            started = self.ensure_lighton()
            if not started:
                raise RuntimeError(f"LightOnOCR server not reachable on port {self.lighton_port} and auto-start failed.")

        b64 = base64.b64encode(img_bytes).decode("ascii")
        user_prompt = prompt or "Transcribe all visible text in Markdown. Output only the verbatim text."
        payload = {
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }],
            "max_tokens": 2048,
            "temperature": 0.0
        }

        t0 = time.time()
        req = urllib.request.Request(
            self.lighton_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        ctx = self.ssl_ctx if self.scheme == "https" else None
        with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        msg = data["choices"][0]["message"]
        raw_content = msg.get("content") or msg.get("reasoning_content") or ""
        cleaned = clean_transcript(raw_content)
        latency_ms = round((time.time() - t0) * 1000, 1)
        return cleaned, latency_ms

    def ocr_spatial(self, image_path: Path) -> Dict[str, Any]:
        p = Path(image_path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if self.is_crisp_online():
            payload = {"image": str(p)}
            try:
                req = urllib.request.Request(
                    self.crisp_endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                ctx = self.ssl_ctx if self.scheme == "https" else None
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                    results = []
                    for item in raw.get("results", []):
                        results.append({
                            "text": item.get("text", "").strip(),
                            "bbox": item.get("bbox", []),
                            "confidence": round(float(item.get("confidence", 0.0)), 4)
                        })
                    return {
                        "task": "spatial_ocr",
                        "engine": "crispembed",
                        "image": str(p),
                        "n_regions": len(results),
                        "mean_confidence": round(float(raw.get("mean_confidence", 0.0)), 4),
                        "results": results,
                        "markdown": raw.get("markdown", "").strip(),
                        "latency_ms": round(float(raw.get("ms", 0.0)), 1),
                        "source": "crispembed_server"
                    }
            except Exception:
                pass

        direct_bin = CRISP_VULKAN_DIRECT if CRISP_VULKAN_DIRECT.is_file() else CRISP_CPU_DIRECT
        if not direct_bin.is_file():
            raise FileNotFoundError(f"CrispEmbed direct binary not found at {direct_bin}")

        t0 = time.time()
        cmd = [str(direct_bin), str(CRISP_DET), str(CRISP_REC), str(p)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        latency_ms = round((time.time() - t0) * 1000, 1)

        pattern = re.compile(
            r"region=\d+\s+score=([0-9.]+)\s+quad=\(([0-9.]+),([0-9.]+)\)\(([0-9.]+),([0-9.]+)\)\(([0-9.]+),([0-9.]+)\)\(([0-9.]+),([0-9.]+)\).*?text=(.*)"
        )
        results = []
        confidences = []
        for line in res.stdout.splitlines():
            m = pattern.search(line.strip())
            if m:
                score = round(float(m.group(1)), 4)
                x1, y1 = float(m.group(2)), float(m.group(3))
                x2, y2 = float(m.group(4)), float(m.group(5))
                x3, y3 = float(m.group(6)), float(m.group(7))
                x4, y4 = float(m.group(8)), float(m.group(9))
                text = m.group(10).strip()
                bbox = [round(min(x1, x2, x3, x4), 2), round(min(y1, y2, y3, y4), 2),
                        round(max(x1, x2, x3, x4), 2), round(max(y1, y2, y3, y4), 2)]
                results.append({"text": text, "bbox": bbox, "confidence": score})
                confidences.append(score)

        mean_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        return {
            "task": "spatial_ocr",
            "engine": "crispembed",
            "image": str(p),
            "n_regions": len(results),
            "mean_confidence": mean_conf,
            "results": results,
            "markdown": "\n".join(r["text"] for r in results if r["text"]),
            "latency_ms": latency_ms,
            "source": "crispembed_direct"
        }

    def is_oxr_online(self) -> bool:
        if not self.is_crisp_online():
            return False
        probe = urllib.request.Request(
            f"{self.scheme}://{self.host}:{self.crisp_port}/oxr/document",
            data=json.dumps({"images": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        ctx = self.ssl_ctx if self.scheme == "https" else None
        try:
            urllib.request.urlopen(probe, timeout=1.5, context=ctx)
            return True
        except urllib.error.HTTPError as exc:
            return exc.code == 400
        except Exception:
            return False

    def ensure_oxr(self, timeout: float = 180.0) -> bool:
        if self.is_oxr_online():
            return True
        if not CRISP_LAUNCHER.is_file():
            return False
        env = dict(os.environ, ENGINE="oxr")
        subprocess.Popen(
            [str(CRISP_LAUNCHER)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_oxr_online():
                return True
            time.sleep(1.0)
        return False

    def _page_images(
        self, p: Path, pages: Optional[str], scratch: Path
    ) -> Tuple[List[Path], int]:
        if p.suffix.lower() in IMAGE_EXTENSIONS:
            return [p], 1

        import pymupdf

        doc = pymupdf.open(p)
        total = len(doc)
        indices = list(range(total))
        if pages:
            selected: List[int] = []
            for part in pages.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-", 1)
                    selected.extend(range(int(start) - 1, int(end)))
                elif part.isdigit():
                    selected.append(int(part) - 1)
            indices = [idx for idx in selected if 0 <= idx < total]

        mat = pymupdf.Matrix(2.0, 2.0)
        out: List[Path] = []
        for idx in indices:
            pix = doc[idx].get_pixmap(matrix=mat, alpha=False)
            target = scratch / f"page_{idx + 1:04d}.png"
            pix.save(str(target))
            out.append(target)
        doc.close()
        if not out:
            raise ValueError(f"No pages selected from {p.name}")
        return out, len(out)

    def _oxr_recognize(self, p: Path, max_new_tokens: int) -> Tuple[str, float]:
        binary = CRISP_DIR / "build-vulkan" / "crispembed"
        if not binary.is_file():
            binary = CRISP_DIR / "build-cpu" / "crispembed"
        if not binary.is_file() or not OXR_MODEL.is_file():
            raise FileNotFoundError(
                f"OXR binary/model missing: {binary} / {OXR_MODEL}"
            )
        base_env = dict(
            os.environ,
            CRISPEMBED_OXR="1",
            CRISPEMBED_ACCEPT_OXR_LICENSE="1",
        )
        cmd = [
            str(binary), "-m", str(OXR_MODEL), "--ocr", str(p),
            "--ocr-max-tokens", str(max_new_tokens), "-t", str(os.cpu_count() or 4),
        ]
        started = time.time()
        gpu_env = dict(base_env, CRISPEMBED_OXR_GPU="1", CRISPEMBED_OXR_GPU_FLASH="1")
        res = subprocess.run(cmd, capture_output=True, text=True, env=gpu_env, timeout=900)
        if res.returncode != 0:
            cpu_env = dict(base_env, CRISPEMBED_OXR_FORCE_CPU="1")
            res = subprocess.run(cmd, capture_output=True, text=True, env=cpu_env, timeout=1800)
        if res.returncode != 0:
            raise RuntimeError(f"OXR recognition failed: {res.stderr.strip()[-400:]}")
        return res.stdout.strip(), round((time.time() - started) * 1000, 1)

    def ocr_document_oxr(
        self,
        file_path: Path,
        pages: Optional[str] = None,
        max_new_tokens: int = 4096,
    ) -> Dict[str, Any]:
        p = Path(file_path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        if self.is_remote:
            raise RuntimeError(
                "OXR document parsing reads image paths server-side; it only works on the "
                "machine hosting the parser. Use --engine lighton for a remote host."
            )
        if not self.ensure_oxr():
            text, ms = self._oxr_recognize(p, max_new_tokens)
            return {
                "task": "document_ocr",
                "engine": "oxr-1.0",
                "file": str(p),
                "pages_count": 1,
                "pages": [{"page": 1, "text": text}],
                "text": text,
                "markdown": text,
                "latency_ms": ms,
                "source": "oxr_cli",
            }

        scratch = Path(tempfile.mkdtemp(prefix="ocr-oxr-"))
        try:
            images, count = self._page_images(p, pages, scratch)
            payload = {
                "images": [str(img) for img in images],
                "format": "upstream",
                "options": {"max_new_tokens": max_new_tokens},
            }
            req = urllib.request.Request(
                f"{self.scheme}://{self.host}:{self.crisp_port}/oxr/document",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            ctx = self.ssl_ctx if self.scheme == "https" else None
            started = time.time()
            try:
                with urllib.request.urlopen(req, timeout=900, context=ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raise RuntimeError(
                    f"OXR document route failed ({exc.code}): "
                    f"{exc.read().decode('utf-8', 'replace')[:400]}"
                )
            latency_ms = round((time.time() - started) * 1000, 1)

            outputs = data.get("outputs") or {}
            markdown = (outputs.get("markdown") or "").strip()
            structure = outputs.get("json") or {}
            meta = (data.get("metadata") or {}).get("crispembed") or {}
            page_texts = [
                {
                    "page": int(page.get("page_num", idx)) + 1,
                    "text": "\n\n".join(
                        str(block.get("content", ""))
                        for block in page.get("blocks", [])
                        if block.get("content")
                    ),
                }
                for idx, page in enumerate(structure.get("pages", []))
            ]
            if not markdown and count == 1 and p.suffix.lower() in IMAGE_EXTENSIONS:
                text, ms = self._oxr_recognize(p, max_new_tokens)
                return {
                    "task": "document_ocr",
                    "engine": "oxr-1.0",
                    "file": str(p),
                    "pages_count": 1,
                    "pages": [{"page": 1, "text": text}],
                    "text": text,
                    "markdown": text,
                    "latency_ms": ms,
                    "source": "oxr_cli",
                }
            return {
                "task": "document_ocr",
                "engine": "oxr-1.0",
                "file": str(p),
                "pages_count": count,
                "pages": page_texts,
                "text": markdown,
                "markdown": markdown,
                "structure": structure,
                "layout_source": meta.get("layout_source"),
                "latency_ms": latency_ms,
                "source": "oxr_native_document",
            }
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def ocr_document(
        self,
        file_path: Path,
        prompt: Optional[str] = None,
        pages: Optional[str] = None
    ) -> Dict[str, Any]:
        p = Path(file_path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = p.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            content, ms = self.ocr_image_lighton(p.read_bytes(), prompt=prompt)
            return {
                "task": "document_ocr",
                "engine": "lighton",
                "file": str(p),
                "pages_count": 1,
                "text": content,
                "markdown": content,
                "latency_ms": ms,
                "source": "lighton_1b_server"
            }

        if suffix == ".pdf":
            try:
                import pymupdf
            except ImportError:
                # ocr.py re-execs under the skill venv, so this only fires when
                # someone imports the engine directly from a bare interpreter.
                raise RuntimeError(
                    "PyMuPDF is required for PDF OCR. Run `ocr` (which re-execs "
                    "into the skill venv) or install pymupdf into this interpreter."
                )

            doc = pymupdf.open(p)
            total_pages = len(doc)
            page_indices = list(range(total_pages))
            if pages:
                selected = []
                for part in pages.split(","):
                    part = part.strip()
                    if "-" in part:
                        start, end = part.split("-", 1)
                        selected.extend(range(int(start) - 1, int(end)))
                    elif part.isdigit():
                        selected.append(int(part) - 1)
                page_indices = [idx for idx in selected if 0 <= idx < total_pages]

            page_results = []
            total_ms = 0.0
            mat = pymupdf.Matrix(2.0, 2.0)
            for idx in page_indices:
                page_pix = doc[idx].get_pixmap(matrix=mat, alpha=False)
                png_bytes = page_pix.tobytes("png")
                page_text, page_ms = self.ocr_image_lighton(png_bytes, prompt=prompt)
                total_ms += page_ms
                page_results.append({
                    "page": idx + 1,
                    "text": page_text
                })
            doc.close()

            combined_md = "\n\n".join(f"<!-- Page {pr['page']} -->\n{pr['text']}" for pr in page_results)
            return {
                "task": "document_ocr",
                "engine": "lighton",
                "file": str(p),
                "pages_count": len(page_indices),
                "pages": page_results,
                "markdown": combined_md,
                "text": combined_md,
                "latency_ms": round(total_ms, 1),
                "source": "lighton_1b_server"
            }

        raise ValueError(f"Unsupported file format: {suffix}")
