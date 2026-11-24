"""
Reusable PDF building blocks for Patent Gap reports.

Each function returns a list of Platypus flowables (or mutates a story list).
Components expect already-narrowed DTOs from data_processors — they do not
fetch from Mongo.
"""

from __future__ import annotations

from io import BytesIO
from typing import Dict, List, Optional, Sequence

from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Flowable,
)

from reports import styles as S
from reports.data_processors import (
    ChartTable,
    ClaimItem,
    IndexEntry,
    InfringementHit,
    MatrixTable,
    PatentInfo,
)


def _p(text: str, style_name: str, styles: dict) -> Paragraph:
    """Escape-ish paragraph helper. ReportLab uses a tiny HTML subset."""
    safe = (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )
    # Preserve line breaks
    safe = safe.replace('\n', '<br/>')
    return Paragraph(safe, styles[style_name])


def _dash(value) -> str:
    if value is None:
        return '—'
    text = str(value).strip()
    return text if text else '—'


def _pct(score: Optional[float]) -> str:
    if score is None:
        return '—'
    return f'{score * 100:.0f}%' if score <= 1.0 else f'{score:.0f}%'


def _tick_cross(matched: bool, score: Optional[float]) -> str:
    mark = '✓' if matched else '✗'
    if score is None:
        return mark
    return f'{mark} {_pct(score)}'


# ---------------------------------------------------------------------------
# Page chrome
# ---------------------------------------------------------------------------

class ReportState:
    """Mutable state shared across page callbacks and builders."""

    def __init__(self):
        self.header_title: str = ''
        self.header_date: str = ''
        self.show_header: bool = True
        self.show_page_number: bool = True
        self.page_offset: int = 0  # subtract from canvas page for display
        self.page_map: Dict[str, int] = {}
        self.styles = S.build_paragraph_styles()


class Marker(Flowable):
    """Invisible flowable that records the current page into ReportState.page_map."""

    def __init__(self, key: str, state: ReportState):
        super().__init__()
        self.key = key
        self.state = state
        self.width = 0
        self.height = 0

    def draw(self):
        # canvas.getPageNumber() is 1-based within the current build
        page = self.canv.getPageNumber() - self.state.page_offset
        if page < 1:
            page = 1
        self.state.page_map[self.key] = page


class SetHeaderTitle(Flowable):
    """Update the running header title from the next page onward."""

    def __init__(self, state: ReportState, title: str):
        super().__init__()
        self.state = state
        self.title = title
        self.width = 0
        self.height = 0

    def draw(self):
        self.state.header_title = self.title


def _draw_header_footer(canvas, doc, state: ReportState):
    canvas.saveState()
    width, height = doc.pagesize
    styles = state.styles

    if state.show_header:
        # Top rule
        canvas.setStrokeColor(S.DEEP)
        canvas.setLineWidth(0.6)
        y = height - S.MARGIN_TOP + 4 * mm
        canvas.line(S.MARGIN_LEFT, y, width - S.MARGIN_RIGHT, y)

        canvas.setFont(S.FONTS['body'], 7.5)
        canvas.setFillColor(S.INK2)
        left = (state.header_title or '')[:110]
        right = state.header_date or ''
        canvas.drawString(S.MARGIN_LEFT, y + 2 * mm, left)
        canvas.drawRightString(width - S.MARGIN_RIGHT, y + 2 * mm, right)

    # Footer band
    fy = S.MARGIN_BOTTOM - 6 * mm
    canvas.setStrokeColor(S.DEEP)
    canvas.setLineWidth(0.5)
    canvas.line(S.MARGIN_LEFT, fy + 5 * mm, width - S.MARGIN_RIGHT, fy + 5 * mm)

    canvas.setFillColor(S.INK3)
    canvas.setFont(S.FONTS['body'], 7.5)
    if state.show_page_number:
        display = canvas.getPageNumber() - state.page_offset
        if display >= 1:
            canvas.drawCentredString(width / 2.0, fy, str(display))

    canvas.setFont(S.FONTS['body_oblique'], 7.5)
    canvas.drawRightString(width - S.MARGIN_RIGHT, fy, S.WATERMARK_TEXT)
    canvas.restoreState()


def _draw_cover_chrome(canvas, doc, state: ReportState):
    """Cover: watermark only — no header, no page number."""
    canvas.saveState()
    width, height = doc.pagesize
    fy = S.MARGIN_BOTTOM - 6 * mm
    canvas.setFillColor(S.INK3)
    canvas.setFont(S.FONTS['body_oblique'], 7.5)
    canvas.drawRightString(width - S.MARGIN_RIGHT, fy, S.WATERMARK_TEXT)
    canvas.restoreState()


