"""
Data isolation for PDF reports.

Takes full case / folder payloads and returns narrow structures that
components can render without knowing Mongo shape details.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models.cases import get_case_by_id, get_unsorted_cases_for_user
from models.folders import get_folder
from models.notes import get_notes_for_case
from reports.styles import MATCH_TICK_THRESHOLD


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class NoteItem:
    section_type: str
    text: str
    entry_id: Optional[str] = None
    index: Optional[int] = None
    section_key: str = ''


@dataclass
class ClaimItem:
    index: int
    text: str
    claim_type: Optional[str] = None
    note: Optional[str] = None


@dataclass
class PatentInfo:
    case_id: str
    patent_id: str
    title: str
    inventors: List[str] = field(default_factory=list)
    assignees: List[str] = field(default_factory=list)
    filing_date: str = ''
    grant_date: str = ''
    description: str = ''
    keywords: List[str] = field(default_factory=list)
    context: str = ''
    search_limitations: str = ''
    source: str = ''
    url: str = ''
    notes: Dict[str, str] = field(default_factory=dict)  # section.type -> note text
    claim_notes: Dict[int, str] = field(default_factory=dict)  # claim index -> note


@dataclass
class InfringementHit:
    entry_id: str
    kind: str  # 'product' | 'patent'
    title: str
    source: str = ''
    url: str = ''
    posted_by: str = ''
    average_similarity: Optional[float] = None
    claims: List[ClaimItem] = field(default_factory=list)
    documents: List[Dict[str, Any]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    notes: Dict[str, str] = field(default_factory=dict)  # product / field notes
    claim_notes: Dict[int, str] = field(default_factory=dict)
    created_at: Optional[datetime] = None


@dataclass
class MatrixCell:
    ref_claim_index: int
    entry_id: str
    score: Optional[float]  # 0–1 unit score (feature avg or legacy embedding)
    matched: bool
    note: Optional[str] = None
    feature: str = ''


@dataclass
class MatrixFeatureRow:
    """One feature line inside a claim block (feature may be blank)."""
    feature: str
    cells: Dict[str, MatrixCell] = field(default_factory=dict)  # entry_id -> cell


@dataclass
class MatrixClaimBlock:
    """One reference claim with feature sub-rows for the claim matrix."""
    claim: ClaimItem
    feature_rows: List[MatrixFeatureRow] = field(default_factory=list)
    note: Optional[str] = None  # single-hit attorney note for this claim


@dataclass
class MatrixTable:
    """Ref claims × features × one or more hits (restructured claim matrix)."""
    claim_blocks: List[MatrixClaimBlock]
    hits: List[InfringementHit]
    include_notes_column: bool = False  # single-hit notes column
    attorney_notes: List[str] = field(default_factory=list)

    @property
    def ref_claims(self) -> List[ClaimItem]:
        return [block.claim for block in self.claim_blocks]


@dataclass
class ChartRow:
    ref_claim_index: Optional[int]
    ref_claim: str
    inf_claim: str
    similarity: Optional[float]
    justification: str = ''
    note: Optional[str] = None


@dataclass
class ChartTable:
    entry_id: str
    hit_title: str
    rows: List[ChartRow]
    attorney_notes: List[str] = field(default_factory=list)


@dataclass
class IndexEntry:
    """One index row: id | title/subtitle | page (page filled via marker → page_map)."""
    entry_id: str = ''
    title: str = ''
    level: int = 0  # 0 = primary, 1 = subtitle row (e.g. Claim Chart)
    marker: str = ''  # bookmark / page-map key


@dataclass
class PortfolioChapterPlan:
    case_id: str
    patent: PatentInfo
    hits: List[InfringementHit]
    mode: str  # 'single' | 'multi'


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _parse_datetime(value) -> Optional[datetime]:
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip()
    if not text:
        return None
    # Normalize common ISO / mongo suffixes
    normalized = text.replace('+00:00', '')
    if normalized.endswith('Z'):
        normalized = normalized[:-1]
    for fmt in (
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
    ):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except Exception:
        return None


def format_generated_date(when: Optional[datetime] = None) -> str:
    """Cover-page style: '24, Tuesday, Nov 2026'."""
    when = when or datetime.now()
    return f'{when.day}, {when.strftime("%A, %b %Y")}'


def format_header_date(when: Optional[datetime] = None) -> str:
    when = when or datetime.now()
    return when.strftime('%Y-%m-%d')


def extract_patent_id(case: dict) -> str:
    """Human patent id (not Mongo case _id). Prefer explicit fields, else last _id segment."""
    for key in ('patent_id', 'patentId', 'patent_number', 'patentNumber', 'publication_number'):
        val = _clean_text(case.get(key))
        if val:
            return val
    case_id = _clean_text(case.get('_id') or case.get('id') or '')
    if '_' in case_id:
        return case_id.split('_')[-1]
    return case_id or '—'


def strip_claim_number_prefix(text: str) -> str:
    """Remove leading ``N.`` / ``N)`` numbering when the report already labels Claim N."""
    if not text:
        return ''
    return re.sub(r'^\s*\d+\s*[\.\)\:\-]\s*', '', text.strip()).strip()


def claim_documented_text(claim_obj, *, flag: Optional[str] = None) -> str:
    """
    Resolve claim text from string or object form.

    ``flag='market'`` prefers market_language_claim (UI parity with
    ``getReferenceClaimText``); otherwise documented first.
    """
    if claim_obj is None:
        return ''
    if isinstance(claim_obj, str):
        return claim_obj.strip()
    if isinstance(claim_obj, dict):
        if (flag or '').strip().lower() == 'market':
            return _clean_text(
                claim_obj.get('market_language_claim')
                or claim_obj.get('documented_claim')
                or claim_obj.get('claim')
                or claim_obj.get('text')
            )
        return _clean_text(
            claim_obj.get('documented_claim')
            or claim_obj.get('market_language_claim')
            or claim_obj.get('claim')
            or claim_obj.get('text')
        )
    return _clean_text(claim_obj)


def _claims_raw_as_ordered_pairs(raw) -> List[Tuple[int, Any]]:
    """
    Normalize case/hit ``claims`` into ``(index, claim_obj)`` pairs.

    Supports:
    - list of strings / objects
    - dict keyed by index (int or str) → claim object  (common demo shape)
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [(i, c) for i, c in enumerate(raw)]
    if isinstance(raw, dict):
        def _sort_key(k):
            try:
                return (0, int(k))
            except (TypeError, ValueError):
                return (1, str(k))

        pairs: List[Tuple[int, Any]] = []
        for k in sorted(raw.keys(), key=_sort_key):
            try:
                idx = int(k)
            except (TypeError, ValueError):
                idx = len(pairs)
            pairs.append((idx, raw[k]))
        return pairs
    return []


