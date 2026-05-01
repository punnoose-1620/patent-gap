import hashlib
from datetime import datetime, timezone
from itertools import product

SCORE_METHOD = "embedding_cosine"
SCORE_VERSION = "v1"


def _clean_claim_text(claim):
    if not isinstance(claim, str):
        return ""
    return claim.strip()


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_scoring_input_hash(ref_claim, infringing_claim, method=SCORE_METHOD, version=SCORE_VERSION):
    payload = f"{method}|{version}|{_clean_claim_text(ref_claim)}|{_clean_claim_text(infringing_claim)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_cache_map(existing_infringements):
    out = {}
    if not isinstance(existing_infringements, list):
        return out
    for row in existing_infringements:
        if not isinstance(row, dict):
            continue
        h = row.get("scoring_input_hash")
        if not h:
            continue
        out[h] = row
    return out


def _cached_row_valid(row, expected_hash):
    if row.get("scoring_input_hash") != expected_hash:
        return False
    if row.get("score_method") != SCORE_METHOD:
        return False
    if row.get("score_version") != SCORE_VERSION:
        return False
    if not isinstance(row.get("calculated_similarity_score"), (int, float)):
        return False
    return True


def _chart_row_from_storage(row):
    inf = _clean_claim_text(row.get("claim", ""))
    return {
        "ref_claim": _clean_claim_text(row.get("ref_claim", "")),
        "infringing_claim": inf,
        "similarity_score": float(row["calculated_similarity_score"]),
        "evaluation_method": SCORE_METHOD,
        "last_evaluated": row.get("last_scored_at"),
    }


def _pair_scores_matrix_openai(ref_list, inf_list):
    """Return dict (ref, inf) -> score, or None if embeddings not uniform."""
    from data_processor import getPatentEmbedding, getSimilarityScore

    ref_embs = []
    for r in ref_list:
        e = getPatentEmbedding(r)
        ref_embs.append(e)
    inf_embs = []
    for t in inf_list:
        e = getPatentEmbedding(t)
        inf_embs.append(e)
    if any(e is None for e in ref_embs + inf_embs):
        return None
    dim = len(ref_embs[0])
    if any(len(e) != dim for e in ref_embs + inf_embs):
        return None

    scores = {}
    for i, ref in enumerate(ref_list):
        for j, inf in enumerate(inf_list):
            s = getSimilarityScore(ref_embs[i], inf_embs[j])
            if not isinstance(s, (int, float)) or s < 0:
                return None
            scores[(ref, inf)] = float(s)
    return scores


def _pair_scores_matrix_tfidf(ref_list, inf_list):
    """Single vector space for all claims in this matrix (same row length)."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        all_docs = ref_list + inf_list
        v = TfidfVectorizer(min_df=1)
        X = v.fit_transform(all_docs)
        n_ref = len(ref_list)
        ref_X = X[:n_ref]
        inf_X = X[n_ref:]
        scores = {}
        for i, ref in enumerate(ref_list):
            for j, inf in enumerate(inf_list):
                s = float(cosine_similarity(ref_X[i], inf_X[j])[0][0])
                if s < 0:
                    s = abs(s)
                scores[(ref, inf)] = float(min(1.0, max(0.0, s)))
        return scores
    except Exception:
        return None


def _pair_scores_matrix(ref_list, inf_list):
    scores = _pair_scores_matrix_openai(ref_list, inf_list)
    if scores is not None:
        return scores
    return _pair_scores_matrix_tfidf(ref_list, inf_list)


def _fully_cached_matrix(ref_list, inf_list, existing_infringements, cache, threshold):
    """If every (ref, inf) pair has a valid cached row, return (stored, chart) without re-embedding."""
    if not isinstance(existing_infringements, list):
        return None
    stored_rows = []
    chart_rows = []
    for ref, inf in product(ref_list, inf_list):
        h = build_scoring_input_hash(ref, inf)
        if h not in cache or not _cached_row_valid(cache[h], h):
            return None
        row = cache[h]
        calc = float(row["calculated_similarity_score"])
        if calc > threshold:
            stored_rows.append(row)
            chart_rows.append(_chart_row_from_storage(row))
    return stored_rows, chart_rows


def score_infringement_matrix_entry(reference_claims, infringing_claims, existing_infringements, threshold=0.5):
    """
    Full matrix: each parent claim x each infringing claim. Stores only pairs with
    calculated_similarity_score > threshold.

    existing_infringements may be a legacy Gemini dict, a list of scored rows, or None.

    Returns:
        (stored_rows: list | None, chart_rows: list)
        stored_rows is None if there is nothing to persist (no infringing claims).
    """
    ref_list = [_clean_claim_text(c) for c in (reference_claims or []) if _clean_claim_text(c)]
    inf_list = [_clean_claim_text(c) for c in (infringing_claims or []) if _clean_claim_text(c)]
    if not ref_list or not inf_list:
        return None, []

    cache = _row_cache_map(existing_infringements if isinstance(existing_infringements, list) else [])
    full_cache = _fully_cached_matrix(ref_list, inf_list, existing_infringements, cache, threshold)
    if full_cache is not None:
        return full_cache

    pair_scores = _pair_scores_matrix(ref_list, inf_list)
    if pair_scores is None:
        return None, []

    stored_rows = []
    chart_rows = []
    now_iso = _utc_now_iso()

    for ref, inf in product(ref_list, inf_list):
        h = build_scoring_input_hash(ref, inf)
        if h in cache and _cached_row_valid(cache[h], h):
            row = cache[h]
            calc = float(row["calculated_similarity_score"])
            if calc > threshold:
                stored_rows.append(row)
                chart_rows.append(_chart_row_from_storage(row))
            continue

        score = float(pair_scores[(ref, inf)])
        if score <= threshold:
            continue

        row = {
            "ref_claim": ref,
            "claim": inf,
            "calculated_similarity_score": score,
            "score_method": SCORE_METHOD,
            "score_version": SCORE_VERSION,
            "scoring_input_hash": h,
            "last_scored_at": now_iso,
        }
        stored_rows.append(row)
        chart_rows.append(
            {
                "ref_claim": ref,
                "infringing_claim": inf,
                "similarity_score": score,
                "evaluation_method": SCORE_METHOD,
                "last_evaluated": now_iso,
            }
        )

    return stored_rows, chart_rows
