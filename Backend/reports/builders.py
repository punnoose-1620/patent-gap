"""
Report builders — public entry points that assemble processors + components
into PDF bytes for the three report families.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from PyPDF2 import PdfMerger, PdfReader
except Exception:  # pragma: no cover
    PdfMerger = None
    PdfReader = None

from reports import styles as S
from reports.components import (
    Marker,
    ReportState,
    SetHeaderTitle,
    attorney_notes_section,
    available_content_width,
    build_pdf,
    claim_chart_section,
    claim_matrix_section,
    claims_section,
    cover_page_whats_new,
    documents_section,
    hit_info_section,
    index_section,
    patent_info_section,
)
from reports.data_processors import (
    IndexEntry,
    InfringementHit,
    PortfolioChapterPlan,
    build_claim_chart,
    build_matrix,
    extract_claims,
    extract_hit,
    filter_hits_by_kind,
    find_infringement_entry,
    format_generated_date,
    format_header_date,
    header_title_hit_kind,
    header_title_patent_vs,
    load_case_bundle,
    mixed_kind_label,
    plan_whats_new_chapters,
)
from reportlab.platypus import NextPageTemplate, PageBreak


# ---------------------------------------------------------------------------
# Internal story helpers
# ---------------------------------------------------------------------------

def _story_patent_block(patent, styles, state: ReportState, marker: str) -> List:
    story: List = [Marker(marker, state)]
    story.extend(patent_info_section(patent, styles))
    return story


def _story_ref_claims(patent, case, styles) -> List:
    claims = extract_claims(case)
    # attach notes from patent.claim_notes
    return claims_section(
        claims,
        styles,
        title='Reference Patent Claims',
        claim_notes=patent.claim_notes,
    )


def _story_single_hit_body(
    case,
    entry: dict,
    notes_map: dict,
    styles,
    state: ReportState,
    *,
    hit_marker: str,
    chart_marker: str,
    include_matrix: bool = True,
) -> Tuple[List, InfringementHit]:
    hit = extract_hit(entry, notes_map=notes_map)
    story: List = [Marker(hit_marker, state)]
    story.extend(hit_info_section(hit, styles))
    story.extend(claims_section(
        hit.claims,
        styles,
        title=('Infringing Product Claims' if hit.kind == 'product' else 'Infringing Patent Claims'),
        claim_notes=hit.claim_notes,
    ))

    width = available_content_width(S.PAGE_PORTRAIT)

    if include_matrix:
        matrix = build_matrix(
            case,
            [entry],
            notes_map,
            single_hit_notes_column=True,
        )
        story.extend(claim_matrix_section(matrix, styles, available_width=width))
        # When notes are in-column we skip the under-matrix attorney block for single-hit;
        # otherwise (no notes column) still emit under-matrix notes if any.
        if not matrix.include_notes_column and matrix.attorney_notes:
            story.extend(attorney_notes_section(matrix.attorney_notes, styles))

    story.append(Marker(chart_marker, state))
    chart = build_claim_chart(case, entry, notes_map)
    story.extend(claim_chart_section(chart, styles, available_width=width))
    story.extend(documents_section(hit, styles))
    return story, hit


def _story_full_matrix(
    case,
    entries: Sequence[dict],
    notes_map: dict,
    styles,
    state: ReportState,
    *,
    matrix_marker: str,
) -> List:
    matrix = build_matrix(case, entries, notes_map, single_hit_notes_column=False)
    use_landscape = len(matrix.hits) > S.LANDSCAPE_HIT_THRESHOLD
    story: List = []

    if use_landscape:
        story.append(NextPageTemplate('landscape'))
        story.append(PageBreak())
        story.append(Marker(matrix_marker, state))
        width = available_content_width(S.PAGE_LANDSCAPE)
        story.extend(claim_matrix_section(matrix, styles, available_width=width))
        # Notes on following portrait page
        story.append(NextPageTemplate('portrait'))
        story.append(PageBreak())
        story.extend(attorney_notes_section(matrix.attorney_notes, styles))
    else:
        story.append(Marker(matrix_marker, state))
        width = available_content_width(S.PAGE_PORTRAIT)
        story.extend(claim_matrix_section(matrix, styles, available_width=width))
        story.extend(attorney_notes_section(matrix.attorney_notes, styles))
    return story


def _story_multi_hit_report(
    case,
    patent,
    entries: Sequence[dict],
    notes_map: dict,
    state: ReportState,
    *,
    index_entries: List[IndexEntry],
    marker_prefix: str = '',
    header_title: Optional[str] = None,
) -> List:
    styles = state.styles
    story: List = []
    if header_title:
        story.append(SetHeaderTitle(state, header_title))

    ref_marker = f'{marker_prefix}ref'
    index_entries.append(IndexEntry(
        label=f'{patent.patent_id}: {patent.title}',
        level=0,
        marker=ref_marker,
    ))
    story.extend(_story_patent_block(patent, styles, state, ref_marker))
    story.extend(_story_ref_claims(patent, case, styles))

    matrix_marker = f'{marker_prefix}matrix'
    index_entries.append(IndexEntry(
        label='Full Claim Matrix',
        level=0,
        marker=matrix_marker,
    ))
    story.extend(_story_full_matrix(
        case, entries, notes_map, styles, state, matrix_marker=matrix_marker,
    ))

    for i, entry in enumerate(entries):
        hit = extract_hit(entry, notes_map=notes_map)
        hit_marker = f'{marker_prefix}hit:{hit.entry_id}:{i}'
        chart_marker = f'{marker_prefix}chart:{hit.entry_id}:{i}'
        index_entries.append(IndexEntry(
            label=f'{hit.entry_id}: {hit.title}',
            level=0,
            marker=hit_marker,
        ))
        index_entries.append(IndexEntry(
            label='Claim Chart',
            level=1,
            marker=chart_marker,
        ))
        story.append(PageBreak())
        body, _ = _story_single_hit_body(
            case, entry, notes_map, styles, state,
            hit_marker=hit_marker,
            chart_marker=chart_marker,
            include_matrix=False,  # full matrix already above
        )
        story.extend(body)

    return story


def _story_single_hit_report(
    case,
    patent,
    entry: dict,
    notes_map: dict,
    state: ReportState,
    *,
    index_entries: Optional[List[IndexEntry]] = None,
    marker_prefix: str = '',
    include_in_index: bool = False,
    header_title: Optional[str] = None,
) -> List:
    styles = state.styles
    story: List = []
    if header_title:
        story.append(SetHeaderTitle(state, header_title))
    ref_marker = f'{marker_prefix}ref'
    if include_in_index and index_entries is not None:
        index_entries.append(IndexEntry(
            label=f'{patent.patent_id}: {patent.title}',
            level=0,
            marker=ref_marker,
        ))
    story.extend(_story_patent_block(patent, styles, state, ref_marker))
    story.extend(_story_ref_claims(patent, case, styles))

    hit = extract_hit(entry, notes_map=notes_map)
    hit_marker = f'{marker_prefix}hit:{hit.entry_id}'
    chart_marker = f'{marker_prefix}chart:{hit.entry_id}'
    if include_in_index and index_entries is not None:
        index_entries.append(IndexEntry(
            label=f'{hit.entry_id}: {hit.title}',
            level=0,
            marker=hit_marker,
        ))
        index_entries.append(IndexEntry(
            label='Claim Chart',
            level=1,
            marker=chart_marker,
        ))

    story.append(PageBreak())
    body, _ = _story_single_hit_body(
        case, entry, notes_map, styles, state,
        hit_marker=hit_marker,
        chart_marker=chart_marker,
        include_matrix=True,
    )
    story.extend(body)
    return story


def _pdf_page_count(pdf_bytes: bytes) -> int:
    if not pdf_bytes or PdfReader is None:
        return 0
    return len(PdfReader(BytesIO(pdf_bytes)).pages)


def _merge_pdfs(parts: Sequence[bytes]) -> bytes:
    if PdfMerger is None:
        # Fallback: return last non-empty part
        for p in reversed(parts):
            if p:
                return p
        return b''
    merger = PdfMerger()
    for part in parts:
        if not part:
            continue
        merger.append(BytesIO(part))
    out = BytesIO()
    merger.write(out)
    merger.close()
    return out.getvalue()


def _build_index_pdf(
    entries: Sequence[IndexEntry],
    page_map: Dict[str, int],
    state: ReportState,
    *,
    page_shift: int = 0,
) -> bytes:
    """
    Build index pages. ``page_shift`` is added to recorded content page numbers
    so index labels match the final merged pagination (index pages themselves
    occupy pages 1..N; content starts at N+1).
    """
    shifted = {k: v + page_shift for k, v in page_map.items()}
    # First estimate without shift correction for index length: build once,
    # then rebuild with correct shift if needed by caller.
    index_state = ReportState()
    index_state.header_title = state.header_title
    index_state.header_date = state.header_date
    index_state.show_header = True
    index_state.show_page_number = True
    index_state.page_offset = 0
    story = index_section(entries, shifted, index_state.styles)
    story.append(PageBreak())  # ensure trailing content doesn't collide; builders trim empty?
    # Remove trailing page break by not adding one — index can end naturally
    story = index_section(entries, shifted, index_state.styles)
    return build_pdf(story, index_state, first_template='portrait')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_patent_vs_infringement_report(
    case_id: str,
    infringement_id: str,
    *,
    user_id: Optional[str] = None,
) -> bytes:
    """
    Report type 1 — Patent vs Infringement Report.

    Header: ``<patent id> vs <infringement id> Infringement Report``
    """
    del user_id  # reserved for future ACL checks at the API layer
    case, patent, notes_map = load_case_bundle(case_id)
    entry = find_infringement_entry(case, infringement_id)
    if entry is None:
        raise ValueError(f'Infringement not found on case {case_id}: {infringement_id}')

    hit = extract_hit(entry, notes_map=notes_map)
    state = ReportState()
    state.header_title = header_title_patent_vs(patent.patent_id, hit.entry_id)
    state.header_date = format_header_date()
    state.show_header = True
    state.show_page_number = True
    state.page_offset = 0

    story = _story_single_hit_report(case, patent, entry, notes_map, state)
    return build_pdf(story, state)


def build_products_patents_infringements_report(
    case_id: str,
    hit_kind: str = 'products',
    *,
    infringement_ids: Optional[Sequence[str]] = None,
    user_id: Optional[str] = None,
) -> bytes:
    """
    Report type 2 — Products / Patents Infringements Report.

    ``hit_kind``: ``products`` | ``patents`` | ``mixed`` (products+patents together).

    Optional ``infringement_ids`` restricts the hit set (used by What's New
    multi-hit chapters). When omitted, all hits of ``hit_kind`` on the case
    are included.

    Header examples:
      ``<patent id> Products Infringements Report``
      ``<patent id> Patents Infringements Report``
      ``<patent id> Product And Patent Infringement Report``
    """
    del user_id
    case, patent, notes_map = load_case_bundle(case_id)
    all_entries = [e for e in (case.get('infringements') or []) if isinstance(e, dict)]

    if infringement_ids:
        wanted = {str(x).strip() for x in infringement_ids}
        entries = []
        for e in all_entries:
            hit = extract_hit(e, notes_map=notes_map)
            if hit.entry_id in wanted:
                entries.append(e)
    else:
        entries = filter_hits_by_kind(all_entries, hit_kind)

    if not entries:
        raise ValueError(
            f'No infringements of kind={hit_kind!r} on case {case_id}'
            + (f' matching ids={list(infringement_ids)}' if infringement_ids else '')
        )

    hits = [extract_hit(e, notes_map=notes_map) for e in entries]
    kind_for_header = hit_kind if hit_kind in ('products', 'patents', 'product', 'patent') else mixed_kind_label(hits)
    if hit_kind in ('mixed', 'all'):
        kind_for_header = 'mixed'

    state = ReportState()
    state.header_title = header_title_hit_kind(patent.patent_id, kind_for_header)
    state.header_date = format_header_date()

    index_entries: List[IndexEntry] = []
    content_story = _story_multi_hit_report(
        case, patent, entries, notes_map, state,
        index_entries=index_entries,
        header_title=state.header_title,
    )

    # Pass 1 — content, collect page map
    content_pdf = build_pdf(content_story, state)
    page_map = dict(state.page_map)

    # Pass 2 — index with correct page shift (= index page count)
    # Build a draft index with shift 0 to measure length, then rebuild.
    draft_index = _build_index_pdf(index_entries, page_map, state, page_shift=0)
    index_len = _pdf_page_count(draft_index) or 1
    final_index = _build_index_pdf(index_entries, page_map, state, page_shift=index_len)

    # Rebuild content so displayed page numbers continue after the index
    state2 = ReportState()
    state2.header_title = state.header_title
    state2.header_date = state.header_date
    state2.page_offset = -index_len
    index_entries_2: List[IndexEntry] = []
    content_story_2 = _story_multi_hit_report(
        case, patent, entries, notes_map, state2,
        index_entries=index_entries_2,
        header_title=state2.header_title,
    )
    content_pdf_2 = build_pdf(content_story_2, state2)

    # Refresh index with page numbers from second pass (already include offset in markers)
    # Markers recorded display pages directly when page_offset is applied in Marker.draw
    final_index = _build_index_pdf(index_entries_2, state2.page_map, state2, page_shift=0)

    return _merge_pdfs([final_index, content_pdf_2])


def build_whats_new_report(
    user_id: str,
    folder_id: str = 'unsorted',
    *,
    since: Optional[datetime] = None,
) -> bytes:
    """
    Report type 3 — What's New in portfolio.

    Cover (unnumbered) → Index (page 1…) → chapters:
      - exactly 1 new hit → Patent vs Infringement chapter
      - >1 new hits → multi-hit chapter (mixed products+patents in one matrix)
      - 0 new → skipped

    ``since`` overrides the newness baseline (default:
    each case's ``last_infringement_analysis_date``).
    """
    if not user_id or not str(user_id).strip():
        raise ValueError('user_id is required')

    portfolio_name, chapters = plan_whats_new_chapters(
        str(user_id).strip(), folder_id, since=since,
    )
    if not chapters:
        from reportlab.platypus import Paragraph
        cover_pdf = _build_cover_pdf(portfolio_name)
        notice_state = ReportState()
        notice_state.header_title = f'What is new in {portfolio_name}'
        notice_state.header_date = format_header_date()
        notice_pdf = build_pdf(
            [Paragraph(
                'No new patent or product infringements found for this portfolio.',
                notice_state.styles['body_center'],
            )],
            notice_state,
        )
        return _merge_pdfs([cover_pdf, notice_pdf])

    # Assemble all chapter content into one story with index entries
    content_state = ReportState()
    content_state.header_title = f'What is new in {portfolio_name}'
    content_state.header_date = format_header_date()
    index_entries: List[IndexEntry] = []
    content_story: List = []

    for ci, chapter in enumerate(chapters):
        case, patent, notes_map = load_case_bundle(chapter.case_id)
        # Restrict to the planned new hits only
        wanted_ids = {h.entry_id for h in chapter.hits}
        entries = []
        for e in case.get('infringements') or []:
            if not isinstance(e, dict):
                continue
            if extract_hit(e, notes_map=notes_map).entry_id in wanted_ids:
                entries.append(e)

        prefix = f'ch{ci}:'
        if ci > 0:
            content_story.append(PageBreak())

        if chapter.mode == 'single' and entries:
            hit = extract_hit(entries[0], notes_map=notes_map)
            content_story.extend(_story_single_hit_report(
                case, patent, entries[0], notes_map, content_state,
                index_entries=index_entries,
                marker_prefix=prefix,
                include_in_index=True,
                header_title=header_title_patent_vs(patent.patent_id, hit.entry_id),
            ))
        else:
            hits = [extract_hit(e, notes_map=notes_map) for e in entries]
            content_story.extend(_story_multi_hit_report(
                case, patent, entries, notes_map, content_state,
                index_entries=index_entries,
                marker_prefix=prefix,
                header_title=header_title_hit_kind(patent.patent_id, mixed_kind_label(hits)),
            ))

    # Pass 1 content
    content_pdf = build_pdf(content_story, content_state)
    page_map = dict(content_state.page_map)

    draft_index = _build_index_pdf(index_entries, page_map, content_state, page_shift=0)
    index_len = _pdf_page_count(draft_index) or 1

    # Pass 2 content with page numbers continuing after index
    content_state2 = ReportState()
    content_state2.header_title = content_state.header_title
    content_state2.header_date = content_state.header_date
    content_state2.page_offset = -index_len
    index_entries2: List[IndexEntry] = []
    content_story2: List = []

    for ci, chapter in enumerate(chapters):
        case, patent, notes_map = load_case_bundle(chapter.case_id)
        wanted_ids = {h.entry_id for h in chapter.hits}
        entries = []
        for e in case.get('infringements') or []:
            if not isinstance(e, dict):
                continue
            if extract_hit(e, notes_map=notes_map).entry_id in wanted_ids:
                entries.append(e)
        prefix = f'ch{ci}:'
        if ci > 0:
            content_story2.append(PageBreak())
        if chapter.mode == 'single' and entries:
            hit = extract_hit(entries[0], notes_map=notes_map)
            content_story2.extend(_story_single_hit_report(
                case, patent, entries[0], notes_map, content_state2,
                index_entries=index_entries2,
                marker_prefix=prefix,
                include_in_index=True,
                header_title=header_title_patent_vs(patent.patent_id, hit.entry_id),
            ))
        else:
            hits = [extract_hit(e, notes_map=notes_map) for e in entries]
            content_story2.extend(_story_multi_hit_report(
                case, patent, entries, notes_map, content_state2,
                index_entries=index_entries2,
                marker_prefix=prefix,
                header_title=header_title_hit_kind(patent.patent_id, mixed_kind_label(hits)),
            ))

    content_pdf2 = build_pdf(content_story2, content_state2)
    final_index = _build_index_pdf(index_entries2, content_state2.page_map, content_state2, page_shift=0)
    cover_pdf = _build_cover_pdf(portfolio_name)

    return _merge_pdfs([cover_pdf, final_index, content_pdf2])


def _build_cover_pdf(portfolio_name: str) -> bytes:
    state = ReportState()
    state.show_header = False
    state.show_page_number = False
    story = cover_page_whats_new(portfolio_name, format_generated_date(), state.styles)
    # cover_page_whats_new ends with PageBreak — drop it for a single cover page
    if story and isinstance(story[-1], PageBreak):
        story = story[:-1]
    return build_pdf(story, state, first_template='cover')