def get_reference_claim_text(
    claims_data,
    ref_claim_index,
    ref_claim_flag: Optional[str] = None,
) -> str:
    """
    UI-parity resolver for a chart/matrix row's reference claim text.
    Does not mutate stored case data.
    """
    if claims_data is None or ref_claim_index is None:
        return ''
    try:
        idx = int(ref_claim_index)
    except (TypeError, ValueError):
        return ''

    claim_obj = None
    if isinstance(claims_data, list):
        if 0 <= idx < len(claims_data):
            claim_obj = claims_data[idx]
    elif isinstance(claims_data, dict):
        claim_obj = claims_data.get(idx)
        if claim_obj is None:
            claim_obj = claims_data.get(str(idx))

    if claim_obj is None:
        return ''

    text = claim_documented_text(claim_obj, flag=ref_claim_flag)
    return strip_claim_number_prefix(text)


def extract_claims(case_or_entry: dict, *, prefer_documented: bool = True) -> List[ClaimItem]:
    """
    Build renderable claim rows from list- or dict-shaped ``claims``.
    Strips leading claim numbers from body text (label is added in components).
    """
    raw = (case_or_entry or {}).get('claims')
    items: List[ClaimItem] = []
    flag = None if prefer_documented else 'market'
    for idx, c in _claims_raw_as_ordered_pairs(raw):
        text = claim_documented_text(c, flag=flag)
        if not text and isinstance(c, dict):
            text = _clean_text(c.get('market_language_claim') or c.get('documented_claim'))
        text = strip_claim_number_prefix(text)
        ctype = None
        if isinstance(c, dict):
            ctype = _clean_text(c.get('claim_type') or c.get('type')) or None
        items.append(ClaimItem(index=idx, text=text or '—', claim_type=ctype))
    return items


