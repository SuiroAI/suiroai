"""Independent claim review against resolved evidence, never producer pass flags.

The parent supplies both review callbacks as trusted independent code. They must
not be loaded from a report or its artifacts. This module does not infer truth
from prose, keywords or an upstream finding. In particular, narrative review
must cover undeclared claims, list/name/exception fidelity, synthetic provenance,
capability and gap guidance, and truthful scoped terminal explanations.

``review_claim(item, evidence_bytes)`` receives one declared claim or final-report
finding and a tuple of bytes in its evidence-reference order.
``review_narrative(report, evidence_map)`` receives the whole report and a map
from (artifact_id, version, sha256, provenance) to resolved bytes. Every reference
in the report is resolved first. Both return exactly status/expected/actual;
status is a literal pass, fail or unavailable string, and both texts are nonempty.
The parent is responsible for reviewer independence and source authenticity.
"""
from __future__ import annotations

from copy import deepcopy

from suiroai.contracts import record_ref


_REF_FIELDS = {"artifact_id", "version", "sha256", "provenance"}


def _references(value):
    if isinstance(value, dict):
        if set(value) == _REF_FIELDS:
            yield value
        else:
            for child in value.values():
                yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def _key(ref):
    return tuple(ref[name] for name in
                 ("artifact_id", "version", "sha256", "provenance"))


def _review(callback, *args):
    if not callable(callback):
        return {"status": "unavailable", "expected": "Trusted independent review",
                "actual": "Independent review callback is unavailable"}
    try:
        result = callback(*deepcopy(args))
    except Exception as exc:
        return {"status": "unavailable", "expected": "Completed independent review",
                "actual": f"Independent review raised {type(exc).__name__}"}
    if (type(result) is not dict or set(result) != {"status", "expected", "actual"}
            or type(result["status"]) is not str
            or result["status"] not in {"pass", "fail", "unavailable"}
            or any(type(result[name]) is not str or not result[name].strip()
                   for name in ("expected", "actual"))):
        return {"status": "unavailable", "expected": "Explicit measured review result",
                "actual": "Independent review returned an invalid result"}
    return dict(result)


def check_claims(report, *, resolve_bytes, review_claim=None,
                 review_narrative=None, verifier):
    """Return shared check dictionaries; any non-pass blocks delivery.

    ``report`` must already have passed shared record validation. Resolution must
    verify immutable reference hashes. Returned checks do not authorize delivery;
    the parent must check current bindings and authorize the exact reviewed draft.
    Exceptions from evidence retrieval fail closed without exposing exception text.
    """
    if type(verifier) is not str or not verifier.strip():
        raise ValueError("An independent verifier identity is required")
    report = deepcopy(report)
    report_reference = record_ref(report)
    checks = []

    def add(check_id, result, refs=()):
        checks.append({"check_id": check_id, "requirement_id": "DSC-30-report-claims",
                       **result, "evidence_refs": [deepcopy(report_reference),
                                                   *deepcopy(list(refs))],
                       "verifier": verifier})

    def structural(check_id, passed, expected, actual):
        add(check_id, {"status": "pass" if passed else "fail",
                       "expected": expected, "actual": actual})

    evidence = {}
    unavailable = set()
    for ref in _references(report):
        key = _key(ref)
        if key in evidence or key in unavailable:
            continue
        try:
            data = resolve_bytes(deepcopy(ref))
            if type(data) is not bytes:
                raise TypeError("Evidence resolver must return bytes")
            evidence[key] = data
        except Exception:
            unavailable.add(key)
    add("claims-evidence-resolution", {
        "status": "unavailable" if unavailable else "pass",
        "expected": "All report references resolve to independently verified bytes",
        "actual": (f"Resolved {len(evidence)} references; "
                   f"{len(unavailable)} references unavailable")})

    claims = report.get("claims", [])
    structural("claims-declared", bool(claims),
               "Material customer claims are explicitly declared",
               f"Report declares {len(claims)} claims")
    items = [("claim", item) for item in claims]
    items += [("finding", item) for item in report.get("findings", [])
              if item.get("audience") == "final_report"]
    identities = []
    for index, (kind, item) in enumerate(items):
        identities.append((kind, item.get(f"{kind}_id")))
        refs = item.get("evidence_refs", [])
        if not refs:
            result = {"status": "fail", "expected": "Evidence-linked independent review",
                      "actual": f"Declared {kind} has no evidence references"}
        elif any(_key(ref) not in evidence for ref in refs):
            result = {"status": "unavailable", "expected": "Resolved independent evidence",
                      "actual": f"Declared {kind} evidence is unavailable"}
        else:
            result = _review(review_claim, item,
                             tuple(evidence[_key(ref)] for ref in refs))
        add(f"claims-{kind}-{index}", result, refs)
    structural("claims-unique-identities", len(identities) == len(set(identities)),
               "Declared claim and finding identities are unique",
               f"Reviewed {len(identities)} declarations and {len(set(identities))} identities")

    if report.get("outcome") != "success":
        structural("claims-terminal-no-orders",
                   not report.get("orders") and report.get("quantity_result_ref") is None,
                   "Guidance and failure explanations contain no recommendation list",
                   f"Order rows={len(report.get('orders', []))}; "
                   f"quantity reference present={report.get('quantity_result_ref') is not None}")
    if report.get("outcome") in {"validation_failure", "execution_failure"}:
        failure = report.get("failure") or {}
        structural("claims-terminal-scope", bool(str(failure.get("scope_limitation") or "").strip()),
                   "Terminal explanation declares its supplied-data/MVP scope limitation",
                   "Scope field present" if failure.get("scope_limitation") else "Scope field missing")
    if unavailable:
        add("claims-full-narrative", {
            "status": "unavailable", "expected": "Whole narrative reviewed against resolved evidence",
            "actual": "Full narrative review blocked by unavailable report evidence"})
    else:
        add("claims-full-narrative", _review(review_narrative, report, evidence))
    return checks
