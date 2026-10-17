#!/usr/bin/env python3
import json
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple, Union


class JevEngine:
    def __init__(self, host: str = "127.0.0.1", port: int = 8083, timeout: float = 1.5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.endpoint = f"http://{self.host}:{self.port}/decide"

    def is_online(self) -> bool:
        try:
            req = urllib.request.Request(f"http://{self.host}:{self.port}/health")
            with urllib.request.urlopen(req, timeout=0.2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def decide_bool(self, context: str, question: str) -> Dict[str, Any]:
        payload = {
            "primitive": "bool",
            "context": context.strip(),
            "question": question.strip(),
        }
        res = self._call_service(payload)
        if res is not None:
            return res

        # Deterministic heuristic fallback when local SLM server is offline
        clean_ctx = context.lower()
        clean_q = question.lower()
        
        # Conflict / superseding heuristics
        if "supersede" in clean_q or "conflict" in clean_q:
            # Check for temporal contradiction
            has_conflict = any(neg in clean_ctx for neg in ["deprecated", "obsolete", "replaced", "instead of", "cancelled", "migrated"])
            p_true = 0.92 if has_conflict else 0.15
        else:
            p_true = 0.50

        return {
            "primitive": "bool",
            "decision": p_true >= 0.5,
            "confidence": round(p_true if p_true >= 0.5 else 1.0 - p_true, 4),
            "probabilities": {"true": round(p_true, 4), "false": round(1.0 - p_true, 4)},
            "source": "heuristic_fallback",
        }

    def decide_choice(self, context: str, question: str, options: List[str]) -> Dict[str, Any]:
        if not options:
            raise ValueError("Choice primitive requires at least one option")
        payload = {
            "primitive": "choice",
            "context": context.strip(),
            "question": question.strip(),
            "options": options,
        }
        res = self._call_service(payload)
        if res is not None:
            return res

        # Semantic overlap heuristic fallback
        clean_ctx = set(re.findall(r"[a-zA-Z0-9]+", context.lower()))
        scores = {}
        for opt in options:
            words = set(re.findall(r"[a-zA-Z0-9]+", opt.lower()))
            overlap = sum(1 for w in words if w in clean_ctx)
            scores[opt] = overlap + 0.01

        total = sum(scores.values())
        probs = {k: round(v / total, 4) for k, v in scores.items()}
        best_opt = max(probs.items(), key=lambda x: x[1])

        return {
            "primitive": "choice",
            "selection": best_opt[0],
            "confidence": best_opt[1],
            "probabilities": probs,
            "source": "heuristic_fallback",
        }

    def decide_score(self, context: str, criteria: str) -> Dict[str, Any]:
        payload = {
            "primitive": "score",
            "context": context.strip(),
            "criteria": criteria.strip(),
        }
        res = self._call_service(payload)
        if res is not None:
            return res

        # Normalized density heuristic fallback ignoring common stop words
        stop_words = {"and", "or", "the", "a", "an", "for", "with", "in", "to", "of"}
        num_map = {"0": "zero", "1": "one", "2": "two"}
        clean_ctx = set(re.findall(r"[a-zA-Z0-9]+", context.lower()))
        clean_crit = [w for w in re.findall(r"[a-zA-Z0-9]+", criteria.lower()) if w not in stop_words]
        
        match_count = 0
        for w in clean_crit:
            if w in clean_ctx or num_map.get(w) in clean_ctx:
                match_count += 1
            elif any(w.startswith(cw[:4]) or cw.startswith(w[:4]) for cw in clean_ctx if len(cw) >= 4 and len(w) >= 4):
                match_count += 1

        score = min(1.0, max(0.0, match_count / max(1, len(clean_crit))))

        return {
            "primitive": "score",
            "score": round(score, 4),
            "source": "heuristic_fallback",
        }

    def clean_context_claims(self, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Sort claims chronologically by timestamp
        sorted_claims = sorted(claims, key=lambda c: c.get("timestamp", ""))
        active_claims = []
        superseded_pairs = []

        for i in range(len(sorted_claims)):
            claim_b = sorted_claims[i]
            is_superseded = False
            for j in range(i + 1, len(sorted_claims)):
                claim_newer = sorted_claims[j]
                ctx = f"Older claim ({claim_b.get('timestamp')}): {claim_b.get('text')}\nNewer claim ({claim_newer.get('timestamp')}): {claim_newer.get('text')}"
                q = "Does the newer claim supersede, negate, or obsolete the older claim?"
                res = self.decide_bool(ctx, q)
                if res["decision"] and res["confidence"] > 0.70:
                    is_superseded = True
                    superseded_pairs.append({
                        "superseded": claim_b,
                        "superseded_by": claim_newer,
                        "confidence": res["confidence"]
                    })
                    break
            if not is_superseded:
                active_claims.append(claim_b)

        return {
            "total_input_claims": len(claims),
            "active_claims_retained": len(active_claims),
            "superseded_count": len(superseded_pairs),
            "active": active_claims,
            "superseded": superseded_pairs,
        }

    def evaluate_uat_target(self, dom_elements: List[Dict[str, str]], user_intent: str) -> Dict[str, Any]:
        options = [f"{elem.get('id', 'unknown')}: {elem.get('text', '')}" for elem in dom_elements]
        q = f"Which UI element should be clicked to satisfy user intent: '{user_intent}'?"
        choice = self.decide_choice(user_intent, q, options)
        selected_str = choice["selection"]
        selected_id = selected_str.split(":", 1)[0].strip()
        matched_elem = next((e for e in dom_elements if e.get("id") == selected_id), None)
        return {
            "user_intent": user_intent,
            "selected_id": selected_id,
            "element": matched_elem,
            "confidence": choice["confidence"],
        }

    def _call_service(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            req = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    data["source"] = "local_jev_server"
                    return data
        except Exception:
            pass
        return None