def _person_name(value) -> str:
    """Flatten inventor/assignee entries that may be strings or dicts."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return _clean_text(
            value.get('inventorNameText')
            or value.get('name')
            or value.get('inventor')
            or value.get('assignee')
            or value.get('text')
        )
    return _clean_text(value)


def classify_hit(entry: dict) -> str:
    if not isinstance(entry, dict):
        return 'patent'
    if entry.get('product_id') or entry.get('product_name'):
        return 'product'
    return 'patent'


def hit_entry_id(entry: dict) -> str:
    if not isinstance(entry, dict):
        return ''
    for key in ('product_id', 'entry_id', 'case_id', '_id', 'id'):
        val = entry.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    title = entry.get('product_name') or entry.get('entry_title') or entry.get('title')
    return _clean_text(title) or 'unknown'


def hit_title(entry: dict) -> str:
    if not isinstance(entry, dict):
        return 'Untitled'
    return _clean_text(
        entry.get('product_name')
        or entry.get('entry_title')
        or entry.get('title')
        or entry.get('name')
    ) or 'Untitled'


def hit_url(entry: dict) -> str:
    if not isinstance(entry, dict):
        return ''
    docs = entry.get('documents') or []
    doc0 = docs[0] if isinstance(docs, list) and docs else {}
    return _clean_text(
        entry.get('product_url')
        or entry.get('entry_url')
        or entry.get('url')
        or (doc0.get('url') if isinstance(doc0, dict) else '')
        or ((entry.get('document_urls') or [None])[0])
    )


def hit_timestamp(entry: dict) -> Optional[datetime]:
    if not isinstance(entry, dict):
        return None
    for key in ('created_at', 'created_on', 'created_date', 'last_updated', 'updated_at', 'updated_date'):
        parsed = _parse_datetime(entry.get(key))
        if parsed:
            return parsed
    return None


def average_similarity_for_entry(entry: dict) -> Optional[float]:
    """Mean of nested matrix/chart scores for one infringement entry."""
    if not isinstance(entry, dict):
        return None
    scores: List[float] = []
    nested = entry.get('infringements') or []
    if isinstance(nested, list):
        for row in nested:
            if not isinstance(row, dict):
                continue
            s = row.get('calculated_similarity_score')
            if isinstance(s, (int, float)):
                scores.append(float(s))
    similar = entry.get('similar_claims') or []
    if isinstance(similar, list):
        for row in similar:
            if not isinstance(row, dict):
                continue
            s = row.get('similarity_score')
            if isinstance(s, (int, float)):
                scores.append(float(s))
    if not scores:
        top = entry.get('similarity_score') or entry.get('average_similarity') or entry.get('risk_score')
        if isinstance(top, (int, float)):
            return float(top)
        return None
    return sum(scores) / len(scores)


def notes_by_key(case_id: str) -> Dict[str, dict]:
    """Map section_key -> note document for a case."""
    result = get_notes_for_case(case_id)
    notes = (result or {}).get('notes') or []
    out: Dict[str, dict] = {}
    for n in notes:
        if not isinstance(n, dict):
            continue
        key = n.get('section_key')
        if key:
            out[str(key)] = n
    return out


def _note_text(notes_map: Dict[str, dict], key: str) -> Optional[str]:
    doc = notes_map.get(key)
    if not doc:
        return None
    text = _clean_text(doc.get('note'))
    return text or None


# ---------------------------------------------------------------------------
# High-level extractors
# ---------------------------------------------------------------------------

def extract_patent_info(case: dict, notes_map: Optional[Dict[str, dict]] = None) -> PatentInfo:
    case_id = str(case.get('_id') or case.get('id') or '')
    notes_map = notes_map if notes_map is not None else (notes_by_key(case_id) if case_id else {})

    field_notes = {}
    for stype in (
        'description', 'title', 'inventors', 'keywords', 'context', 'search_limitations',
    ):
        t = _note_text(notes_map, stype)
        if t:
            field_notes[stype] = t

    claim_notes = {}
    for key, doc in notes_map.items():
        if key.startswith('claim:') and not key.startswith('claim_chart') and not key.startswith('claim_matrix'):
            try:
                idx = int(key.split(':', 1)[1])
            except Exception:
                continue
            text = _clean_text(doc.get('note'))
            if text:
                claim_notes[idx] = text

    assignees_raw = _as_list(
        case.get('current_assignee')
        or case.get('assignees')
        or case.get('assignee')
        or case.get('assigneeBag')
    )
    inventors_raw = _as_list(
        case.get('inventors')
        or case.get('inventor')
        or case.get('inventorBag')
    )
    inventors = [_person_name(x) for x in inventors_raw if _person_name(x)]
    assignees = [_person_name(x) for x in assignees_raw if _person_name(x)]

    filing_date = _clean_text(
        case.get('filingDate')
        or case.get('filing_date')
        or case.get('filedAt')
        or case.get('applicationDate')
    )
    grant_date = _clean_text(
        case.get('grantDate')
        or case.get('grant_date')
        or case.get('granted_date')
        or case.get('grantedDate')
        or case.get('issueDate')
        or case.get('issue_date')
        or case.get('publicationDate')
        or case.get('publication_date')
        or case.get('currentStatusDate')
        or case.get('current_status_date')
    )

    return PatentInfo(
        case_id=case_id,
        patent_id=extract_patent_id(case),
        title=_clean_text(case.get('title')) or 'Untitled Patent',
        inventors=inventors,
        assignees=assignees,
        filing_date=filing_date,
        grant_date=grant_date,
        description=_clean_text(case.get('description') or case.get('abstract')),
        keywords=[_clean_text(k) for k in _as_list(case.get('keywords')) if _clean_text(k)],
        context=_clean_text(case.get('context')),
        search_limitations=_clean_text(case.get('search_limitations')),
        source=_clean_text(case.get('source')),
        url=_clean_text(case.get('url') or case.get('source_url')),
        notes=field_notes,
        claim_notes=claim_notes,
    )


def extract_hit(
    entry: dict,
    *,
    notes_map: Optional[Dict[str, dict]] = None,
) -> InfringementHit:
    eid = hit_entry_id(entry)
    kind = classify_hit(entry)
    notes_map = notes_map or {}

    field_notes: Dict[str, str] = {}
    product_note = _note_text(notes_map, f'product:{eid}')
    if product_note:
        field_notes['product'] = product_note

    claim_notes: Dict[int, str] = {}
    prefix = f'product_claim:{eid}:'
    for key, doc in notes_map.items():
        if key.startswith(prefix):
            try:
                idx = int(key.rsplit(':', 1)[-1])
            except Exception:
                continue
            text = _clean_text(doc.get('note'))
            if text:
                claim_notes[idx] = text

    claims = extract_claims(entry)
    for c in claims:
        if c.index in claim_notes:
            c.note = claim_notes[c.index]

    docs = []
    for d in _as_list(entry.get('documents')):
        if isinstance(d, dict):
            docs.append(d)
    for u in _as_list(entry.get('document_urls')):
        if u:
            docs.append({'url': u, 'title': u})

    return InfringementHit(
        entry_id=eid,
        kind=kind,
        title=hit_title(entry),
        source=_clean_text(entry.get('source') or (docs[0].get('source') if docs else '')),
        url=hit_url(entry),
        posted_by=_clean_text(entry.get('posted_by') or entry.get('seller') or entry.get('author')),
        average_similarity=average_similarity_for_entry(entry),
        claims=claims,
        documents=docs,
        raw=entry if isinstance(entry, dict) else {},
        notes=field_notes,
        claim_notes=claim_notes,
        created_at=hit_timestamp(entry),
    )


def find_infringement_entry(case: dict, infringement_id: str) -> Optional[dict]:
    target = str(infringement_id).strip()
    for entry in case.get('infringements') or []:
        if not isinstance(entry, dict):
            continue
        candidates = {
            str(entry.get('product_id') or '').strip(),
            str(entry.get('entry_id') or '').strip(),
            str(entry.get('case_id') or '').strip(),
            str(entry.get('_id') or '').strip(),
            str(entry.get('id') or '').strip(),
        }
        if target in candidates:
            return entry
        # fuzzy: title match as last resort
        if target and target.lower() in (hit_title(entry) or '').lower():
            return entry
    return None


def filter_hits_by_kind(entries: Sequence[dict], kind: str) -> List[dict]:
    """kind: 'product' | 'patent' | 'all' | 'mixed'."""
    kind = (kind or 'all').lower()
    out = []
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        k = classify_hit(e)
        if kind in ('all', 'mixed'):
            out.append(e)
        elif kind in ('product', 'products') and k == 'product':
            out.append(e)
        elif kind in ('patent', 'patents') and k == 'patent':
            out.append(e)
    return out


def filter_new_infringements(
    case: dict,
    *,
    since: Optional[datetime] = None,
) -> List[dict]:
    """
    Hits whose created_at / last_updated is after ``since``
    (default: case.last_infringement_analysis_date).

    If no baseline date exists, every hit is treated as new.
    Hits with no timestamp are included when a baseline exists only if
    they cannot be proven older — they are included so documentation
    reports do not silently drop untimestamped rows; prefer stamping
    hits at write time.
    """
    baseline = since or _parse_datetime(case.get('last_infringement_analysis_date'))
    entries = [e for e in (case.get('infringements') or []) if isinstance(e, dict)]
    if baseline is None:
        return entries
    new_hits = []
    for e in entries:
        ts = hit_timestamp(e)
        if ts is None or ts > baseline:
            new_hits.append(e)
    return new_hits


def _score_for_ref_vs_entry(entry: dict, ref_index: int) -> Optional[float]:
    """Best similarity for a reference claim index against one hit."""
    best: Optional[float] = None

    nested = entry.get('infringements') or []
    if isinstance(nested, list):
        for row in nested:
            if not isinstance(row, dict):
                continue
            # Prefer explicit index when present
            idx = row.get('ref_claim_index')
            if idx is not None and int(idx) != int(ref_index):
                continue
            s = row.get('calculated_similarity_score')
            if isinstance(s, (int, float)):
                # If no index, match by ref_claim text later; accept positional loosely
                if idx is not None or best is None:
                    val = float(s)
                    if best is None or val > best:
                        best = val

    similar = entry.get('similar_claims') or []
    if isinstance(similar, list):
        for row in similar:
            if not isinstance(row, dict):
                continue
            idx = row.get('ref_claim_index')
            if idx is not None and int(idx) != int(ref_index):
                continue
            if idx is None and len(similar) > ref_index:
                # positional fallback only when looking at same index slot
                row = similar[ref_index] if ref_index < len(similar) else row
                if not isinstance(row, dict):
                    continue
            s = row.get('similarity_score')
            if isinstance(s, (int, float)):
                val = float(s)
                if best is None or val > best:
                    best = val
                if idx is None:
                    break
    return best


def _normalize_feature_key(text: str) -> str:
    return ' '.join((text or '').strip().lower().split())


def _features_for_ref_claim(case: dict, ref_index: int) -> List[str]:
    """Features for a reference claim from claim_features or claims[*].features."""
    cache = (case or {}).get('claim_features') or {}
    if isinstance(cache, dict):
        raw = cache.get(str(ref_index))
        if raw is None:
            raw = cache.get(ref_index)
        if isinstance(raw, list):
            cleaned = [_clean_text(f) for f in raw if _clean_text(f)]
            if cleaned:
                return cleaned
    claims = (case or {}).get('claims')
    if isinstance(claims, dict):
        entry = claims.get(str(ref_index))
        if entry is None:
            entry = claims.get(ref_index)
        if isinstance(entry, dict):
            raw = entry.get('features')
            if isinstance(raw, list):
                cleaned = [_clean_text(f) for f in raw if _clean_text(f)]
                if cleaned:
                    return cleaned
    return []


def _feature_matrix_rows(case: dict) -> List[dict]:
    raw = (case or {}).get('feature_matrix')
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def _feature_pct_to_unit(value) -> Optional[float]:
    """Convert feature_matrix percentage (0–100) or unit score to 0–1."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v > 1.0:
        v = v / 100.0
    if v < 0:
        return None
    return v


