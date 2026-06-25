"""Filter infringement claim-pair scores below the similarity threshold."""

CLAIM_SIMILARITY_THRESHOLD = 0.85


def _as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_meets_threshold(score, threshold=CLAIM_SIMILARITY_THRESHOLD) -> bool:
    parsed = _as_float(score)
    if parsed is None:
        return False
    return parsed > threshold


def filter_similar_claims(similar_claims, threshold=CLAIM_SIMILARITY_THRESHOLD):
    if not isinstance(similar_claims, list):
        return similar_claims
    return [
        item
        for item in similar_claims
        if isinstance(item, dict)
        and score_meets_threshold(
            item.get("similarity_score", item.get("calculated_similarity_score")),
            threshold,
        )
    ]


def filter_scored_infringement_rows(rows, threshold=CLAIM_SIMILARITY_THRESHOLD):
    if not isinstance(rows, list):
        return rows
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and score_meets_threshold(row.get("calculated_similarity_score"), threshold)
    ]


def filter_infringement_entry(entry, threshold=CLAIM_SIMILARITY_THRESHOLD):
    if not isinstance(entry, dict):
        return entry

    filtered = dict(entry)

    if "similar_claims" in filtered:
        filtered["similar_claims"] = filter_similar_claims(
            filtered.get("similar_claims"), threshold
        )

    nested = filtered.get("infringements")
    if isinstance(nested, list):
        filtered["infringements"] = filter_scored_infringement_rows(nested, threshold)
    elif isinstance(nested, dict):
        score = nested.get("similarity_score", nested.get("calculated_similarity_score"))
        if not score_meets_threshold(score, threshold):
            filtered.pop("infringements", None)

    gemini = filtered.get("gemini_infringement")
    if isinstance(gemini, dict):
        score = gemini.get("similarity_score", gemini.get("calculated_similarity_score"))
        if not score_meets_threshold(score, threshold):
            filtered.pop("gemini_infringement", None)

    return filtered


def filter_infringements_list(infringements, threshold=CLAIM_SIMILARITY_THRESHOLD):
    if not isinstance(infringements, list):
        return infringements
    return [filter_infringement_entry(entry, threshold) for entry in infringements]


def filter_chart_rows(chart_rows, threshold=CLAIM_SIMILARITY_THRESHOLD):
    if not isinstance(chart_rows, list):
        return chart_rows
    kept = []
    for row in chart_rows:
        if not isinstance(row, dict):
            continue
        score = row.get("similarity_score", row.get("calculated_similarity_score"))
        if score_meets_threshold(score, threshold):
            kept.append(row)
    return kept


def apply_infringement_filters_to_case(case_data, threshold=CLAIM_SIMILARITY_THRESHOLD):
    if not isinstance(case_data, dict):
        return case_data
    infringements = case_data.get("infringements")
    if isinstance(infringements, list):
        case_data = dict(case_data)
        case_data["infringements"] = filter_infringements_list(infringements, threshold)
    return case_data
