import hashlib
import re
from datetime import datetime, timezone
from itertools import product

SCORE_METHOD = "embedding_cosine"
# v3: claim-number assignment + additive forward-fold (i + all additives) + parent-gate.
SCORE_VERSION = "v3"

_CLAIM_NUM_HEAD_RE = re.compile(
    r"^\s*(?:claim\s*)?(\d+)\s*[.:)\-\u2013\u2014]\s*",
    re.IGNORECASE,
)
_PARENT_REF_RE = re.compile(
    r"\bclaims?\s+(\d+(?:\s*(?:-|–|—|to|or|and|,|/)\s*\d+)*)",
    re.IGNORECASE,
)
_PARENT_NUM_RE = re.compile(r"\d+")
# Contrastive cues immediately before a claim reference.
_CONTRASTIVE_PARENT_RE = re.compile(
    r"\b(?:"
    r"unlike|instead\s+of|alternative\s+to|contrary\s+to|different\s+from|"
    r"as\s+opposed\s+to|rather\s+than|excluding|except(?:ing)?"
    r")\s+claims?\s+(\d+(?:\s*(?:-|–|—|to|or|and|,|/)\s*\d+)*)",
    re.IGNORECASE,
)


def _clean_claim_text(claim):
    if not isinstance(claim, str):
        return ""
    return claim.strip()


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_scoring_input_hash(ref_claim, infringing_claim, method=SCORE_METHOD, version=SCORE_VERSION):
    payload = f"{method}|{version}|{_clean_claim_text(ref_claim)}|{_clean_claim_text(infringing_claim)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_claim_number(claim_text: str) -> int | None:
    """Best-effort claim index from leading '1.' / 'Claim 1:' style prefixes."""
    text = _clean_claim_text(claim_text)
    if not text:
        return None
    match = _CLAIM_NUM_HEAD_RE.match(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _parse_num_chunk(chunk: str) -> list[int]:
    nums = [int(n) for n in _PARENT_NUM_RE.findall(chunk or "")]
    if not nums:
        return []
    if len(nums) == 2 and re.search(r"(?:-|–|—|\bto\b)", chunk, re.IGNORECASE):
        lo, hi = sorted(nums)
        return list(range(lo, hi + 1))
    return nums


def parse_parent_claim_numbers(claim_text: str) -> list[int]:
    """
    Parse dependent-claim parent references such as:
    'claim 1', 'claims 1 and 2', 'claims 1-3', 'claim 1 or 2'.
    """
    text = _clean_claim_text(claim_text)
    if not text:
        return []
    own = parse_claim_number(text)
    found: list[int] = []
    seen: set[int] = set()
    for match in _PARENT_REF_RE.finditer(text):
        for num in _parse_num_chunk(match.group(1) or ""):
            if own is not None and num == own:
                continue
            if num in seen:
                continue
            seen.add(num)
            found.append(num)
    return found


def classify_parent_relation(claim_text: str, parent_num: int) -> str:
    """
    Classify how claim_text relates to parent_num.

    Returns:
      'additive' | 'contrastive' | 'none'
    """
    text = _clean_claim_text(claim_text)
    if not text or parent_num is None:
        return "none"
    parents = parse_parent_claim_numbers(text)
    if parent_num not in parents:
        return "none"
    for match in _CONTRASTIVE_PARENT_RE.finditer(text):
        if parent_num in _parse_num_chunk(match.group(1) or ""):
            return "contrastive"
    # Patent dependents default to additive when they mention an earlier claim.
    return "additive"


def assign_claim_numbers(claims: list[str]) -> list[tuple[int, str]]:
    """
    Pair each claim with a 1-based number.

    Prefer a leading 'N.' / 'Claim N:' prefix; otherwise use list position
    (index + 1), matching portfolio dict keys '0'→1, '1'→2, …
    """
    cleaned = [_clean_claim_text(c) for c in (claims or []) if _clean_claim_text(c)]
    used: set[int] = set()
    out: list[tuple[int, str]] = []
    for idx, text in enumerate(cleaned):
        parsed = parse_claim_number(text)
        if parsed is not None and parsed not in used:
            num = parsed
        else:
            num = idx + 1
            while num in used:
                num += 1
        used.add(num)
        out.append((num, text))
    return out


def expand_claims_with_parents(claims: list[str]) -> tuple[list[str], dict[str, dict]]:
    """
    Expand reference claims for scoring (v3).

    For each claim i:
      1. Prepend additive parent claim texts (dependent → parent).
      2. Append all later claims (i+j, j>0) that additively mention i
         (forward fold: i + all additives). Contrastive mentions are skipped.

    Returns:
      expanded_list aligned with input claims,
      meta keyed by original claim text:
        {number, parents, additive_children, expanded, original}
    """
    numbered = assign_claim_numbers(claims)
    by_number: dict[int, str] = {}
    order: list[int] = []
    for num, text in numbered:
        if num not in by_number:
            by_number[num] = text
            order.append(num)

    text_to_number = {text: num for num, text in numbered}

    # Forward: parent_num -> later claim nums that additively mention it.
    additive_children: dict[int, list[int]] = {n: [] for n in order}
    for num in order:
        text = by_number[num]
        for parent_num in parse_parent_claim_numbers(text):
            if parent_num not in by_number:
                continue
            if parent_num >= num:
                # Only earlier claims are parents (X mentioned in X+j).
                continue
            if classify_parent_relation(text, parent_num) != "additive":
                continue
            kids = additive_children.setdefault(parent_num, [])
            if num not in kids:
                kids.append(num)

    meta: dict[str, dict] = {}
    expanded_list: list[str] = []

    def _expand_parents(text: str, stack: set[int]) -> str:
        num = text_to_number.get(text) or parse_claim_number(text)
        parents = parse_parent_claim_numbers(text)
        if not parents:
            return text
        parts: list[str] = []
        for parent_num in parents:
            if parent_num in stack:
                continue
            if classify_parent_relation(text, parent_num) != "additive":
                continue
            parent_text = by_number.get(parent_num)
            if not parent_text:
                continue
            next_stack = set(stack)
            if num is not None:
                next_stack.add(num)
            parts.append(_expand_parents(parent_text, next_stack))
        if not parts:
            return text
        uniq_parts: list[str] = []
        seen_parts: set[str] = set()
        for part in parts:
            key = part.strip()
            if not key or key in seen_parts or key == text:
                continue
            seen_parts.add(key)
            uniq_parts.append(part)
        if not uniq_parts:
            return text
        return "\n\n".join([*uniq_parts, text])

    for num, text in numbered:
        parents = [
            p
            for p in parse_parent_claim_numbers(text)
            if p < num and classify_parent_relation(text, p) == "additive"
        ]
        # Contrastive parents are recorded but not folded into scoring text.
        all_parents = parse_parent_claim_numbers(text)
        base = _expand_parents(text, set())
        child_nums = additive_children.get(num) or []
        child_texts = [by_number[c] for c in child_nums if c in by_number and by_number[c] != text]
        if child_texts:
            expanded = "\n\n".join([base, *child_texts])
        else:
            expanded = base
        expanded_list.append(expanded)
        meta[text] = {
            "number": num,
            "parents": parents,
            "all_parents": all_parents,
            "additive_children": list(child_nums),
            "original": text,
            "expanded": expanded,
        }
    return expanded_list, meta


def _apply_parent_consistency_gate(
    stored_rows: list[dict],
    chart_rows: list[dict],
    claim_meta: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """
    Drop dependent-claim hits unless at least one parent also hits the same
    infringing claim in this matrix pass.
    """
    if not stored_rows:
        return stored_rows, chart_rows

    number_to_original = {
        meta["number"]: original
        for original, meta in claim_meta.items()
        if meta.get("number") is not None
    }
    hits_by_inf: dict[str, set[str]] = {}
    for row in stored_rows:
        ref = _clean_claim_text(row.get("ref_claim", ""))
        inf = _clean_claim_text(row.get("claim", ""))
        if not ref or not inf:
            continue
        hits_by_inf.setdefault(inf, set()).add(ref)

    kept_stored: list[dict] = []
    kept_chart: list[dict] = []
    for row, chart in zip(stored_rows, chart_rows):
        ref = _clean_claim_text(row.get("ref_claim", ""))
        inf = _clean_claim_text(row.get("claim", ""))
        meta = claim_meta.get(ref) or {}
        parents = meta.get("parents") or []
        if not parents:
            kept_stored.append(row)
            kept_chart.append(chart)
            continue
        parent_originals = [
            number_to_original[p]
            for p in parents
            if p in number_to_original
        ]
        # If we cannot resolve any parents, keep the hit (fail-open on parse gaps).
        if not parent_originals:
            kept_stored.append(row)
            kept_chart.append(chart)
            continue
        hit_refs = hits_by_inf.get(inf) or set()
        if any(parent in hit_refs for parent in parent_originals):
            kept_stored.append(row)
            kept_chart.append(chart)
            continue
        print(
            "LOG: parent-gate dropped dependent hit "
            f"ref_num={meta.get('number')} parents={parents} "
            f"inf={inf[:80]!r}"
        )
    return kept_stored, kept_chart


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
    except Exception as e:
        print(f"LOG: _pair_scores_matrix_tfidf failed ({type(e).__name__}: {e})")
        return None


def _pair_scores_matrix(ref_list, inf_list):
    try:
        scores = _pair_scores_matrix_openai(ref_list, inf_list)
        if scores is not None:
            return scores
    except Exception as e:
        print(f"LOG: _pair_scores_matrix_openai failed ({type(e).__name__}: {e}); falling back to joint TF-IDF")
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


def score_infringement_matrix_entry(
    reference_claims,
    infringing_claims,
    existing_infringements,
    threshold=0.5,
    user_id=None,
    case_id=None,
):
    """
    Score reference × infringing claim pairs (embedding cosine, method v3).

    Each reference claim i is expanded for scoring by:
      - prepending additive parent claim text, and
      - appending all later claims that additively mention i (i + all additives).
    Contrastive mentions ("unlike claim i") are not folded in.
    Hits on dependents are kept only when at least one additive parent also
    scores above threshold against the same infringing claim. Stored/chart
    rows keep the original reference claim text.

    Reuses rows from existing_infringements when scoring_input_hash / method /
    version match. Otherwise embeds via data_processor and keeps pairs with
    calculated_similarity_score > threshold (default 0.5).

    When AI_WORKFLOW_MODE=rag and user_id+case_id are set, pair iteration may be
    shortlisted via shortlist_claim_pairs (full product if ≤200 pairs or on error).

    Returns:
        (stored_rows: list | None, chart_rows: list)
        stored_rows is None if there is nothing to persist (no infringing claims).
    """
    ref_list = [_clean_claim_text(c) for c in (reference_claims or []) if _clean_claim_text(c)]
    inf_list = [_clean_claim_text(c) for c in (infringing_claims or []) if _clean_claim_text(c)]
    if not ref_list or not inf_list:
        return None, []

    expanded_refs, claim_meta = expand_claims_with_parents(ref_list)
    # Map expanded scoring text -> original claim text for storage/UI.
    expanded_to_original: dict[str, str] = {}
    for original, meta in claim_meta.items():
        expanded = meta.get("expanded") or original
        expanded_to_original.setdefault(expanded, original)

    cache = _row_cache_map(existing_infringements if isinstance(existing_infringements, list) else [])
    # Cache keys are hashed on expanded ref text.
    full_cache = _fully_cached_matrix(
        [claim_meta[r]["expanded"] for r in ref_list],
        inf_list,
        existing_infringements,
        cache,
        threshold,
    )
    if full_cache is not None:
        stored_cached, chart_cached = full_cache
        rewritten_stored = []
        rewritten_chart = []
        for row, chart in zip(stored_cached, chart_cached):
            expanded_ref = _clean_claim_text(row.get("ref_claim", ""))
            original_ref = expanded_to_original.get(expanded_ref, expanded_ref)
            row = dict(row)
            row["ref_claim"] = original_ref
            chart = dict(chart)
            chart["ref_claim"] = original_ref
            rewritten_stored.append(row)
            rewritten_chart.append(chart)
        return _apply_parent_consistency_gate(rewritten_stored, rewritten_chart, claim_meta)

    pair_iter = product(expanded_refs, inf_list)
    try:
        from ai_workflow.config import is_rag_mode
        from ai_workflow.hybrid_retrieve import shortlist_claim_pairs

        if is_rag_mode():
            pair_iter = shortlist_claim_pairs(
                expanded_refs,
                inf_list,
                user_id=user_id,
                case_id=case_id,
            )
    except Exception as e:
        print(f"LOG: RAG shortlist skipped ({type(e).__name__}: {e})")
        pair_iter = product(expanded_refs, inf_list)

    # Materialize pairs so we only embed what's needed
    pair_list = list(pair_iter)
    needed_refs = sorted({r for r, _ in pair_list})
    needed_infs = sorted({i for _, i in pair_list})
    pair_scores = _pair_scores_matrix(needed_refs, needed_infs)
    if pair_scores is None:
        return None, []

    stored_rows = []
    chart_rows = []
    now_iso = _utc_now_iso()

    for expanded_ref, inf in pair_list:
        original_ref = expanded_to_original.get(expanded_ref, expanded_ref)
        h = build_scoring_input_hash(expanded_ref, inf)
        if h in cache and _cached_row_valid(cache[h], h):
            row = dict(cache[h])
            row["ref_claim"] = original_ref
            stored_rows.append(row)
            chart = _chart_row_from_storage(row)
            chart["ref_claim"] = original_ref
            chart_rows.append(chart)
            continue

        if (expanded_ref, inf) not in pair_scores:
            continue
        score = float(pair_scores[(expanded_ref, inf)])
        if score <= threshold:
            continue

        row = {
            "ref_claim": original_ref,
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
                "ref_claim": original_ref,
                "infringing_claim": inf,
                "similarity_score": score,
                "evaluation_method": SCORE_METHOD,
                "last_evaluated": now_iso,
            }
        )

    return _apply_parent_consistency_gate(stored_rows, chart_rows, claim_meta)