def _average_feature_score_for_product(
    feature_rows: Sequence[dict],
    *,
    ref_claim_index: int,
    feature: str,
    product_id: str,
) -> Optional[float]:
    """
    Mean of (feature × product-claim) unit scores for one product.

    Scores at or below CLAIM_SIMILARITY_THRESHOLD (0.10) are excluded,
    matching claim-matrix filtering.
    """
    from infringement_score_filters import score_meets_threshold

    if not feature or not product_id:
        return None
    feat_key = _normalize_feature_key(feature)
    pid = str(product_id).strip()
    scores: List[float] = []
    for row in feature_rows:
        try:
            idx = int(row.get('ref_claim_index'))
        except (TypeError, ValueError):
            continue
        if idx != int(ref_claim_index):
            continue
        if str(row.get('product_id') or '').strip() != pid:
            continue
        if _normalize_feature_key(str(row.get('feature') or '')) != feat_key:
            continue
        unit = _feature_pct_to_unit(row.get('possible_infringement_percentage'))
        if unit is None:
            continue
        if score_meets_threshold(unit):
            scores.append(unit)
    if not scores:
        return None
    return sum(scores) / len(scores)


def build_matrix(
    case: dict,
    entries: Sequence[dict],
    notes_map: Optional[Dict[str, dict]] = None,
    *,
    single_hit_notes_column: bool = False,
) -> MatrixTable:
    """
    Build the claim matrix as claim × feature × hit cells.

    Product cell values are averages of feature_matrix scores for that
    feature vs each of the product's claims (excluding scores ≤ 0.10).
    Tick/cross still uses MATCH_TICK_THRESHOLD (0.8).
    """
    notes_map = notes_map or {}
    ref_claims = extract_claims(case)
    hits = [extract_hit(e, notes_map=notes_map) for e in entries]
    fm_rows = _feature_matrix_rows(case)
    attorney_notes: List[str] = []
    any_inline_note = False
    claim_blocks: List[MatrixClaimBlock] = []

    for claim in ref_claims:
        features = _features_for_ref_claim(case, claim.index)
        # Rare: no features → one blank feature row (legacy claim score fallback).
        feature_labels = features if features else ['']

        claim_note = ''
        if len(hits) == 1:
            claim_note = (
                _note_text(notes_map, f'claim_matrix:{hits[0].entry_id}:{claim.index}')
                or _note_text(notes_map, f'claim_chart:{hits[0].entry_id}:{claim.index}')
            )
            if claim_note:
                any_inline_note = True
                attorney_notes.append(
                    f'claim {claim.index + 1} - {hits[0].entry_id} : {claim_note}'
                )
        else:
            for hit in hits:
                note = (
                    _note_text(notes_map, f'claim_matrix:{hit.entry_id}:{claim.index}')
                    or _note_text(notes_map, f'claim_chart:{hit.entry_id}:{claim.index}')
                )
                if note:
                    attorney_notes.append(
                        f'claim {claim.index + 1} - {hit.entry_id} : {note}'
                    )

        feature_rows: List[MatrixFeatureRow] = []
        for feature in feature_labels:
            cells: Dict[str, MatrixCell] = {}
            for hit, entry in zip(hits, entries):
                if feature:
                    score = _average_feature_score_for_product(
                        fm_rows,
                        ref_claim_index=claim.index,
                        feature=feature,
                        product_id=hit.entry_id,
                    )
                else:
                    # No features extracted — fall back to claim-level embedding score.
                    score = _score_for_ref_vs_entry(entry, claim.index)
                matched = score is not None and score >= MATCH_TICK_THRESHOLD
                cells[hit.entry_id] = MatrixCell(
                    ref_claim_index=claim.index,
                    entry_id=hit.entry_id,
                    score=score,
                    matched=matched,
                    note=claim_note or None,
                    feature=feature,
                )
            feature_rows.append(MatrixFeatureRow(feature=feature, cells=cells))

        claim_blocks.append(
            MatrixClaimBlock(
                claim=claim,
                feature_rows=feature_rows,
                note=claim_note or None,
            )
        )

    return MatrixTable(
        claim_blocks=claim_blocks,
        hits=hits,
        include_notes_column=bool(
            single_hit_notes_column and any_inline_note and len(hits) == 1
        ),
        attorney_notes=attorney_notes,
    )


