"""Build patent-source search URLs from keyword lists."""


# FPO AND-style queries collapse when too many terms are joined with "+".
# Cap joined query size / term count and emit multiple shorter searches instead.
KEYWORD_QUERY_MAX_CHARS = 100
KEYWORD_QUERY_MAX_TERMS = 6
KEYWORD_QUERY_MAX_GROUPS = 5
# Cap merged result URLs so 5 groups do not explode detail-fetch + LLM cost.
KEYWORD_SEARCH_MAX_URLS = 75


def _normalize_keyword(keyword) -> str:
    if not isinstance(keyword, str):
        return ""
    return " ".join(keyword.split()).strip()


def _joined_query_length(terms: list[str]) -> int:
    """Length of the query string as built by free_patents_online / google_patents."""
    if not terms:
        return 0
    return len("+".join(t.replace(" ", "+") for t in terms))


def chunk_keywords_for_search(
    keywords: list[str] | None,
    max_chars: int = KEYWORD_QUERY_MAX_CHARS,
    max_terms: int = KEYWORD_QUERY_MAX_TERMS,
    max_groups: int = KEYWORD_QUERY_MAX_GROUPS,
) -> list[list[str]]:
    """
    Split keywords into short groups so each search URL stays under ~max_chars.

    Deduplicates (case-insensitive), preserves order, and caps the number of
    groups so analysis runtime does not explode.
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in keywords or []:
        term = _normalize_keyword(raw)
        if not term:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(term)

    if not cleaned:
        return []

    if _joined_query_length(cleaned) <= max_chars and len(cleaned) <= max_terms:
        return [cleaned]

    groups: list[list[str]] = []
    current: list[str] = []
    for term in cleaned:
        if len(groups) >= max_groups:
            break
        trial = current + [term]
        overflows = current and (
            _joined_query_length(trial) > max_chars or len(trial) > max_terms
        )
        if overflows:
            groups.append(current)
            current = [term]
        else:
            current = trial

    if current and len(groups) < max_groups:
        groups.append(current)

    used = sum(len(g) for g in groups)
    if used < len(cleaned):
        print(
            f"LOG: Keyword search truncated to {max_groups} groups "
            f"({used}/{len(cleaned)} keywords used; "
            f"max_chars={max_chars}, max_terms={max_terms})"
        )

    print(
        f"LOG: Split {len(cleaned)} keywords into {len(groups)} search group(s): "
        + "; ".join(f"[{i+1}] {' + '.join(g)}" for i, g in enumerate(groups))
    )
    return groups


class SearchUrlBuilderByKeywords:
    base_url: str

    def __init__(self, url: str):
        self.base_url = url

    def build_url(self, keywords: list[str], country: str, selector: str):
        if selector == "free-patents-online":
            return self.free_patents_online(keywords)
        if selector == "google-patents":
            return self.google_patents(keywords)
        return None

    def free_patents_online(self, keywords: list[str]):
        sort_param = "sort=relevance"
        keywords_merged = "+".join(keywords)
        keywords_merged = keywords_merged.replace(" ", "+")

        print(f"Free Patents Online keywords: {keywords_merged}")
        return f"{self.base_url}?{sort_param}&query_txt={keywords_merged}"

    def google_patents(self, keywords: list[str]):
        keywords_merged = "+".join(keywords)
        keywords_merged = keywords_merged.replace(" ", "+")
        print(f"Google Patents keywords: {keywords_merged}")

        q_value = f"q=({keywords_merged})"
        oq_value = f"oq={keywords_merged}"
        page_limit = "num=5000"

        return f"{self.base_url}/?{q_value}&{page_limit}&{oq_value}"
