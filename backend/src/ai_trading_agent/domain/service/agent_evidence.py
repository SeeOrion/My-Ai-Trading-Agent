"""Evidence-referenced reports and non-overlapping research scoring dimensions."""

import json
from decimal import Decimal


class InsufficientEvidence(ValueError):
    pass


DIMENSIONS = {
    "event_veracity": Decimal("0.35"),
    "earnings_persistence": Decimal("0.35"),
    "thesis_resilience": Decimal("0.30"),
}


def validate_agent_report(report, trace):
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    if report.get("status") == "insufficient_evidence":
        raise InsufficientEvidence("missing evidence")
    evidence = {str(i): row for i, row in enumerate(trace) if row.get("status") == "completed"}
    if len(evidence) < 2:
        raise InsufficientEvidence("at least two tool observations required")

    def check_claim(claim):
        if (
            not isinstance(claim, dict)
            or not isinstance(claim.get("text"), str)
            or not claim["text"].strip()
        ):
            raise ValueError("invalid claim")
        refs = claim.get("evidence_ids", [])
        if not refs or any(str(ref) not in evidence for ref in refs):
            raise InsufficientEvidence("invalid evidence reference")
        return {"text": claim["text"][:1000], "evidence_ids": [str(ref) for ref in refs]}

    scores, total = {}, Decimal(0)
    for name, weight in DIMENSIONS.items():
        item = report["dimensions"][name]
        claim = check_claim(item)
        required = {
            "event_veracity": {"news"},
            "earnings_persistence": {"financials"},
            "thesis_resilience": {"quote", "technical", "capital_flow", "factors"},
        }[name]
        if not any(evidence[ref]["tool"] in required for ref in claim["evidence_ids"]):
            raise InsufficientEvidence("dimension lacks relevant source observations")
        value = Decimal(str(item["score"]))
        if not value.is_finite() or not 0 <= value <= 100:
            raise ValueError("invalid dimension score")
        scores[name] = {**claim, "score": str(value), "weight": str(weight)}
        total += value * weight
    risks = []
    for risk in report.get("risks", [])[:10]:
        checked = check_claim(risk)
        severity = risk.get("severity")
        if severity not in {"minor", "major", "critical"}:
            raise ValueError("invalid severity")
        quote = risk.get("source_quote", "")
        if (
            not isinstance(quote, str)
            or len(quote.strip()) < 8
            or not any(
                quote in json.dumps(evidence[ref]["evidence"], ensure_ascii=False, default=str)
                for ref in checked["evidence_ids"]
            )
        ):
            raise InsufficientEvidence("risk needs an exact source excerpt")
        risks.append({**checked, "severity": severity, "source_quote": quote[:2000]})
    action = report.get("recommendation")
    if action not in {"buy", "wait", "hold", "reduce", "exit"}:
        raise ValueError("invalid recommendation")
    thesis_state = report.get("thesis_state", "unverifiable")
    if thesis_state not in {"intact", "weakened", "invalidated", "unverifiable"}:
        raise ValueError("invalid thesis state")
    thesis = check_claim(report["thesis"])
    lower, upper = Decimal(str(report["price_min"])), Decimal(str(report["price_max"]))
    if not lower.is_finite() or not upper.is_finite() or not 0 < lower <= upper:
        raise ValueError("invalid entry price range")
    return {
        "status": "completed",
        "score": str(total),
        "dimensions": scores,
        "support": [check_claim(c) for c in report.get("support", [])[:10]],
        "opposition": [check_claim(c) for c in report.get("opposition", [])[:10]],
        "risks": risks,
        "data_gaps": [str(s)[:500] for s in report.get("data_gaps", [])[:10]],
        "thesis": thesis,
        "thesis_state": thesis_state,
        "recommendation": action,
        "price_min": str(lower),
        "price_max": str(upper),
    }