def build_claim_chart(
    case: dict,
    entry: dict,
    notes_map: Optional[Dict[str, dict]] = None,
) -> ChartTable:
    notes_map = notes_map or {}
    hit = extract_hit(entry, notes_map=notes_map)
    claims_data = (case or {}).get('claims')
    rows: List[ChartRow] = []
    attorney_notes: List[str] = []

    def _resolve_ref(row: dict, fallback_index: int) -> Tuple[Optional[int], str]:
        idx = row.get('ref_claim_index')
        if idx is None:
            idx = fallback_index
        try:
            idx_i = int(idx)
        except Exception:
            idx_i = fallback_index
        flag = row.get('ref_claim_flag') or row.get('ref_claim_type')
        ref_text = get_reference_claim_text(claims_data, idx_i, flag)
        if not ref_text:
            ref_text = strip_claim_number_prefix(_clean_text(row.get('ref_claim')))
        return idx_i, ref_text

    # Prefer similar_claims (product-style with justification)
    similar = entry.get('similar_claims')
    if isinstance(similar, list) and similar:
        for i, row in enumerate(similar):
            if not isinstance(row, dict):
                continue
            idx_i, ref_text = _resolve_ref(row, i)
            inf_text = strip_claim_number_prefix(
                claim_documented_text(row.get('claim') or row.get('infringing_claim') or '')
            )
            sim = row.get('similarity_score')
            if not isinstance(sim, (int, float)):
                sim = row.get('calculated_similarity_score')
            sim_f = float(sim) if isinstance(sim, (int, float)) else None
            note = _note_text(notes_map, f'claim_chart:{hit.entry_id}:{idx_i}')
            if note:
                attorney_notes.append(f'claim {idx_i + 1} - {hit.entry_id} : {note}')
            rows.append(ChartRow(
                ref_claim_index=idx_i,
                ref_claim=ref_text or '—',
                inf_claim=inf_text or '—',
                similarity=sim_f,
                justification=_clean_text(row.get('justification')),
                note=note,
            ))
    else:
        nested = entry.get('infringements') or []
        if isinstance(nested, list):
            for i, row in enumerate(nested):
                if not isinstance(row, dict):
                    continue
                idx_i, ref_text = _resolve_ref(row, i)
                inf_text = strip_claim_number_prefix(
                    claim_documented_text(row.get('claim') or row.get('infringing_claim') or '')
                )
                sim = row.get('calculated_similarity_score')
                if not isinstance(sim, (int, float)):
                    sim = row.get('similarity_score')
                sim_f = float(sim) if isinstance(sim, (int, float)) else None
                note = (
                    _note_text(notes_map, f'claim_chart:{hit.entry_id}:{idx_i}')
                    or _note_text(notes_map, f'claim_matrix:{hit.entry_id}:{idx_i}')
                )
                if note:
                    attorney_notes.append(f'claim {idx_i + 1} - {hit.entry_id} : {note}')
                rows.append(ChartRow(
                    ref_claim_index=idx_i,
                    ref_claim=ref_text or '—',
                    inf_claim=inf_text or '—',
                    similarity=sim_f,
                    justification=_clean_text(row.get('justification')),
                    note=note,
                ))

    return ChartTable(
        entry_id=hit.entry_id,
        hit_title=hit.title,
        rows=rows,
        attorney_notes=attorney_notes,
    )