def make_doc_template(
    buffer: BytesIO,
    state: ReportState,
    *,
    pagesize=S.PAGE_PORTRAIT,
) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=S.MARGIN_LEFT,
        rightMargin=S.MARGIN_RIGHT,
        topMargin=S.MARGIN_TOP,
        bottomMargin=S.MARGIN_BOTTOM,
        title=state.header_title or 'Patent Gap Report',
        author=S.BRAND_NAME,
    )

    def _frame(ps):
        w, h = ps
        return Frame(
            S.MARGIN_LEFT,
            S.MARGIN_BOTTOM,
            w - S.MARGIN_LEFT - S.MARGIN_RIGHT,
            h - S.MARGIN_TOP - S.MARGIN_BOTTOM,
            id='normal',
        )

    def on_portrait(canvas, doc_):
        _draw_header_footer(canvas, doc_, state)

    def on_landscape(canvas, doc_):
        _draw_header_footer(canvas, doc_, state)

    def on_cover(canvas, doc_):
        _draw_cover_chrome(canvas, doc_, state)

    portrait = PageTemplate(
        id='portrait',
        frames=[_frame(S.PAGE_PORTRAIT)],
        pagesize=S.PAGE_PORTRAIT,
        onPage=on_portrait,
    )
    landscape_tpl = PageTemplate(
        id='landscape',
        frames=[_frame(S.PAGE_LANDSCAPE)],
        pagesize=S.PAGE_LANDSCAPE,
        onPage=on_landscape,
    )
    cover = PageTemplate(
        id='cover',
        frames=[_frame(S.PAGE_PORTRAIT)],
        pagesize=S.PAGE_PORTRAIT,
        onPage=on_cover,
    )
    doc.addPageTemplates([portrait, landscape_tpl, cover])
    return doc


def build_pdf(story: List, state: ReportState, *, first_template: str = 'portrait') -> bytes:
    buf = BytesIO()
    doc = make_doc_template(buf, state)
    # Ensure starting template
    full_story = []
    if first_template != 'portrait':
        full_story.append(NextPageTemplate(first_template))
    full_story.extend(story)
    doc.build(full_story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Section components
# ---------------------------------------------------------------------------

def hero_block(entity_id: str, title: str, styles: dict) -> List:
    return [
        Spacer(1, 6 * mm),
        _p(_dash(entity_id), 'hero_id', styles),
        _p(_dash(title), 'hero_title', styles),
    ]


def meta_row(label: str, value: str, styles: dict) -> List:
    return [
        _p(label.upper(), 'meta_label', styles),
        _p(_dash(value), 'meta_value', styles),
        Spacer(1, 2 * mm),
    ]


def note_line(text: str, styles: dict, *, attorney: bool = False) -> Paragraph:
    style = 'attorney_note' if attorney else 'note'
    prefix = '*Note: ' if not attorney else ''
    return _p(f'{prefix}{text}', style, styles)


def patent_info_section(patent: PatentInfo, styles: dict) -> List:
    story: List = []
    story.extend(hero_block(patent.patent_id, patent.title, styles))
    story.append(_p('Reference Patent Information', 'section_title', styles))

    owners = ', '.join(patent.assignees) if patent.assignees else '—'
    inventors = ', '.join(patent.inventors) if patent.inventors else '—'
    story.extend(meta_row('Owners / Assignees', owners, styles))
    if patent.notes.get('inventors'):
        # owners notes preferred under owners; inventors note still shown
        pass
    # Prefer inventors note under inventors line
    story.extend(meta_row('Inventors', inventors, styles))
    if patent.notes.get('inventors'):
        story.append(note_line(patent.notes['inventors'], styles))
        story.append(Spacer(1, 2 * mm))

    story.extend(meta_row('Filing Date', patent.filing_date, styles))
    story.extend(meta_row('Granted / Patented Date', patent.grant_date, styles))

    story.append(_p('Description', 'meta_label', styles))
    story.append(_p(_dash(patent.description), 'body_center', styles))
    if patent.notes.get('description'):
        story.append(note_line(patent.notes['description'], styles))
    story.append(Spacer(1, 3 * mm))

    if patent.keywords:
        story.extend(meta_row('Keywords', ', '.join(patent.keywords), styles))
        if patent.notes.get('keywords'):
            story.append(note_line(patent.notes['keywords'], styles))
    if patent.context:
        story.append(_p('Context', 'meta_label', styles))
        story.append(_p(patent.context, 'body_center', styles))
        if patent.notes.get('context'):
            story.append(note_line(patent.notes['context'], styles))
    if patent.search_limitations:
        story.append(_p('Search Limitations', 'meta_label', styles))
        story.append(_p(patent.search_limitations, 'body_center', styles))
        if patent.notes.get('search_limitations'):
            story.append(note_line(patent.notes['search_limitations'], styles))

    return story


def claims_section(
    claims: Sequence[ClaimItem],
    styles: dict,
    *,
    title: str = 'Claims',
    claim_notes: Optional[Dict[int, str]] = None,
) -> List:
    story: List = [_p(title, 'section_title', styles)]
    claim_notes = claim_notes or {}
    if not claims:
        story.append(_p('No claims available.', 'body_center', styles))
        return story

    for c in claims:
        note = c.note or claim_notes.get(c.index)
        type_bit = f' ({c.claim_type})' if c.claim_type else ''
        header = f'<b>Claim {c.index + 1}{type_bit}</b>'
        block = [
            Paragraph(header, styles['claim']),
            _p(c.text or '—', 'claim', styles),
        ]
        if note:
            block.append(note_line(note, styles))
        block.append(Spacer(1, 3 * mm))
        story.append(KeepTogether(block))
    return story


def hit_info_section(hit: InfringementHit, styles: dict) -> List:
    kind_label = 'Infringing Product' if hit.kind == 'product' else 'Infringing Patent'
    story: List = []
    story.extend(hero_block(hit.entry_id, hit.title, styles))
    story.append(_p(f'{kind_label} Details', 'section_title', styles))
    story.extend(meta_row('ID', hit.entry_id, styles))
    story.extend(meta_row('Source', hit.source, styles))
    story.extend(meta_row('URL / Listing', hit.url, styles))
    if hit.posted_by:
        story.extend(meta_row('Posted By', hit.posted_by, styles))
    story.extend(meta_row(
        'Average Similarity',
        _pct(hit.average_similarity) if hit.average_similarity is not None else '—',
        styles,
    ))
    if hit.notes.get('product'):
        story.append(note_line(hit.notes['product'], styles))
    return story


def attorney_notes_section(lines: Sequence[str], styles: dict, *, title: str = 'Attorney Notes') -> List:
    if not lines:
        return []
    story: List = [
        Spacer(1, 3 * mm),
        _p(title, 'section_title', styles),
    ]
    for line in lines:
        story.append(_p(line, 'attorney_note', styles))
        story.append(Spacer(1, 1 * mm))
    return story


def _matrix_table_style(cols: int) -> TableStyle:
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), S.DEEP),
        ('TEXTCOLOR', (0, 0), (-1, 0), S.WHITE),
        ('FONTNAME', (0, 0), (-1, 0), S.FONTS['body_bold']),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), S.TABLE_BORDER_WIDTH, S.TABLE_BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 1), (0, -1), S.SURF),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
    ])


