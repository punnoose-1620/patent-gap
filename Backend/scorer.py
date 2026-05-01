import hashlib
from datetime import datetime, timezone


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


def has_cached_score(infringement_obj, expected_hash, method=SCORE_METHOD, version=SCORE_VERSION):
    if not isinstance(infringement_obj, dict):
        return False
    if not _clean_claim_text(infringement_obj.get("ref_claim", "")):
        return False
    cached_score = infringement_obj.get("calculated_similarity_score")
    if not isinstance(cached_score, (int, float)):
        return False
    if infringement_obj.get("score_method") != method:
        return False
    if infringement_obj.get("score_version") != version:
        return False
    if infringement_obj.get("scoring_input_hash") != expected_hash:
        return False
    return True


def find_best_reference_claim(reference_claims, infringing_claim):
    from data_processor import getPatentEmbedding, getSimilarityScore

    clean_infringing_claim = _clean_claim_text(infringing_claim)
    if not clean_infringing_claim:
        return None, -1

    infringing_embedding = getPatentEmbedding(clean_infringing_claim)
    if infringing_embedding is None:
        return None, -1

    best_ref_claim = None
    best_score = -1

    for ref_claim in reference_claims:
        clean_ref_claim = _clean_claim_text(ref_claim)
        if not clean_ref_claim:
            continue

        reference_embedding = getPatentEmbedding(clean_ref_claim)
        if reference_embedding is None:
            continue

        score = getSimilarityScore(reference_embedding, infringing_embedding)
        if isinstance(score, (int, float)) and score > best_score:
            best_score = float(score)
            best_ref_claim = clean_ref_claim

    return best_ref_claim, best_score


def score_infringement_entry(reference_claims, infringement_obj, threshold=0.5):
    if not isinstance(infringement_obj, dict):
        return None

    infringing_claim = _clean_claim_text(infringement_obj.get("claim", ""))
    if not infringing_claim:
        return None

    existing_ref_claim = _clean_claim_text(infringement_obj.get("ref_claim", ""))
    ref_for_hash = existing_ref_claim if existing_ref_claim else ""
    expected_hash = build_scoring_input_hash(ref_for_hash, infringing_claim)

    if has_cached_score(infringement_obj, expected_hash):
        cached_score = float(infringement_obj.get("calculated_similarity_score"))
        if cached_score > threshold:
            return {
                "ref_claim": existing_ref_claim,
                "infringing_claim": infringing_claim,
                "similarity_score": cached_score,
                "evaluation_method": SCORE_METHOD,
                "last_evaluated": infringement_obj.get("last_scored_at"),
            }
        return None

    best_ref_claim, best_score = find_best_reference_claim(reference_claims, infringing_claim)
    if (not best_ref_claim) or (not isinstance(best_score, (int, float))) or (best_score <= threshold):
        return None

    now_iso = _utc_now_iso()
    final_hash = build_scoring_input_hash(best_ref_claim, infringing_claim)
    infringement_obj["ref_claim"] = best_ref_claim
    infringement_obj["calculated_similarity_score"] = float(best_score)
    infringement_obj["score_method"] = SCORE_METHOD
    infringement_obj["score_version"] = SCORE_VERSION
    infringement_obj["scoring_input_hash"] = final_hash
    infringement_obj["last_scored_at"] = now_iso

    return {
        "ref_claim": best_ref_claim,
        "infringing_claim": infringing_claim,
        "similarity_score": float(best_score),
        "evaluation_method": SCORE_METHOD,
        "last_evaluated": now_iso,
    }
