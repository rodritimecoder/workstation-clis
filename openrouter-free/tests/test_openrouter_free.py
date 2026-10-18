import json
import subprocess
import unittest
from pathlib import Path


class TestOpenRouterFree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli = "/run/media/rodri/AI/skills/openrouter-free/scripts/or_agent.py"

    def test_01_doctor_json_contract(self):
        res = subprocess.run(
            ["python3", self.cli, "doctor", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Doctor check failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertIn("status", data)
        self.assertIn("credentials", data)
        self.assertIn("free_tier_telemetry", data)
        self.assertIn("local_homelab_fallbacks", data)

        creds = data["credentials"]["openrouter_api_key"]
        self.assertTrue(creds["configured"])
        self.assertTrue(creds["valid"])

        telemetry = data["free_tier_telemetry"]
        self.assertIsNotNone(telemetry["daily_requests_remaining"])
        self.assertGreater(telemetry["daily_requests_limit"], 0)

    def test_02_decide_response_projection(self):
        res = subprocess.run(
            [
                "python3",
                self.cli,
                "decide",
                "--query",
                "Is 100 greater than 10?",
                "--options",
                "yes",
                "no",
                "--project",
                "verdict,confidence",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
        self.assertEqual(data.get("verdict"), "yes")
        self.assertIn("confidence", data)
        self.assertNotIn("probabilities", data)
        self.assertNotIn("raw", data)

    def test_03_decide_jq_projection(self):
        res = subprocess.run(
            [
                "python3",
                self.cli,
                "decide",
                "--query",
                "Is ice cold?",
                "--options",
                "yes",
                "no",
                "--jq",
                ".verdict",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(res.stdout.strip().strip('"'), "yes")

    def test_04_invalid_mode_exit_code(self):
        res = subprocess.run(
            ["python3", self.cli, "nonexistent_mode"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
