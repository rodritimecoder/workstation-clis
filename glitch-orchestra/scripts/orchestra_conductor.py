#!/usr/bin/env python3
import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class OrchestraConductor:
    def __init__(self, workspace_dir: Path):
        self.workspace = Path(workspace_dir)
        self.orchestra_dir = self.workspace / ".orchestra"
        self.sessions_file = self.orchestra_dir / "sessions.json"
        self.orchestra_dir.mkdir(parents=True, exist_ok=True)

    def _read_sessions(self) -> Dict[str, Any]:
        if not self.sessions_file.exists():
            return {"active_sessions": [], "completed_sessions": []}
        return json.loads(self.sessions_file.read_text(encoding="utf-8"))

    def _write_sessions(self, data: Dict[str, Any]):
        self.sessions_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def register_child_session(self, session_id: str, task: str, terminal_tag: str = "term_01") -> Dict[str, Any]:
        data = self._read_sessions()
        session_entry = {
            "session_id": session_id,
            "task": task,
            "terminal_tag": terminal_tag,
            "status": "running",
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        data["active_sessions"].append(session_entry)
        self._write_sessions(data)
        return session_entry

    def mark_session_complete(self, session_id: str, summary: str = "Finished") -> Dict[str, Any]:
        data = self._read_sessions()
        matched = next((s for s in data["active_sessions"] if s["session_id"] == session_id), None)
        if not matched:
            raise ValueError(f"Session '{session_id}' not found in active sessions")

        data["active_sessions"].remove(matched)
        matched["status"] = "completed"
        matched["summary"] = summary
        matched["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data["completed_sessions"].append(matched)
        self._write_sessions(data)
        return matched

    def trigger_completion_alert(self, message: str = "All orchestra subagents have completed their tasks.") -> Dict[str, Any]:
        # Audible terminal bell and optional audio synthesis
        bell_emitted = False
        try:
            print("\a", end="", flush=True)
            bell_emitted = True
        except Exception:
            pass

        return {
            "alert_message": message,
            "bell_emitted": bell_emitted,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def status(self) -> Dict[str, Any]:
        data = self._read_sessions()
        return {
            "active_count": len(data["active_sessions"]),
            "completed_count": len(data["completed_sessions"]),
            "active_sessions": data["active_sessions"],
            "completed_sessions": data["completed_sessions"],
        }
