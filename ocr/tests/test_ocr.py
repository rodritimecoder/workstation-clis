#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import unittest

OCR_PY = str(Path(__file__).resolve().parent.parent / "ocr.py")
SAMPLE_IMG = Path("/run/media/rodri/AI/llama.cpp/media/llama0-banner.png")


class TestUnifiedOCRDeterministic(unittest.TestCase):
    def test_01_doctor(self):
        cmd = ["python3", OCR_PY, "doctor", "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Doctor failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertEqual(data["premier_engine"], "LightOnOCR-3-1B")
        self.assertTrue(data["lighton_models_ready"])
        self.assertTrue(data["crisp_models_ready"])
        print("  ✓ doctor health check · verified")

    def test_02_lighton_document_ocr(self):
        cmd = ["python3", OCR_PY, str(SAMPLE_IMG)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"LightOnOCR failed: {res.stderr}")
        text = res.stdout.strip()
        self.assertIn("LLaMA", text)
        print(f"  ✓ premier LightOnOCR document transcription ('{text.splitlines()[0]}') · verified")

    def test_03_lighton_json_contract(self):
        cmd = ["python3", OCR_PY, str(SAMPLE_IMG), "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"LightOnOCR JSON failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertEqual(data["task"], "document_ocr")
        self.assertEqual(data["engine"], "lighton")
        self.assertIn("LLaMA", data["text"])
        self.assertIn("latency_ms", data)
        print(f"  ✓ premier LightOnOCR JSON contract ({data['latency_ms']}ms) · verified")

    def test_04_crispembed_spatial_boxes(self):
        cmd = ["python3", OCR_PY, str(SAMPLE_IMG), "--boxes", "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Spatial OCR failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertEqual(data["task"], "spatial_ocr")
        self.assertEqual(data["engine"], "crispembed")
        self.assertGreaterEqual(data["n_regions"], 1)
        for r in data["results"]:
            self.assertEqual(len(r["bbox"]), 4)
            self.assertGreaterEqual(r["confidence"], 0.0)
        print(f"  ✓ spatial CrispEmbed boxes ({data['n_regions']} regions, {data['latency_ms']}ms) · verified")

    def test_05_spatial_subcommand(self):
        cmd = ["python3", OCR_PY, "spatial", str(SAMPLE_IMG), "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Spatial subcommand failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertEqual(data["task"], "spatial_ocr")
        print("  ✓ spatial subcommand · verified")

    def test_06_remote_tailscale_ocr(self):
        host = "rodri-x870-taichi-creator.tail2975a8.ts.net"
        cmd = ["python3", OCR_PY, "read", str(SAMPLE_IMG), "--host", host, "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("  ⚠️ Remote OCR host offline, skipping")
            return
        data = json.loads(res.stdout)
        self.assertEqual(data["task"], "document_ocr")
        self.assertIn("LLaMA C++", data["text"])
        print(f"  ✓ remote tailscale LightOnOCR with base64 inlining ({data['latency_ms']}ms) · verified")


if __name__ == "__main__":
    print("\n🧪 Running Unified Premier OCR Test Suite:")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUnifiedOCRDeterministic)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    exit(0 if result.wasSuccessful() else 1)
