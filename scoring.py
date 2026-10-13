from analyze import CVAnalysis, analyze_cv

MIN_STATEMENTS = 5  # floor so very short statement lists can't swing the ratios


def ratio(part: int, total: int) -> float:
    return min(part / max(total, MIN_STATEMENTS), 1.0) if total > 0 else 0.0


def _clamp(value: int, low: int = 0, high: int = 10) -> int:
    return max(low, min(high, value))


def score_cv(a: CVAnalysis) -> dict:
    #Turn the model's structured facts into a percentage
    if not a.is_cv:
        return {
            "percentage": 0,
            "breakdown": {},
            "tips": [],
            "message": "This doesn't look like a CV. Please upload your CV.",
        }

    total = len(a.statements)
    quantified = sum(s.quantified for s in a.statements)
    results = sum(s.shows_result for s in a.statements)

    quality = (
        _clamp(a.clarity)
        + _clamp(a.impact)
        + _clamp(a.structure_and_readability)
        + _clamp(a.language_and_tone)
    ) / 40
    contact = (
        (4 if a.has_email else 0)
        + (3 if a.has_phone else 0)
        + (3 if a.has_location_or_online_profile else 0)
    )

    parts = {
        "Quality (clarity, impact, structure, language)": (quality * 50, 50),
        "Quantified achievements": (ratio(quantified, total) * 20, 20),
        "Results focus": (ratio(results, total) * 15, 15),
        "Contact details": (contact, 10),
        "Accuracy (spelling and grammar)": (max(0, 5 - max(0, a.spelling_or_grammar_errors)), 5),
    }

    return {
        "percentage": round(sum(earned for earned, _ in parts.values())),
        "breakdown": {k: f"{round(e, 1)} / {m}" for k, (e, m) in parts.items()},
        "statements_found": total,
        "statements_quantified": quantified,
        "statements_with_results": results,
        "tips": [t.model_dump() for t in sorted(a.tips, key=lambda t: t.priority)],
        "field": a.detected_field,
        "seniority": a.detected_seniority,
    }


def review_cv(text: str) -> dict:
    return score_cv(analyze_cv(text))