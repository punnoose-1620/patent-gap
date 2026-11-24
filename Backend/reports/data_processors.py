"""
Data isolation for PDF reports.

Takes full case / folder payloads and returns narrow structures that
components can render without knowing Mongo shape details.
"""

from __future__ import annotations

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
    score: Optional[float]
    matched: bool
    note: Optional[str] = None


@dataclass
class MatrixTable:
    """Ref claims × one or more hits."""
    ref_claims: List[ClaimItem]
    hits: List[InfringementHit]
    cells: Dict[Tuple[int, str], MatrixCell]  # (ref_index, entry_id) -> cell
    include_notes_column: bool = False  # single-hit 3-col layout
    attorney_notes: List[str] = field(default_factory=list)


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
    label: str
    level: int = 0  # 0 = primary, 1 = indented (e.g. Claim Chart)
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


def claim_documented_text(claim_obj) -> str:
    if claim_obj is None:
        return ''
    if isinstance(claim_obj, str):
        return claim_obj.strip()
    if isinstance(claim_obj, dict):
        return _clean_text(
            claim_obj.get('documented_claim')
            or claim_obj.get('market_language_claim')
            or claim_obj.get('claim')
            or claim_obj.get('text')
        )
    return _clean_text(claim_obj)


def extract_claims(case_or_entry: dict, *, prefer_documented: bool = True) -> List[ClaimItem]:
    raw = case_or_entry.get('claims') or []
    if not isinstance(raw, list):
        return []
    items: List[ClaimItem] = []
    for i, c in enumerate(raw):
        text = claim_documented_text(c) if prefer_documented else _clean_text(c)
        if not text and isinstance(c, dict):
            text = _clean_text(c.get('market_language_claim'))
        ctype = None
        if isinstance(c, dict):
            ctype = _clean_text(c.get('claim_type') or c.get('type')) or None
        items.append(ClaimItem(index=i, text=text or '—', claim_type=ctype))
    return items


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

    assignees = _as_list(case.get('current_assignee') or case.get('assignees') or case.get('assignee'))
    inventors = _as_list(case.get('inventors') or case.get('inventor'))

    return PatentInfo(
        case_id=case_id,
        patent_id=extract_patent_id(case),
        title=_clean_text(case.get('title')) or 'Untitled Patent',
        inventors=[_clean_text(x) for x in inventors if _clean_text(x)],
        assignees=[_clean_text(x) for x in assignees if _clean_text(x)],
        filing_date=_clean_text(case.get('filingDate') or case.get('filing_date')),
        grant_date=_clean_text(
            case.get('grantDate')
            or case.get('granted_date')
            or case.get('currentStatusDate')
            or case.get('publication_date')
        ),
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

    claims_raw = entry.get('claims') or []
    claims: List[ClaimItem] = []
    if isinstance(claims_raw, list):
        for i, c in enumerate(claims_raw):
            text = claim_documented_text(c) if not isinstance(c, str) else c.strip()
            claims.append(ClaimItem(
                index=i,
                text=text or '—',
                note=claim_notes.get(i),
            ))

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


def build_matrix(
    case: dict,
    entries: Sequence[dict],
    notes_map: Optional[Dict[str, dict]] = None,
    *,
    single_hit_notes_column: bool = False,
) -> MatrixTable:
    notes_map = notes_map or {}
    ref_claims = extract_claims(case)
    hits = [extract_hit(e, notes_map=notes_map) for e in entries]
    cells: Dict[Tuple[int, str], MatrixCell] = {}
    attorney_notes: List[str] = []
    any_inline_note = False

    for hit, entry in zip(hits, entries):
        for claim in ref_claims:
            score = _score_for_ref_vs_entry(entry, claim.index)
            matched = score is not None and score >= MATCH_TICK_THRESHOLD
            note = (
                _note_text(notes_map, f'claim_matrix:{hit.entry_id}:{claim.index}')
                or _note_text(notes_map, f'claim_chart:{hit.entry_id}:{claim.index}')
            )
            if note:
                any_inline_note = True
                attorney_notes.append(
                    f'claim {claim.index + 1} - {hit.entry_id} : {note}'
                )
            cells[(claim.index, hit.entry_id)] = MatrixCell(
                ref_claim_index=claim.index,
                entry_id=hit.entry_id,
                score=score,
                matched=matched,
                note=note,
            )

    return MatrixTable(
        ref_claims=ref_claims,
        hits=hits,
        cells=cells,
        include_notes_column=bool(single_hit_notes_column and any_inline_note and len(hits) == 1),
        attorney_notes=attorney_notes,
    )


def build_claim_chart(
    case: dict,
    entry: dict,
    notes_map: Optional[Dict[str, dict]] = None,
) -> ChartTable:
    notes_map = notes_map or {}
    hit = extract_hit(entry, notes_map=notes_map)
    ref_claims = extract_claims(case)
    rows: List[ChartRow] = []
    attorney_notes: List[str] = []

    # Prefer similar_claims (product-style with justification)
    similar = entry.get('similar_claims')
    if isinstance(similar, list) and similar:
        for i, row in enumerate(similar):
            if not isinstance(row, dict):
                continue
            idx = row.get('ref_claim_index')
            if idx is None:
                idx = i
            try:
                idx_i = int(idx)
            except Exception:
                idx_i = i
            ref_text = ''
            if 0 <= idx_i < len(ref_claims):
                ref_text = ref_claims[idx_i].text
            else:
                ref_text = _clean_text(row.get('ref_claim'))
            inf_text = claim_documented_text(row.get('claim') or row.get('infringing_claim') or '')
            sim = row.get('similarity_score')
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
                idx = row.get('ref_claim_index')
                if idx is None:
                    idx = i
                try:
                    idx_i = int(idx)
                except Exception:
                    idx_i = i
                ref_text = _clean_text(row.get('ref_claim'))
                if not ref_text and 0 <= idx_i < len(ref_claims):
                    ref_text = ref_claims[idx_i].text
                inf_text = claim_documented_text(row.get('claim') or '')
                sim = row.get('calculated_similarity_score')
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
                    justification='',
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