def claim_matrix_section(
    matrix: MatrixTable,
    styles: dict,
    *,
    available_width: float,
) -> List:
    """
    Full or single-hit claim matrix as a bordered table.
    Empty cells remain visible (bordered) with ✗ / —.
    """
    story: List = [_p('Claim Matrix', 'section_title', styles)]
    if not matrix.ref_claims or not matrix.hits:
        story.append(_p('No matrix data.', 'body_center', styles))
        return story

    header = [_p('Reference Claim', 'table_header', styles)]
    for h in matrix.hits:
        header.append(_p(_dash(h.entry_id), 'table_header', styles))
    if matrix.include_notes_column:
        header.append(_p('Attorney Notes', 'table_header', styles))

    data = [header]
    for claim in matrix.ref_claims:
        # Left cell: claim number + full claim text (left aligned, no ellipsis)
        left = _p(f'<b>Claim {claim.index + 1}</b><br/>{claim.text or "—"}', 'table_cell_left', styles)
        row = [left]
        note_for_row = ''
        for h in matrix.hits:
            cell = matrix.cells.get((claim.index, h.entry_id))
            if cell is None:
                row.append(_p('✗', 'table_cell', styles))
            else:
                row.append(_p(_tick_cross(cell.matched, cell.score), 'table_cell', styles))
                if matrix.include_notes_column and cell.note:
                    note_for_row = cell.note
        if matrix.include_notes_column:
            row.append(_p(note_for_row or '', 'table_cell_left', styles))
        data.append(row)

    n_cols = len(header)
    claim_w = available_width * 0.42
    rest = available_width - claim_w
    if matrix.include_notes_column:
        hit_w = rest * 0.35
        note_w = rest * 0.65
        col_widths = [claim_w, hit_w, note_w]
    else:
        hit_w = rest / max(len(matrix.hits), 1)
        col_widths = [claim_w] + [hit_w] * len(matrix.hits)

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(_matrix_table_style(n_cols))
    story.append(table)
    return story


