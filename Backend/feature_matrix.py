"""
Secondary AI-only feature × product claim matrix.

Independent of embedding claim-chart scores. Built as a sibling step after
claim-matrix scoring in ``get_infringement_chart``.
"""
from __future__ import annotations

from typing import Any, Optional

from structures.notes import validate_note_content

# Embedding check: model-returned inf_claim must match the real claim j.
INF_CLAIM_MATCH_THRESHOLD = 0.75
FEATURE_MATRIX_MAX_ATTEMPTS = 5


def _clean(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return text.strip()


def _normalize_feature_key(text: str) -> str:
    return " ".join(_clean(text).lower().split())


def _justification_ok(text: str) -> tuple[bool, str]:
    ok, result = validate_note_content(text)
    if not ok:
        return False, str(result)
    return True, str(result)


def _inf_claim_matches(expected: str, got: str) -> bool:
    """True when returned inf_claim matches claim j (embedding cosine)."""
    exp = _clean(expected)
    got_c = _clean(got)
    if not exp or not got_c:
        return False
    if _normalize_feature_key(exp) == _normalize_feature_key(got_c):
        return True
    try:
        from data_processor import getPatentEmbedding, getSimilarityScore

        e1 = getPatentEmbedding(exp)
        e2 = getPatentEmbedding(got_c)
        if e1 is None or e2 is None:
            # Fail closed on embed failure unless exact/near-exact text match above.
            return False
        score = getSimilarityScore(e1, e2)
        return isinstance(score, (int, float)) and float(score) >= INF_CLAIM_MATCH_THRESHOLD
    except Exception as e:
        print(f"LOG: feature-matrix inf_claim embed check failed: {e}", flush=True)
        return False


def extract_documented_ref_claims(case_data: dict) -> list[tuple[int, str]]:
    """
    Return (index, documented/original claim text) pairs for feature extraction.

    Prefer documented_claim from bucketed claims; fall back to plain string list.
    """
    claims = (case_data or {}).get("claims")
    out: list[tuple[int, str]] = []
    if isinstance(claims, list) and all(isinstance(c, str) for c in (claims or [])):
        for i, text in enumerate(claims):
            t = _clean(text)
            if t:
                out.append((i, t))
        return out
    if isinstance(claims, dict):
        def _key_order(item):
            key = item[0]
            try:
                return (0, int(key))
            except (TypeError, ValueError):
                return (1, str(key))

        for key, claim_data in sorted(claims.items(), key=_key_order):
            if not isinstance(claim_data, dict):
                continue
            try:
                idx = int(key)
            except (TypeError, ValueError):
                idx = len(out)
            documented = _clean(claim_data.get("documented_claim"))
            if not documented:
                documented = _clean(claim_data.get("market_language_claim"))
            if documented:
                out.append((idx, documented))
    return out


def get_cached_features(case_data: dict, ref_index: int) -> Optional[list[str]]:
    cache = (case_data or {}).get("claim_features") or {}
    if isinstance(cache, dict):
        raw = cache.get(str(ref_index))
        if isinstance(raw, list) and raw:
            return [_clean(f) for f in raw if _clean(f)]
    claims = (case_data or {}).get("claims")
    if isinstance(claims, dict):
        entry = claims.get(str(ref_index)) or claims.get(ref_index)
        if isinstance(entry, dict):
            raw = entry.get("features")
            if isinstance(raw, list) and raw:
                return [_clean(f) for f in raw if _clean(f)]
    return None


def set_cached_features(case_data: dict, ref_index: int, features: list[str]) -> None:
    cleaned = [_clean(f) for f in features if _clean(f)]
    cache = case_data.get("claim_features")
    if not isinstance(cache, dict):
        cache = {}
    cache[str(ref_index)] = cleaned
    case_data["claim_features"] = cache
    claims = case_data.get("claims")
    if isinstance(claims, dict):
        key = str(ref_index) if str(ref_index) in claims else ref_index
        if key in claims and isinstance(claims[key], dict):
            claims[key] = dict(claims[key])
            claims[key]["features"] = list(cleaned)
            case_data["claims"] = claims


def claim_features_map_from_claims(claims: dict) -> dict[str, list[str]]:
    """Build case-level claim_features map from bucketed claims[*].features."""
    out: dict[str, list[str]] = {}
    if not isinstance(claims, dict):
        return out
    for key, entry in claims.items():
        if not isinstance(entry, dict):
            continue
        raw = entry.get("features")
        if not isinstance(raw, list):
            continue
        cleaned = [_clean(f) for f in raw if _clean(f)]
        if cleaned:
            out[str(key)] = cleaned
    return out


def fill_missing_features_on_claims(claims: dict, *, gemini=None) -> dict[str, list[str]]:
    """
    Ensure every bucketed claim dict has a non-empty features list.

    Uses existing features when present; otherwise calls Gemini extract_claim_features
    on documented_claim (fallback: market_language_claim).
    Returns the claim_features map (index -> features).
    """
    if not isinstance(claims, dict):
        return {}
    if gemini is None:
        # Lazy: only construct if at least one claim needs extract.
        needs = False
        for entry in claims.values():
            if not isinstance(entry, dict):
                continue
            raw = entry.get("features")
            if not (isinstance(raw, list) and any(_clean(f) for f in raw)):
                needs = True
                break
        if needs:
            from llm_brain.gemini import Gemini
            gemini = Gemini()

    for key, entry in list(claims.items()):
        if not isinstance(entry, dict):
            continue
        raw = entry.get("features")
        cleaned = [_clean(f) for f in raw if _clean(f)] if isinstance(raw, list) else []
        if cleaned:
            claims[key] = dict(entry)
            claims[key]["features"] = cleaned
            continue
        text = _clean(entry.get("documented_claim")) or _clean(entry.get("market_language_claim"))
        if not text or gemini is None:
            continue
        try:
            features = gemini.extract_claim_features(text)
            cleaned = [_clean(f) for f in features if _clean(f)]
        except Exception as e:
            print(f"LOG: fill_missing_features failed for claim {key}: {e}", flush=True)
            cleaned = []
        claims[key] = dict(entry)
        if cleaned:
            claims[key]["features"] = cleaned

    return claim_features_map_from_claims(claims)


def ensure_claim_features(
    case_data: dict,
    ref_index: int,
    claim_text: str,
    *,
    gemini=None,
) -> list[str]:
    cached = get_cached_features(case_data, ref_index)
    if cached:
        # Keep claims[*].features in sync when only claim_features was populated.
        set_cached_features(case_data, ref_index, cached)
        return cached
    if gemini is None:
        from llm_brain.gemini import Gemini
        gemini = Gemini()
    features = gemini.extract_claim_features(claim_text)
    set_cached_features(case_data, ref_index, features)
    return get_cached_features(case_data, ref_index) or list(features)


def _row_to_dict(
    *,
    ref_claim_index: int,
    feature: str,
    inf_claim: str,
    product_id: str,
    possible_infringement: bool,
    possible_infringement_percentage: int,
    possible_infringement_justification: str,
) -> dict:
    return {
        "ref_claim_index": int(ref_claim_index),
        "feature": feature,
        "inf_claim": inf_claim,
        "product_id": product_id,
        "possible_infringement": bool(possible_infringement),
        "possible_infringement_percentage": int(possible_infringement_percentage),
        "possible_infringement_justification": possible_infringement_justification,
    }


def validate_feature_rows_against_expected(
    items: list,
    *,
    ref_claim_index: int,
    expected_features: list[str],
    expected_inf_claim: str,
    expected_product_id: str,
) -> tuple[list[dict], list[str], str]:
    """
    Split model items into (ok_rows, features_needing_retry, error_summary).

    Forces stored inf_claim / product_id / ref_claim_index to the expected values
    when validation otherwise passes.
    """
    allowed = {_normalize_feature_key(f): f for f in expected_features}
    seen_ok: set[str] = set()
    ok_rows: list[dict] = []
    retry_features: list[str] = []
    errors: list[str] = []

    for item in items or []:
        feature = _clean(getattr(item, "feature", None) if not isinstance(item, dict) else item.get("feature"))
        inf_claim = _clean(
            getattr(item, "inf_claim", None) if not isinstance(item, dict) else item.get("inf_claim")
        )
        product_id = _clean(
            getattr(item, "product_id", None) if not isinstance(item, dict) else item.get("product_id")
        )
        if isinstance(item, dict):
            pct_raw = item.get("possible_infringement_percentage")
            just = item.get("possible_infringement_justification")
            pinfr = item.get("possible_infringement")
            idx_raw = item.get("ref_claim_index")
        else:
            pct_raw = getattr(item, "possible_infringement_percentage", None)
            just = getattr(item, "possible_infringement_justification", None)
            pinfr = getattr(item, "possible_infringement", None)
            idx_raw = getattr(item, "ref_claim_index", None)

        fkey = _normalize_feature_key(feature)
        if fkey not in allowed:
            errors.append(f"unknown feature {feature!r}")
            continue

        try:
            idx = int(idx_raw)
        except (TypeError, ValueError):
            errors.append(f"bad ref_claim_index for feature {feature!r}")
            retry_features.append(allowed[fkey])
            continue
        if idx != int(ref_claim_index):
            errors.append(
                f"ref_claim_index {idx} != expected {ref_claim_index} for feature {feature!r}"
            )
            retry_features.append(allowed[fkey])
            continue

        if not _inf_claim_matches(expected_inf_claim, inf_claim):
            errors.append(f"inf_claim hallucination for feature {feature!r}")
            retry_features.append(allowed[fkey])
            continue

        if _normalize_feature_key(product_id) != _normalize_feature_key(expected_product_id):
            # Soft: overwrite if non-empty mismatch is minor; still require non-empty
            if not product_id:
                errors.append(f"missing product_id for feature {feature!r}")
                retry_features.append(allowed[fkey])
                continue

        try:
            pct = int(pct_raw)
        except (TypeError, ValueError):
            errors.append(f"bad percentage for feature {feature!r}")
            retry_features.append(allowed[fkey])
            continue
        if pct < 0 or pct > 100:
            errors.append(f"percentage out of range for feature {feature!r}")
            retry_features.append(allowed[fkey])
            continue

        if isinstance(pinfr, bool):
            pinfr_b = pinfr
        elif str(pinfr).strip().lower() in ("true", "1", "yes"):
            pinfr_b = True
        elif str(pinfr).strip().lower() in ("false", "0", "no"):
            pinfr_b = False
        else:
            errors.append(f"bad possible_infringement for feature {feature!r}")
            retry_features.append(allowed[fkey])
            continue

        just_ok, just_text = _justification_ok(just if isinstance(just, str) else str(just or ""))
        if not just_ok:
            errors.append(f"justification invalid for feature {feature!r}: {just_text}")
            retry_features.append(allowed[fkey])
            continue

        if fkey in seen_ok:
            continue
        seen_ok.add(fkey)
        ok_rows.append(
            _row_to_dict(
                ref_claim_index=int(ref_claim_index),
                feature=allowed[fkey],
                inf_claim=_clean(expected_inf_claim),
                product_id=_clean(expected_product_id),
                possible_infringement=pinfr_b,
                possible_infringement_percentage=pct,
                possible_infringement_justification=just_text,
            )
        )

    missing = [
        f for f in expected_features if _normalize_feature_key(f) not in seen_ok
    ]
    for f in missing:
        if f not in retry_features:
            retry_features.append(f)
            errors.append(f"missing row for feature {f!r}")

    # Dedupe retry list preserving order
    deduped_retry: list[str] = []
    seen_r: set[str] = set()
    for f in retry_features:
        k = _normalize_feature_key(f)
        if k in seen_r:
            continue
        seen_r.add(k)
        deduped_retry.append(f)

    return ok_rows, deduped_retry, "; ".join(errors[:8])


def evaluate_features_vs_claim_with_retry(
    *,
    ref_claim_index: int,
    features: list[str],
    infringing_claim: str,
    product_id: str,
    gemini=None,
) -> list[dict]:
    """One (claim i features × claim j) evaluation with batched error retries."""
    if gemini is None:
        from llm_brain.gemini import Gemini
        gemini = Gemini()

    pending = list(features)
    accepted: list[dict] = []
    attempt = 0
    last_err = ""

    while pending and attempt < FEATURE_MATRIX_MAX_ATTEMPTS:
        attempt += 1
        try:
            items = gemini.analyze_claim_features_vs_infringing_claim(
                ref_claim_index=ref_claim_index,
                features=features,
                infringing_claim=infringing_claim,
                product_id=product_id,
                features_subset=pending,
            )
        except Exception as e:
            last_err = str(e)
            print(
                f"LOG: feature-matrix AI call failed "
                f"(ref={ref_claim_index} product={product_id} attempt={attempt}): {e}",
                flush=True,
            )
            continue

        ok_rows, retry_features, err = validate_feature_rows_against_expected(
            items,
            ref_claim_index=ref_claim_index,
            expected_features=pending,
            expected_inf_claim=infringing_claim,
            expected_product_id=product_id,
        )
        accepted.extend(ok_rows)
        pending = retry_features
        last_err = err or last_err
        if pending:
            print(
                f"LOG: feature-matrix retry {len(pending)} feature(s) "
                f"(ref={ref_claim_index} product={product_id} attempt={attempt}): {last_err}",
                flush=True,
            )

    if pending:
        print(
            f"LOG: feature-matrix dropped {len(pending)} feature(s) after "
            f"{FEATURE_MATRIX_MAX_ATTEMPTS} attempts "
            f"(ref={ref_claim_index} product={product_id}): {last_err}",
            flush=True,
        )
    return accepted


def build_and_attach_feature_matrix(case_data: dict, *, gemini=None) -> bool:
    """
    Build case-level ``feature_matrix`` for product infringements.

    Returns True if case_data was mutated (matrix / claim_features updated).
    Does not affect embedding similarity scores.
    """
    if not isinstance(case_data, dict):
        return False

    ref_claims = extract_documented_ref_claims(case_data)
    if not ref_claims:
        print("LOG: feature-matrix skipped — no documented reference claims", flush=True)
        return False

    infringements = case_data.get("infringements") or []
    product_entries = [
        e
        for e in infringements
        if isinstance(e, dict) and str(e.get("product_id") or "").strip()
    ]
    if not product_entries:
        print("LOG: feature-matrix skipped — no product infringements", flush=True)
        return False

    if gemini is None:
        from llm_brain.gemini import Gemini
        gemini = Gemini()

    # Cache features for all ref claims first
    features_by_index: dict[int, list[str]] = {}
    for idx, text in ref_claims:
        try:
            features_by_index[idx] = ensure_claim_features(
                case_data, idx, text, gemini=gemini
            )
        except Exception as e:
            print(f"LOG: feature extract failed for claim {idx}: {e}", flush=True)
            features_by_index[idx] = []

    matrix_rows: list[dict] = []
    for entry in product_entries:
        product_id = str(entry.get("product_id") or "").strip()
        inf_claims = [
            _clean(c)
            for c in (entry.get("claims") or [])
            if isinstance(c, str) and _clean(c)
        ]
        if not inf_claims:
            continue
        for idx, _ref_text in ref_claims:
            feats = features_by_index.get(idx) or []
            if not feats:
                continue
            for inf_claim in inf_claims:
                rows = evaluate_features_vs_claim_with_retry(
                    ref_claim_index=idx,
                    features=feats,
                    infringing_claim=inf_claim,
                    product_id=product_id,
                    gemini=gemini,
                )
                matrix_rows.extend(rows)

    case_data["feature_matrix"] = matrix_rows
    print(
        f"LOG: feature-matrix built rows={len(matrix_rows)} "
        f"ref_claims={len(ref_claims)} products={len(product_entries)}",
        flush=True,
    )
    return True
