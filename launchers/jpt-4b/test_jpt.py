#!/usr/bin/env python3
"""Tests for JPT-4B typed decisions on stock llama.cpp.

Run against a live engine:
    python3 test_jpt.py                       # uses JPT_ENGINE_URL (default :8090)
    python3 test_jpt.py --api http://127.0.0.1:8080   # also exercises the HTTP facade

Checks the pieces the decision path depends on (chat template, one-token labels, label
logprobs, answer shapes, calibrated behaviour on rule-derived items) rather than the
model's prose.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jpt_llamacpp import (ANSWER, INSTRUCTION, JPTError, JPTLlamaCpp,  # noqa: E402
                          confidence, label_alphabet, options_of, softmax)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}", flush=True)


def approx(a, b, tol=0.02):
    return abs(a - b) <= tol


# --------------------------------------------------------------------------- offline
def test_units():
    print("offline pieces")
    check("labels are A..Z then AA..", label_alphabet(28)[:3] == ["A", "B", "C"] and label_alphabet(28)[26] == "AA")
    check("softmax normalises", approx(sum(softmax([-0.1, -2.0, -3.0], 1.036)), 1.0, 1e-9))
    check("confidence: point mass = 1", approx(confidence([1.0, 0.0]), 1.0))
    check("confidence: uniform = 0", approx(confidence([0.5, 0.5]), 0.0))
    check("noul keys are true/false", options_of({"type": "noul"})[0] == ["true", "false"])
    check("noul labels read Yes/No", options_of({"type": "noul"})[1][0].startswith("Yes:"))
    check("choice keeps key order", options_of({"type": "choice", "criteria": {"a": "x", "b": "y"}})[0] == ["a", "b"])
    check("choice renders 'key: desc'", options_of({"type": "choice", "criteria": {"a": "x", "b": None}})[1] == ["a: x", "b"])
    check("score keys are 0..n", options_of({"type": "score", "criteria": ["lo", "hi"]})[0] == ["0", "1"])
    try:
        options_of({"type": "choice", "criteria": {"only": 1}})
        check("choice needs >= 2 options", False)
    except JPTError:
        check("choice needs >= 2 options", True)
    try:
        options_of({"type": "bogus"})
        check("unknown type rejected", False)
    except JPTError:
        check("unknown type rejected", True)


# --------------------------------------------------------------------------- live
def test_engine(eng: JPTLlamaCpp):
    print("engine (llama-server)")
    check("engine healthy", eng.health())
    info = eng.info()
    check("model is the jpt-4b GGUF", "jpt-4b" in (info.get("model") or ""), info.get("model") or "?")

    prefix, rendered = eng.render("The build is on fire and nobody is answering.",
                                  {"q": {"type": "choice", "instructions": "Is this urgent?",
                                         "criteria": {"yes": "it is urgent", "no": "it is not"}}})
    check("prompt carries the llm2jev instruction", INSTRUCTION.split(".")[0] in prefix)
    check("one shared prefix across questions", prefix in rendered["q"][0])
    check("assistant prefill 'Answer:' at the end", rendered["q"][0].endswith(ANSWER))
    check("option lines are labelled A. B.", "\nA. yes: it is urgent\nB. no: it is not" in rendered["q"][0])

    ids = eng.label_ids(rendered["q"][0].rsplit("\nQuestion:", 1)[0], 8)
    check("8 labels are one token each after the ending", len(ids) == 8 and len(set(ids.values())) == 8)
    check("label detokenises to the label itself",
          all(eng.detokenize([i])["content"].strip() == lab for lab, i in list(ids.items())[:4]))

    lps = eng.label_logprobs(rendered["q"][0], list(ids.values()))
    check("engine returns label logprobs", all(i in lps for i in list(ids.values())[:3]))
    check("A/B logprobs are close for a real decision", approx(lps[ids["A"]], lps[ids["B"]], 4.0),
          f"A {lps[ids['A']]:.2f}  B {lps[ids['B']]:.2f}")


RULE_STATE = ("Refund policy: full refund within 30 days of purchase; 50% until day 60; none after.\n"
              "Order 1182 was bought on 3 March and returned on 20 April.")


def test_decisions(eng: JPTLlamaCpp):
    print("decisions (rules stated in the state, so the answer is checkable)")
    # the card's own example: bought 3 Mar, returned 20 Apr -> 48 days -> 50%
    t = time.perf_counter()
    refund_q = {"refund": {"type": "choice",
                           "instructions": "What refund does order 1182 get?",
                           "criteria": {"full": "Full refund", "half": "50% refund",
                                        "none": "No refund"}}}
    r = eng.decide(RULE_STATE, refund_q)
    a = r["refund"]
    print(f"    (choice) {a['choice']} {json.dumps({k: round(v,3) for k,v in a['probabilities'].items()})} "
          f"conf {a['confidence']:.2f}")
    check("date rule -> 50% refund", a["choice"] == "half", f"got {a['choice']}")
    check("choice answer carries the distribution + confidence",
          set(a["probabilities"]) == {"full", "half", "none"} and 0 <= a["confidence"] <= 1)
    check("probabilities sum to 1", approx(sum(a["probabilities"].values()), 1.0, 1e-6))

    r = eng.decide(RULE_STATE, {"late": {"type": "noul", "instructions": "Was the return made after day 30?"}})
    print(f"    (noul)  P(true) {r['late']['noul']:.3f}")
    check("48 days > 30 days -> P(true)", r["late"]["noul"] > 0.5, f"P(true) {r['late']['noul']:.3f}")

    r = eng.decide(RULE_STATE, {"soon": {"type": "noul", "instructions": "Was the return made within 30 days?"}})
    print(f"    (noul)  P(true) {r['soon']['noul']:.3f}  (expect < 0.5)")
    check("not within 30 days -> P(false)", r["soon"]["noul"] < 0.5, f"P(true) {r['soon']['noul']:.3f}")

    r = eng.decide(RULE_STATE, {"severity": {"type": "score", "instructions": "How severe is this case?",
                                             "criteria": ["trivial", "minor", "major", "severe"]}})
    s = r["severity"]
    print(f"    (score) {s['score']:.2f} {json.dumps({k: round(v,3) for k,v in s['probabilities'].items()})}")
    check("score answer is the expected level", 0 <= s["score"] <= 3 and s["probabilities"]["3"] > 0)
    check("score legend round-trips the levels", s["legend"] == {str(i): v for i, v in
                                                                 enumerate(["trivial", "minor", "major", "severe"])})

    print(f"    ({time.perf_counter()-t:.2f}s for 4 questions over one state)")
    # determinism: same question twice, temperature 0 engine-side
    r2 = eng.decide(RULE_STATE, refund_q)
    check("repeat run is stable (<0.02)",
          all(approx(v, r2["refund"]["probabilities"][k], 0.02) for k, v in a["probabilities"].items()))

    # many questions over one state share the prefix (engine-side cache)
    qs = {f"q{i}": {"type": "choice", "instructions": f"Pick a number: what is {i}+1?",
                    "criteria": {str(i + 1): "right", str(i + 2): "wrong"}} for i in range(6)}
    t = time.perf_counter()
    r = eng.decide(RULE_STATE, qs)
    dt = time.perf_counter() - t
    print(f"    (batch) 6 questions over one state in {dt:.2f}s")
    check("batch of 6 questions returns all", len([k for k in r if k != "_meta"]) == 6)
    check("batch is fast (<3 s)", dt < 3.0, f"{dt:.2f}s")


INTENTS = {
    "card_payment_declined": "My card was declined at the checkout even though the limit was fine.",
    "card_delivery_estimate": "When will my new card arrive? I need the tracking number.",
    "transfer_fee_refund": "You charged me a transfer fee, please refund it.",
    "cash_withdrawal": "I withdrew cash at an ATM and the receipt looks wrong.",
    "cash_withdrawal_charge": "Why is there an extra charge on my cash withdrawal?",
    "exchange_rate": "What exchange rate did you use for my transaction?",
    "top_up_by_phone": "My phone credit ran out; how do I top up by phone?",
    "balance_inquiry": "What is my current balance right now?",
    "verify_identity": "I need to verify my identity to finish signing up.",
    "cash_withdrawal_not_recognised": "I do not recognise this cash withdrawal on my statement.",
}
INTENT_OPTIONS = {k: None for k in INTENTS}


def test_intent_classification(eng: JPTLlamaCpp):
    """It is a classifier, not a chat model: one intent label per sentence, in one prefill each."""
    print("intent classification (Banking77-style, 10 clear-cut items)")
    hits = 0
    t = time.perf_counter()
    for gold, sentence in INTENTS.items():
        r = eng.decide_one(sentence, {"type": "choice",
                                      "instructions": "Which single intent does this customer message express?",
                                      "criteria": INTENT_OPTIONS})
        p = r["probabilities"][gold]
        ok = r["choice"] == gold
        hits += ok
        print(f"    {'ok ' if ok else 'MISS'} {gold:<32} pred {r['choice']:<32} p={p:.3f}")
    dt = time.perf_counter() - t
    print(f"    top-1 {hits}/{len(INTENTS)}  ({dt:.2f}s total, {dt/len(INTENTS)*1000:.0f} ms/item)")
    check("intent top-1 >= 8/10", hits >= 8, f"{hits}/10")


def test_api(api: str):
    print(f"HTTP facade ({api})")
    body = json.dumps({"state": RULE_STATE,
                       "questions": {"department": {"type": "choice",
                                                    "instructions": "Which team handles a refund?",
                                                    "criteria": {"billing": "Payments and refunds",
                                                                 "tech": "Software bugs"}},
                                     "urgent": {"type": "noul",
                                                "instructions": "Is this urgent?"}}}).encode()
    req = urllib.request.Request(api.rstrip("/") + "/v1/systemone", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)
    a = out["answers"]
    print(f"    (api)   {a['department']['choice']} {json.dumps({k: round(v,3) for k,v in a['department']['probabilities'].items()})}"
          f"  urgent P(true) {a['urgent']['noul']:.3f}")
    check("api returns System One shape", set(a) == {"department", "urgent"})
    check("api choice has probabilities + confidence", "probabilities" in a["department"] and "confidence" in a["department"])
    check("api noul has a boolean probability", 0 <= a["urgent"]["noul"] <= 1)
    check("api meta reports temperature", approx(out["meta"]["temperature"], 1.036))
    with urllib.request.urlopen(api.rstrip("/") + "/health", timeout=10) as r:
        h = json.load(r)
    check("api health ok", h.get("status") == "ok", json.dumps(h)[:120])
    # bad request is a 400 with a message, not a traceback
    try:
        req = urllib.request.Request(api.rstrip("/") + "/v1/systemone", b'{"questions":{}}',
                                     {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30)
        check("api rejects an empty question set", False)
    except urllib.error.HTTPError as e:
        check("api rejects an empty question set", e.code == 400 and b"error" in e.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=os.environ.get("JPT_ENGINE_URL", "http://127.0.0.1:8090"))
    ap.add_argument("--api", default=os.environ.get("JPT_API_URL", ""),
                    help="also test the HTTP facade, e.g. http://127.0.0.1:8080")
    a = ap.parse_args()

    test_units()
    eng = JPTLlamaCpp(a.engine)
    if not eng.health():
        print(f"\nno engine at {a.engine} — start it with start-jpt.sh, or rerun the live tests later")
        print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
        return 1
    test_engine(eng)
    test_decisions(eng)
    test_intent_classification(eng)
    if a.api:
        try:
            test_api(a.api)
        except Exception as e:  # noqa: BLE001
            check("api reachable", False, f"{type(e).__name__}: {e}")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("failed: " + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    import urllib.error  # noqa: E402  (used in test_api)
    sys.exit(main())