def load_case_bundle(case_id: str) -> Tuple[dict, PatentInfo, Dict[str, dict]]:
    case = get_case_by_id(case_id)
    if not case:
        raise ValueError(f'Case not found: {case_id}')
    notes_map = notes_by_key(str(case.get('_id') or case_id))
    patent = extract_patent_info(case, notes_map)
    return case, patent, notes_map


def header_title_patent_vs(patent_id: str, infringement_id: str) -> str:
    return f'{patent_id} vs {infringement_id} Infringement Report'


def header_title_hit_kind(patent_id: str, kind: str) -> str:
    kind = (kind or '').lower()
    if kind in ('product', 'products'):
        return f'{patent_id} Products Infringements Report'
    if kind in ('patent', 'patents'):
        return f'{patent_id} Patents Infringements Report'
    # mixed / all
    return f'{patent_id} Product And Patent Infringement Report'


def mixed_kind_label(hits: Sequence[InfringementHit]) -> str:
    kinds = {h.kind for h in hits}
    if kinds == {'product'}:
        return 'products'
    if kinds == {'patent'}:
        return 'patents'
    return 'mixed'


def resolve_portfolio_cases(user_id: str, folder_id: str) -> Tuple[str, List[str]]:
    """
    Returns (portfolio_display_name, ordered case_ids).
    folder_id='unsorted' uses cases with no folder membership.
    """
    folder_key = (folder_id or '').strip()
    if not folder_key:
        raise ValueError('folder_id is required')

    if folder_key.lower() == 'unsorted':
        unsorted = get_unsorted_cases_for_user(user_id, include_fields=['_id'])
        case_ids = [str(c.get('_id')) for c in (unsorted or []) if c.get('_id')]
        return 'unsorted', case_ids

    folder = get_folder(folder_key)
    if not folder:
        raise ValueError(f'Folder not found: {folder_key}')
    name = _clean_text(folder.get('name')) or folder_key
    case_ids = [str(cid) for cid in (folder.get('cases') or []) if cid]
    return name, case_ids


def plan_whats_new_chapters(
    user_id: str,
    folder_id: str,
    *,
    since: Optional[datetime] = None,
) -> Tuple[str, List[PortfolioChapterPlan]]:
    portfolio_name, case_ids = resolve_portfolio_cases(user_id, folder_id)
    chapters: List[PortfolioChapterPlan] = []
    for cid in case_ids:
        case = get_case_by_id(cid)
        if not case:
            continue
        new_entries = filter_new_infringements(case, since=since)
        if not new_entries:
            continue
        notes_map = notes_by_key(str(case.get('_id') or cid))
        patent = extract_patent_info(case, notes_map)
        hits = [extract_hit(e, notes_map=notes_map) for e in new_entries]
        mode = 'single' if len(hits) == 1 else 'multi'
        chapters.append(PortfolioChapterPlan(
            case_id=str(case.get('_id') or cid),
            patent=patent,
            hits=hits,
            mode=mode,
        ))
    return portfolio_name, chapters


# ---------------------------------------------------------------------------
# Document / listing page loaders (report-time only; no case DB writes)
# ---------------------------------------------------------------------------

def _coerce_pdf_bytes(raw) -> Optional[bytes]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    # Mongo Binary / memoryview
    try:
        return bytes(raw)
    except Exception:
        return None


def load_pdf_document_pages(pdf_bytes: bytes) -> bytes:
    """
    Load a PDF document and return PDF bytes suitable for appending.

    Validates the payload is a readable PDF. Returns the original bytes when
    valid; raises ValueError if empty or unreadable.
    """
    data = _coerce_pdf_bytes(pdf_bytes)
    if not data:
        raise ValueError('Empty PDF payload')
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(__import__('io').BytesIO(data))
        if len(reader.pages) < 1:
            raise ValueError('PDF has no pages')
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f'Unreadable PDF: {e}') from e
    return data


class ListingFetchBlockedError(Exception):
    """Raised when Chromium cannot return usable listing content (GET fallback off)."""

    def __init__(
        self,
        url: str,
        *,
        chromium_reason: str = '',
        get_reason: str = '',
    ):
        self.url = url
        self.chromium_reason = chromium_reason
        self.get_reason = get_reason
        detail = '; '.join(
            p for p in (
                f'Chromium: {chromium_reason}' if chromium_reason else '',
                f'GET: {get_reason}' if get_reason else '',
            ) if p
        )
        super().__init__(f'Listing fetch blocked for {url}' + (f' ({detail})' if detail else ''))


_BLOCKED_PAGE_MARKERS = (
    'access denied',
    "don't have permission to access",
    'you don\'t have permission',
    'errors.edgesuite.net',
    'pardon our interruption',
    'cf-browser-verification',
    'checking your browser before accessing',
    'attention required! | cloudflare',
    'enable javascript and cookies to continue',
    'request blocked',
    '403 forbidden',
    'http error 403',
)

_BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/122.0.0.0 Safari/537.36'
)


def _text_looks_blocked(text: str) -> bool:
    low = (text or '').lower()
    if not low.strip():
        return False
    return any(m in low for m in _BLOCKED_PAGE_MARKERS)


def _text_looks_blank(text: str, *, min_chars: int = 80) -> bool:
    compact = re.sub(r'\s+', ' ', (text or '')).strip()
    return len(compact) < min_chars


def _page_text_sample(page) -> str:
    try:
        title = page.title() or ''
    except Exception:
        title = ''
    try:
        body = page.evaluate(
            """() => {
              const t = (document.body && document.body.innerText) || '';
              return t.replace(/\\s+/g, ' ').trim();
            }"""
        ) or ''
    except Exception:
        body = ''
    return f'{title}\n{body}'.strip()


def _pdf_text_sample(pdf_bytes: bytes, *, max_pages: int = 2) -> str:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(__import__('io').BytesIO(pdf_bytes))
        chunks = []
        for page in reader.pages[:max_pages]:
            chunks.append(page.extract_text() or '')
        return '\n'.join(chunks).strip()
    except Exception:
        return ''


def _chromium_pdf_options() -> dict:
    return {
        'format': 'A4',
        'print_background': True,
        'margin': {'top': '12mm', 'bottom': '12mm', 'left': '10mm', 'right': '10mm'},
    }


def _http_get_listing(
    url: str,
    *,
    timeout_s: float = 30.0,
) -> Tuple[int, str, str]:
    """
    Plain HTTP GET fallback for listing pages.

    Returns ``(status_code, content_type, body_text_or_html)``.
    """
    import requests

    headers = {
        'User-Agent': _BROWSER_UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    resp = requests.get(url, headers=headers, timeout=timeout_s, allow_redirects=True)
    ctype = (resp.headers.get('Content-Type') or '').split(';')[0].strip().lower()
    # Decode as text for inspection / HTML reprint
    try:
        text = resp.text or ''
    except Exception:
        text = ''
    return int(resp.status_code), ctype, text


def _html_response_usable(status: int, content_type: str, body: str) -> Tuple[bool, str]:
    if status >= 400:
        return False, f'HTTP {status}'
    if _text_looks_blocked(body):
        return False, 'blocked/WAF page in GET body'
    # Prefer HTML-ish responses; allow empty content-type
    if content_type and ('html' not in content_type) and ('text/' not in content_type) and ('xml' not in content_type):
        return False, f'non-HTML content-type {content_type!r}'
    # Strip tags for blank check
    plain = re.sub(r'<script[\s\S]*?</script>', ' ', body, flags=re.I)
    plain = re.sub(r'<style[\s\S]*?</style>', ' ', plain, flags=re.I)
    plain = re.sub(r'<[^>]+>', ' ', plain)
    if _text_looks_blank(plain):
        return False, 'empty/near-empty GET body'
    return True, ''


def _render_html_string_as_pdf(
    html: str,
    *,
    base_url: str,
    timeout_ms: int = 45000,
) -> bytes:
    """Print fetched HTML via Chromium ``set_content`` (no live navigation)."""
    from playwright.sync_api import sync_playwright

    # Help relative assets resolve when possible
    injected = html
    if base_url and '<base ' not in html.lower():
        injected = re.sub(
            r'(<head[^>]*>)',
            rf'\1<base href="{base_url}">',
            html,
            count=1,
            flags=re.I,
        )
        if injected == html:
            injected = '<base href="' + base_url + '">' + html

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=_BROWSER_UA)
            page.set_content(injected, wait_until='load', timeout=timeout_ms)
            page.wait_for_timeout(800)
            sample = _page_text_sample(page)
            if _text_looks_blocked(sample) or _text_looks_blank(sample):
                raise ValueError('GET HTML rendered blank or blocked in Chromium')
            pdf_bytes = page.pdf(**_chromium_pdf_options())
        finally:
            browser.close()
    if not pdf_bytes:
        raise ValueError('Chromium returned empty PDF for GET HTML')
    return pdf_bytes


