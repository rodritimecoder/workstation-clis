#!/usr/bin/env python3
import base64
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import ssl
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Union

ONEJEV_TEMPERATURE = 1.3051569717552742
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _logaddexp(a: float, b: float) -> float:
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))


def _concentration(probs: List[float]) -> float:
    k = len(probs)
    if k <= 1:
        return 1.0
    ent = -math.fsum(p * math.log(p) for p in probs if p > 0)
    return min(1.0, max(0.0, 1 - ent / math.log(k)))

class JevEngine:
    def __init__(self, host: Optional[str] = None, port: int = 8083, timeout: float = 5.0):
        env_host = os.environ.get("JEV_HOST") or os.environ.get("ONEJEV_HOST")
        self.host = host or env_host or "127.0.0.1"
        self.port = port
        self.timeout = timeout

        self.scheme = "https" if (".ts.net" in self.host or os.environ.get("JEV_SCHEME") == "https") else "http"
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

        self.endpoint = f"{self.scheme}://{self.host}:{self.port}/completion"
        self.systemone_url = f"{self.scheme}://{self.host}:{self.port}/v1/systemone"
        self.health_url = f"{self.scheme}://{self.host}:{self.port}/health"

        # auto     = native /v1/systemone first, fall back to the onejev letter readout
        # systemone/vllm = native only
        # legacy   = letter readout only (OneJev/Imajev-4B)
        self.backend = os.environ.get("JEV_BACKEND", "auto").lower()
        self._systemone_supported: Optional[bool] = None

    def is_online(self) -> bool:
        try:
            req = urllib.request.Request(self.health_url)
            ctx = self.ssl_ctx if self.scheme == "https" else None
            with urllib.request.urlopen(req, timeout=0.8, context=ctx) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _encode_image(self, image: Optional[str]) -> Optional[str]:
        if not image:
            return None
        p = Path(image)
        if p.exists() and p.is_file():
            return base64.b64encode(p.read_bytes()).decode("utf-8")
        if len(image) > 64 and ("/" in image or "+" in image or image.endswith("=")):
            return image
        return None

    def _data_url(self, image: Optional[str]) -> Optional[str]:
        raw = self._encode_image(image)
        if not raw:
            return None
        mime = "image/png"
        try:
            guess, _ = mimetypes.guess_type(str(image))
            if guess and guess.startswith("image/"):
                mime = guess
        except Exception:
            pass
        return f"data:{mime};base64,{raw}"

    def _call_systemone(
        self,
        state: str,
        question: str,
        options: Optional[List[str]],
        typ: str,
        image: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """vllm-d3-mini native /v1/systemone. Calibrated server-side."""
        if self.backend == "legacy" or self._systemone_supported is False:
            return None
        if not self.is_online():
            return None

        q: Dict[str, Any] = {"type": typ, "instructions": question}
        levels: Optional[List[str]] = None
        if typ == "choice":
            if not options:
                raise ValueError("Options list required for choice primitive")
            q["criteria"] = {str(o): None for o in options}
        elif typ == "score":
            levels = [str(o) for o in (options or ["0.0", "0.25", "0.5", "0.75", "1.0"])]
            q["criteria"] = levels

        payload: Dict[str, Any] = {"state": state, "questions": {"answer": q}}
        data_url = self._data_url(image)
        if data_url:
            payload["images"] = [data_url]

        try:
            req = urllib.request.Request(
                self.systemone_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            ctx = self.ssl_ctx if self.scheme == "https" else None
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (404, 400, 501):     # not a decision-model server
                self._systemone_supported = False
            return None
        except Exception:
            return None

        self._systemone_supported = True
        ans = (data.get("answers") or {}).get("answer")
        if not ans:
            return None
        source = "vllm_d3_mini_systemone"

        if typ == "noul":
            p_true = round(float(ans.get("noul", 0.0)), 4)
            p_false = round(1.0 - p_true, 4)
            return {
                "primitive": "bool",
                "decision": p_true >= 0.5,
                "confidence": round(abs(p_true - 0.5) * 2.0, 4),
                "probabilities": {"true": p_true, "false": p_false},
                "source": source,
            }

        if typ == "score":
            probs_raw = ans.get("probabilities") or {}
            dist: Dict[str, float] = {}
            scalar = 0.0
            for k, v in probs_raw.items():
                if not str(k).isdigit():
                    continue
                i = int(k)
                if levels and i < len(levels):
                    try:
                        scalar += float(levels[i]) * float(v)
                        dist[levels[i]] = round(float(v), 4)
                    except ValueError:
                        dist[str(k)] = round(float(v), 4)
            return {
                "primitive": "score",
                "score": round(min(1.0, max(0.0, scalar)), 4),
                "probabilities": dist or probs_raw,
                "source": source,
            }

        probs = {str(k): round(float(v), 4) for k, v in (ans.get("probabilities") or {}).items()}
        best = ans.get("choice") or (max(probs, key=probs.get) if probs else None)
        conf = ans.get("confidence")
        if conf is None:
            conf = _concentration(list(probs.values())) if probs else 0.0
        return {
            "primitive": "choice",
            "selection": best,
            "confidence": round(float(conf), 4),
            "probabilities": probs,
            "source": source,
        }

    def _call_onejev(
        self,
        state: str,
        question: str,
        options: Optional[List[str]],
        typ: str,
        image: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not self.is_online():
            return None

        image_b64 = self._encode_image(image)

        if typ == "noul":
            labels = {"A": "yes", "B": "no"}
        elif typ == "score":
            opts_list = options or ["0.0", "0.25", "0.5", "0.75", "1.0"]
            labels = {LETTERS[i]: str(opt) for i, opt in enumerate(opts_list[:len(LETTERS)])}
        else:
            if not options:
                raise ValueError("Options list required for choice primitive")
            labels = {LETTERS[i]: str(opt) for i, opt in enumerate(options[:len(LETTERS)])}

        lines = [f"Task: {question}", f"State: {state}"]
        for lt, lb in labels.items():
            lines.append(f"{lt}. {lb}")
        lines.append("Answer:")
        body = "\n".join(lines)

        img_prefix = "<image>\n" if image_b64 else ""
        prompt = f"{img_prefix}<|im_start|>user\n{body}<|im_end|>\n<|im_start|>assistant\nAnswer:"

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "max_tokens": 1,
            "temperature": 0.0,
            "n_probs": 20
        }
        if image_b64:
            payload["image_data"] = [{"data": image_b64, "id": 1}]

        try:
            req = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            ctx = self.ssl_ctx if self.scheme == "https" else None
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as resp:
                if resp.status != 200:
                    return None
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

        probs_raw = data.get("completion_probabilities") or []
        if not probs_raw:
            return None
        tops = probs_raw[0].get("top_logprobs") or []

        letter_lp: Dict[str, float] = {}
        for t in tops:
            tok = (t.get("token") or "").strip().rstrip(".,:)!").strip()
            if len(tok) == 1 and tok.upper() in LETTERS and tok.upper() in labels:
                lt = tok.upper()
                letter_lp[lt] = _logaddexp(letter_lp.get(lt, -math.inf), float(t["logprob"]))

        if not letter_lp:
            return None

        mx = max(letter_lp.values())
        exps = {lt: math.exp((lp - mx) / ONEJEV_TEMPERATURE) for lt, lp in letter_lp.items()}
        tot = sum(exps.values())
        if tot <= 0:
            return None
        probs = {labels[lt]: round(v / tot, 4) for lt, v in exps.items()}

        if typ == "noul":
            p_yes = probs.get("yes", 0.0)
            p_no = probs.get("no", 0.0)
            denom = p_yes + p_no
            if denom > 0:
                p_true = round(p_yes / denom, 4)
                p_false = round(p_no / denom, 4)
            else:
                p_true, p_false = 0.5, 0.5
            decision = p_true >= 0.5
            conf = round(abs(p_true - 0.5) * 2.0, 4)
            return {
                "primitive": "bool",
                "decision": decision,
                "confidence": conf,
                "probabilities": {"true": p_true, "false": p_false},
                "source": "onejev_1.5_4b_server",
            }

        if typ == "score":
            scalar = sum(float(k) * v for k, v in probs.items() if re.match(r"^-?\d+(\.\d+)?$", k))
            return {
                "primitive": "score",
                "score": round(min(1.0, max(0.0, scalar)), 4),
                "probabilities": probs,
                "source": "onejev_1.5_4b_server",
            }

        best = max(probs, key=probs.get)
        conf = round(_concentration(list(probs.values())), 4)
        return {
            "primitive": "choice",
            "selection": best,
            "confidence": conf,
            "probabilities": probs,
            "source": "onejev_1.5_4b_server",
        }

    def decide_bool(self, context: str, question: str, image: Optional[str] = None) -> Dict[str, Any]:
        res = self._call_systemone(context, question, None, "noul", image)
        if res is None:
            res = self._call_onejev(context, question, None, "noul", image)
        if res is not None:
            return res

        clean_ctx = context.lower()
        clean_q = question.lower()
        if "supersede" in clean_q or "conflict" in clean_q:
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

    def decide_choice(self, context: str, question: str, options: List[str], image: Optional[str] = None) -> Dict[str, Any]:
        if not options:
            raise ValueError("Choice primitive requires at least one option")
        res = self._call_systemone(context, question, options, "choice", image)
        if res is None:
            res = self._call_onejev(context, question, options, "choice", image)
        if res is not None:
            return res

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

    def decide_score(self, context: str, criteria: str, image: Optional[str] = None) -> Dict[str, Any]:
        levels = ["0.0", "0.25", "0.5", "0.75", "1.0"]
        res = self._call_systemone(context, criteria, levels, "score", image)
        if res is None:
            res = self._call_onejev(context, criteria, levels, "score", image)
        if res is not None:
            return res

        stop_words = {"and", "or", "the", "a", "an", "for", "with", "in", "to", "of"}
        clean_ctx = set(re.findall(r"[a-zA-Z0-9]+", context.lower()))
        clean_crit = [w for w in re.findall(r"[a-zA-Z0-9]+", criteria.lower()) if w not in stop_words]
        
        match_count = 0
        for w in clean_crit:
            if w in clean_ctx:
                match_count += 1
            elif any(w.startswith(cw[:4]) or cw.startswith(w[:4]) for cw in clean_ctx if len(cw) >= 4 and len(w) >= 4):
                match_count += 1

        score = min(1.0, max(0.0, match_count / max(1, len(clean_crit))))
        return {
            "primitive": "score",
            "score": round(score, 4),
            "source": "heuristic_fallback",
        }

    def decide_composite(
        self,
        context: str,
        question: str,
        options: List[str],
        criteria: Optional[str] = None,
        image: Optional[str] = None
    ) -> Dict[str, Any]:
        gate_res = self.decide_bool(context, question, image=image)
        choice_res = self.decide_choice(context, question, options, image=image)
        score_crit = criteria if criteria else f"Quality and confidence of {choice_res['selection']}"
        score_res = self.decide_score(context, score_crit, image=image)

        return {
            "primitive": "composite",
            "gate": gate_res["decision"],
            "gate_confidence": gate_res["confidence"],
            "action": choice_res["selection"],
            "choice_confidence": choice_res["confidence"],
            "quality_score": score_res["score"],
            "source": gate_res["source"],
        }

    def clean_context_claims(self, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
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
                if res["decision"] and res["confidence"] > 0.60:
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

    def evaluate_uat_target(self, dom_elements: List[Dict[str, str]], user_intent: str, image: Optional[str] = None) -> Dict[str, Any]:
        options = [f"{elem.get('id', 'unknown')}: {elem.get('text', '')}" for elem in dom_elements]
        q = f"Which UI element satisfies user intent: '{user_intent}'?"
        choice = self.decide_choice(user_intent, q, options, image=image)
        selected_str = choice["selection"]
        selected_id = selected_str.split(":", 1)[0].strip()
        matched_elem = next((e for e in dom_elements if e.get("id") == selected_id), None)
        return {
            "user_intent": user_intent,
            "selected_id": selected_id,
            "element": matched_elem,
            "confidence": choice["confidence"],
            "source": choice["source"],
        }