def claim_chart_section(chart: ChartTable, styles: dict, *, available_width: float) -> List:
    story: List = [_p('Claim Chart', 'section_title', styles)]
    if not chart.rows:
        story.append(_p('No claim chart rows for this infringement.', 'body_center', styles))
        return story

    header = [
        _p('Reference Claim', 'table_header', styles),
        _p('Infringing Claim', 'table_header', styles),
        _p('Similarity', 'table_header', styles),
        _p('Justification', 'table_header', styles),
    ]
    data = [header]
    for row in chart.rows:
        data.append([
            _p(row.ref_claim or '—', 'table_cell_left', styles),
            _p(row.inf_claim or '—', 'table_cell_left', styles),
            _p(_pct(row.similarity), 'table_cell', styles),
            _p(row.justification or '—', 'justification', styles),
        ])

    col_widths = [
        available_width * 0.28,
        available_width * 0.28,
        available_width * 0.12,
        available_width * 0.32,
    ]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), S.DEEP),
        ('TEXTCOLOR', (0, 0), (-1, 0), S.WHITE),
        ('FONTNAME', (0, 0), (-1, 0), S.FONTS['body_bold']),
        ('GRID', (0, 0), (-1, -1), S.TABLE_BORDER_WIDTH, S.TABLE_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 1), (-1, -1), S.BG),
    ]))
    story.append(table)
    story.extend(attorney_notes_section(chart.attorney_notes, styles))
    return story


def documents_section(hit: InfringementHit, styles: dict) -> List:
    """
    Appendix listing for infringing product/patent documents and listing URLs.

    HTML→PDF page append for live listings is intentionally stubbed here:
    we always emit a complete link/title inventory so the report is printable
    without depending on external fetches. Callers can later merge real PDF
    bytes after this section.
    """
    story: List = [_p('Documents / Listing Pages', 'section_title', styles)]
    if not hit.documents and not hit.url:
        story.append(_p('No documents or listing URLs recorded for this infringement.', 'body_center', styles))
        return story

    if hit.url:
        story.append(_p(f'Primary listing: {hit.url}', 'body', styles))
        story.append(Spacer(1, 2 * mm))

    for i, doc in enumerate(hit.documents, start=1):
        title = _dash(doc.get('title') or doc.get('file_name') or doc.get('name') or f'Document {i}')
        url = _dash(doc.get('url') or doc.get('source_url') or '')
        source = _dash(doc.get('source') or '')
        block = [
            _p(f'<b>{i}. {title}</b>', 'body', styles),
            _p(f'Source: {source}', 'meta_value', styles),
            _p(f'URL: {url}', 'body', styles),
            Spacer(1, 2 * mm),
        ]
        story.append(KeepTogether(block))

    story.append(Spacer(1, 2 * mm))
    story.append(_p(
        'Note: Full HTML listing pages are referenced by URL in this framework build. '
        'A later pass can fetch and append rendered PDF pages after this section.',
        'attorney_note',
        styles,
    ))
    return story


def cover_page_whats_new(
    portfolio_name: str,
    generated_on: str,
    styles: dict,
) -> List:
    """
    Cover content only (use with cover page template).
    Title / subtitle / powered-by / generated-on.
    """
    is_unsorted = (portfolio_name or '').strip().lower() == 'unsorted'
    related = 'unsorted' if is_unsorted else f'the {portfolio_name}'
    title = f'What is new in {portfolio_name} patents?'
    subtitle = (
        f'A report on all new patent and product infringements found in patents '
        f'related to {related} patents.'
    )
    return [
        Spacer(1, 45 * mm),
        _p(title, 'cover_title', styles),
        _p(subtitle, 'cover_subtitle', styles),
        Spacer(1, 18 * mm),
        _p(f'Powered by: {S.BRAND_NAME}', 'cover_meta', styles),
        Spacer(1, 6 * mm),
        _p(f'Generated on: {generated_on}', 'cover_meta', styles),
        PageBreak(),
    ]


def index_section(
    entries: Sequence[IndexEntry],
    page_map: Dict[str, int],
    styles: dict,
    *,
    title: str = 'Index',
) -> List:
    story: List = [
        _p(title, 'section_title', styles),
        Spacer(1, 4 * mm),
    ]
    if not entries:
        story.append(_p('No sections to index.', 'body_center', styles))
        return story

    for e in entries:
        page = page_map.get(e.marker, '')
        page_str = str(page) if page != '' else ''
        # Dot leaders via simple spacing — full titles, no ellipsis
        label = e.label
        line = f'{label}  {page_str}'.strip()
        style = 'index_sub' if e.level else 'index_entry'
        story.append(_p(line, style, styles))
        story.append(Spacer(1, 1.5 * mm))
    return story


def available_content_width(pagesize=S.PAGE_PORTRAIT) -> float:
    w, _ = pagesize
    return w - S.MARGIN_LEFT - S.MARGIN_RIGHT