def load_html_listing_as_pdf_pages(
    url: str,
    *,
    timeout_ms: int = 45000,
    wait_until: str = 'load',
) -> bytes:
    """
    Open a product listing URL and return PDF pages.

    1. Headless Chromium navigation (preferred for JS-rendered pages).
    2. If the result is blank / Access Denied / WAF interstitial, raise
       ``ListingFetchBlockedError`` so callers can list the URL for manual
       access instead of appending empty pages.

    Note: plain HTTP GET fallback is disabled for now — it produced poor
    layouts vs rendered pages. Helpers remain below if we re-enable later.
    """
    target = _clean_text(url)
    if not target:
        raise ValueError('Listing URL is empty')
    if not target.startswith(('http://', 'https://')):
        raise ValueError(f'Unsupported listing URL scheme: {target}')

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            'playwright is required for HTML listing → PDF. '
            'Install with: pip install playwright && playwright install chromium'
        ) from e

    chromium_reason = ''
    pdf_bytes: Optional[bytes] = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=_BROWSER_UA)
            http_status = None
            try:
                resp = page.goto(target, wait_until=wait_until, timeout=timeout_ms)
                http_status = resp.status if resp else None
            except Exception:
                # Fallback: accept partial load rather than failing immediately
                try:
                    resp = page.goto(target, wait_until='domcontentloaded', timeout=timeout_ms)
                    http_status = resp.status if resp else None
                except Exception as e:
                    chromium_reason = f'navigation failed: {e}'
                    resp = None

            if chromium_reason:
                pass
            else:
                page.wait_for_timeout(1500)
                sample = _page_text_sample(page)
                if http_status and http_status >= 400:
                    chromium_reason = f'HTTP {http_status}'
                if _text_looks_blocked(sample):
                    chromium_reason = chromium_reason or 'Access Denied / WAF page'
                elif _text_looks_blank(sample):
                    chromium_reason = chromium_reason or 'blank/near-empty page'
                else:
                    pdf_bytes = page.pdf(**_chromium_pdf_options())
                    # Double-check printed text (some SPAs paint empty PDFs)
                    printed = _pdf_text_sample(pdf_bytes)
                    if _text_looks_blocked(printed) or _text_looks_blank(printed):
                        chromium_reason = 'printed PDF blank or blocked'
                        pdf_bytes = None
        finally:
            browser.close()

    if pdf_bytes:
        return pdf_bytes

    # --- HTTP GET fallback (disabled: nasty / incomplete layouts) ---
    # get_reason = ''
    # try:
    #     status, ctype, body = _http_get_listing(target, timeout_s=max(10.0, timeout_ms / 1000.0))
    #     ok, get_reason = _html_response_usable(status, ctype, body)
    #     if ok:
    #         return _render_html_string_as_pdf(body, base_url=target, timeout_ms=timeout_ms)
    #     if not get_reason:
    #         get_reason = 'unusable GET response'
    # except ListingFetchBlockedError:
    #     raise
    # except Exception as e:
    #     get_reason = f'GET failed: {e}'

    raise ListingFetchBlockedError(
        target,
        chromium_reason=chromium_reason or 'unusable Chromium result',
        get_reason='HTTP GET fallback disabled',
    )


def _stored_document_pdf_bytes(doc: dict) -> Optional[bytes]:
    """Resolve PDF bytes from an infringement document dict or documents collection."""
    # Inline / embedded content on the hit
    for key in ('file_content', 'pdf_bytes', 'content', 'data'):
        raw = doc.get(key)
        data = _coerce_pdf_bytes(raw)
        if data and data[:4] == b'%PDF':
            return data

    # Lookup in documents collection
    doc_id = doc.get('_id') or doc.get('document_id') or doc.get('id')
    if doc_id:
        try:
            from models.documents import getDocumentById
            result = getDocumentById(str(doc_id))
            if result.get('success'):
                stored = result.get('document') or {}
                data = _coerce_pdf_bytes(stored.get('file_content'))
                if data and data[:4] == b'%PDF':
                    return data
                # Some stores wrap content
                data = _coerce_pdf_bytes((stored.get('file') or {}).get('content') if isinstance(stored.get('file'), dict) else None)
                if data and data[:4] == b'%PDF':
                    return data
        except Exception:
            pass
    return None


def _manual_access_note(url: str, *, label: str = '') -> str:
    prefix = f'{label}: ' if label else ''
    return (
        f'MANUAL ACCESS REQUIRED — {prefix}{url}. '
        'Automated page fetching (headless Chromium) was blocked or returned '
        'empty/Access Denied content by the host firewall/WAF. '
        'Open this URL manually in a browser.'
    )


def collect_infringement_document_pdfs(
    hit: InfringementHit,
    *,
    include_html_listings: bool = True,
    html_timeout_ms: int = 45000,
) -> Tuple[List[bytes], List[str]]:
    """
    Build appendable PDF parts for one infringement hit.

    Returns ``(pdf_parts, notes)`` where notes describe successes/skips for the
    documents section. Failures never raise — they become notes so the main
    report still downloads. Blocked listings are listed for manual access and
    are not appended as blank/Access Denied pages.
    """
    parts: List[bytes] = []
    notes: List[str] = []
    seen_urls = set()

    def _append_listing(url: str, *, label: str) -> None:
        try:
            parts.append(load_html_listing_as_pdf_pages(url, timeout_ms=html_timeout_ms))
            notes.append(f'Appended listing pages for: {label or url}')
            seen_urls.add(url)
        except ListingFetchBlockedError:
            notes.append(_manual_access_note(url, label=label))
            seen_urls.add(url)
        except Exception as e:
            notes.append(f'Skipped listing {url}: {e}')
            seen_urls.add(url)

    for i, doc in enumerate(hit.documents or [], start=1):
        if not isinstance(doc, dict):
            continue
        title = _clean_text(doc.get('title') or doc.get('file_name') or doc.get('name') or f'Document {i}')
        file_type = _clean_text(doc.get('file_type') or doc.get('mime_type') or '').lower()
        url = _clean_text(doc.get('url') or doc.get('source_url') or '')

        # Prefer stored PDF bytes
        try:
            pdf_raw = _stored_document_pdf_bytes(doc)
            if pdf_raw:
                parts.append(load_pdf_document_pages(pdf_raw))
                notes.append(f'Appended PDF pages for: {title}')
                if url:
                    seen_urls.add(url)
                continue
        except Exception as e:
            notes.append(f'Skipped stored PDF for {title}: {e}')

        # HTML / listing URL via Chromium (+ GET fallback)
        if include_html_listings and url and url not in seen_urls:
            if file_type.startswith('application/pdf'):
                notes.append(f'Skipped PDF URL without stored bytes: {title or url}')
            elif url.startswith(('http://', 'https://')):
                _append_listing(url, label=title or url)

    # Primary hit URL (product listing) if not already covered
    if include_html_listings and hit.url and hit.url not in seen_urls:
        _append_listing(hit.url, label='Primary listing')

    if not parts and not notes:
        notes.append('No appendable document or listing pages were available.')
    return parts, notes
