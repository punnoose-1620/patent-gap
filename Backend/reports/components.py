"""
Reusable PDF building blocks for Patent Gap reports.

Each function returns a list of Platypus flowables (or mutates a story list).
Components expect already-narrowed DTOs from data_processors — they do not
fetch from Mongo.
"""

from __future__ import annotations

from io import BytesIO
from typing import Dict, List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
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


def _escape_xml(text: str) -> str:
    """Escape user content for ReportLab Paragraph XML/HTML subset."""
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _p(text: str, style_name: str, styles: dict) -> Paragraph:
    """Plain-text paragraph: escapes markup, preserves newlines as <br/>."""
    safe = _escape_xml(text).replace('\n', '<br/>')
    return Paragraph(safe, styles[style_name])


def _p_markup(html: str, style_name: str, styles: dict) -> Paragraph:
    """
    Paragraph with intentional ReportLab markup already applied.
    Caller must escape any untrusted text fragments before embedding.
    """
    return Paragraph((html or '').replace('\n', '<br/>'), styles[style_name])


def _claim_label_paragraph(
    claim_index: int,
    claim_text: str,
    styles: dict,
    *,
    style_name: str = 'table_cell_left',
    compact: bool = False,
) -> Paragraph:
    """Bold claim label + full escaped claim body (no literal tags in output)."""
    body = _escape_xml(claim_text or '—').replace('\n', '<br/>')
    html = f'<b>Claim {claim_index + 1}</b><br/>{body}'
    if compact:
        compact_style = ParagraphStyle(
            'PGMatrixClaim',
            parent=styles[style_name],
            fontSize=6.5,
            leading=8,
        )
        return Paragraph(html, compact_style)
    return _p_markup(html, style_name, styles)


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


def _page_orientation(pagesize) -> str:
    w, h = pagesize
    return 'landscape' if w > h else 'portrait'


def _current_pagesize(canvas, doc):
    """Prefer the active page template size (portrait vs landscape)."""
    try:
        tpl = getattr(doc, 'pageTemplate', None)
        if tpl is not None and getattr(tpl, 'pagesize', None):
            return tpl.pagesize
    except Exception:
        pass
    try:
        if getattr(canvas, '_pagesize', None):
            return canvas._pagesize
    except Exception:
        pass
    return doc.pagesize


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


def draw_header(canvas, doc, state: ReportState, orientation: Optional[str] = None):
    """
    Draw report header for the current page.
    ``orientation`` is ``'portrait'`` or ``'landscape'`` (auto-detected if omitted).
    """
    width, height = _current_pagesize(canvas, doc)
    orientation = orientation or _page_orientation((width, height))
    # Same layout rules; geometry follows the active pagesize (landscape is wider).
    del orientation  # available for future orientation-specific tweaks

    if not state.show_header:
        return

    canvas.saveState()
    canvas.setStrokeColor(S.DEEP)
    canvas.setLineWidth(0.6)
    y = height - S.MARGIN_TOP + 4 * mm
    canvas.line(S.MARGIN_LEFT, y, width - S.MARGIN_RIGHT, y)

    canvas.setFont(S.FONTS['body'], 7.5)
    canvas.setFillColor(S.INK2)
    # Allow a longer title on landscape pages
    max_title = 160 if width > height else 110
    left = (state.header_title or '')[:max_title]
    right = state.header_date or ''
    canvas.drawString(S.MARGIN_LEFT, y + 2 * mm, left)
    canvas.drawRightString(width - S.MARGIN_RIGHT, y + 2 * mm, right)
    canvas.restoreState()


def draw_footer(canvas, doc, state: ReportState, orientation: Optional[str] = None):
    """
    Draw report footer (page number + watermark) for the current page.
    ``orientation`` is ``'portrait'`` or ``'landscape'`` (auto-detected if omitted).
    """
    width, height = _current_pagesize(canvas, doc)
    orientation = orientation or _page_orientation((width, height))
    del orientation

    canvas.saveState()
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


def _draw_header_footer(canvas, doc, state: ReportState):
    orientation = _page_orientation(_current_pagesize(canvas, doc))
    draw_header(canvas, doc, state, orientation=orientation)
    draw_footer(canvas, doc, state, orientation=orientation)


def _draw_cover_chrome(canvas, doc, state: ReportState):
    """Cover: watermark only — no header, no page number."""
    canvas.saveState()
    width, height = _current_pagesize(canvas, doc)
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
        canvas.setPageSize(S.PAGE_PORTRAIT)
        draw_header(canvas, doc_, state, orientation='portrait')
        draw_footer(canvas, doc_, state, orientation='portrait')

    def on_landscape(canvas, doc_):
        # Force landscape page box so header/footer span the wide edge
        canvas.setPageSize(S.PAGE_LANDSCAPE)
        draw_header(canvas, doc_, state, orientation='landscape')
        draw_footer(canvas, doc_, state, orientation='landscape')

    def on_cover(canvas, doc_):
        canvas.setPageSize(S.PAGE_PORTRAIT)
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
    story.extend(meta_row('Owners / Assignees', owners, styles))

    # Omit inventors / granted date entirely when empty (no placeholder row)
    if patent.inventors:
        inventors = ', '.join(patent.inventors)
        story.extend(meta_row('Inventors', inventors, styles))
        if patent.notes.get('inventors'):
            story.append(note_line(patent.notes['inventors'], styles))
            story.append(Spacer(1, 2 * mm))
    elif patent.notes.get('inventors'):
        story.append(note_line(patent.notes['inventors'], styles))
        story.append(Spacer(1, 2 * mm))

    if patent.filing_date:
        story.extend(meta_row('Filing Date', patent.filing_date, styles))
    if patent.grant_date:
        story.extend(meta_row('Granted / Patented Date', patent.grant_date, styles))

    story.append(_p('Description', 'meta_label', styles))
    story.append(_p(_dash(patent.description), 'body_center', styles))
    if patent.notes.get('description'):
        story.append(note_line(patent.notes['description'], styles))
    story.append(Spacer(1, 3 * mm))

    # Keywords and search limitations are intentionally omitted from reports
    # (may be shared outside the client; must not expose search strategy).

    if patent.context:
        story.append(_p('Context', 'meta_label', styles))
        story.append(_p(patent.context, 'body_center', styles))
        if patent.notes.get('context'):
            story.append(note_line(patent.notes['context'], styles))

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
    """Infringement opener: title as hero header; id only once in the details block."""
    kind_label = 'Infringing Product' if hit.kind == 'product' else 'Infringing Patent'
    story: List = [
        Spacer(1, 6 * mm),
        _p(_dash(hit.title), 'hero_id', styles),
        _p(f'{kind_label} Details', 'section_title', styles),
    ]
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

    Left column shows full reference claim text (Claim N + body).
    Wide hit sets are chunked so headers stay readable on the page.
    """
    story: List = [_p('Claim Matrix', 'section_title', styles)]
    if not matrix.ref_claims or not matrix.hits:
        story.append(_p('No matrix data.', 'body_center', styles))
        return story

    # Fewer hit columns when embedding full claim text so rows fit landscape height
    max_hits_per_table = 4 if not matrix.include_notes_column else 1
    hit_chunks = [
        matrix.hits[i:i + max_hits_per_table]
        for i in range(0, len(matrix.hits), max_hits_per_table)
    ]
    multi = not matrix.include_notes_column and len(matrix.hits) > 1

    for chunk_i, hits_chunk in enumerate(hit_chunks):
        if chunk_i > 0:
            story.append(Spacer(1, 4 * mm))
            story.append(_p(
                f'Claim Matrix (continued {chunk_i + 1}/{len(hit_chunks)})',
                'section_title',
                styles,
            ))

        header = [_p('Reference Claim', 'table_header', styles)]
        for h in hits_chunk:
            header.append(_p(_dash(h.entry_id), 'table_header', styles))
        if matrix.include_notes_column:
            header.append(_p('Attorney Notes', 'table_header', styles))

        data = [header]
        for claim in matrix.ref_claims:
            left = _claim_label_paragraph(
                claim.index,
                claim.text or '—',
                styles,
                compact=multi,
            )
            row = [left]
            note_for_row = ''
            for h in hits_chunk:
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

        # Single-hit matrix (one product/patent): 70% claim / 30% product(+notes)
        # Multi-hit chunks: give claim column enough room, share the rest across hits
        if len(matrix.hits) == 1:
            claim_w = available_width * 0.70
            rest = available_width - claim_w
            if matrix.include_notes_column:
                hit_w = rest * 0.40
                note_w = rest * 0.60
                col_widths = [claim_w, hit_w, note_w]
            else:
                col_widths = [claim_w, rest]
        else:
            claim_w = available_width * 0.30
            rest = available_width - claim_w
            hit_w = rest / max(len(hits_chunk), 1)
            col_widths = [claim_w] + [hit_w] * len(hits_chunk)

        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(_matrix_table_style(len(header)))
        story.append(table)
    return story


def claim_chart_section(chart: ChartTable, styles: dict, *, available_width: float) -> List:
    story: List = [_p('Claim Chart', 'section_title', styles)]
    if not chart.rows:
        story.append(_p('No claim chart rows for this infringement.', 'body_center', styles))
        return story

    # Hide Justification column when every row has empty justification
    include_justification = any((row.justification or '').strip() for row in chart.rows)

    if include_justification:
        header = [
            _p('Reference Claim', 'table_header', styles),
            _p('Infringing Claim', 'table_header', styles),
            _p('Similarity', 'table_header', styles),
            _p('Justification', 'table_header', styles),
        ]
        col_widths = [
            available_width * 0.28,
            available_width * 0.28,
            available_width * 0.12,
            available_width * 0.32,
        ]
    else:
        header = [
            _p('Reference Claim', 'table_header', styles),
            _p('Infringing Claim', 'table_header', styles),
            _p('Similarity', 'table_header', styles),
        ]
        col_widths = [
            available_width * 0.42,
            available_width * 0.42,
            available_width * 0.16,
        ]

    data = [header]
    for row in chart.rows:
        ref_idx = row.ref_claim_index if row.ref_claim_index is not None else 0
        ref_cell = _claim_label_paragraph(ref_idx, row.ref_claim or '—', styles)
        cells = [
            ref_cell,
            _p(row.inf_claim or '—', 'table_cell_left', styles),
            _p(_pct(row.similarity), 'table_cell', styles),
        ]
        if include_justification:
            cells.append(_p(row.justification or '—', 'justification', styles))
        data.append(cells)

    chart_style_cmds = [
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
    ]
    chart_style = TableStyle(chart_style_cmds)

    header_row = data[0]
    for row_cells in data[1:]:
        table = Table([header_row, row_cells], colWidths=col_widths, repeatRows=1)
        table.setStyle(chart_style)
        story.append(KeepTogether([table, Spacer(1, 3 * mm)]))

    story.extend(attorney_notes_section(chart.attorney_notes, styles))
    return story


def documents_section(
    hit: InfringementHit,
    styles: dict,
    *,
    appendix_notes: Optional[Sequence[str]] = None,
) -> List:
    """
    Documents section header + short inventory.

    Actual PDF/HTML listing pages are appended after the ReportLab body via
    ``collect_infringement_document_pdfs`` (merged by the builder).
    """
    story: List = [_p('Documents / Listing Pages', 'section_title', styles)]
    if not hit.documents and not hit.url:
        story.append(_p(
            'No documents or listing URLs recorded for this infringement.',
            'body_center',
            styles,
        ))
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

    if appendix_notes:
        story.append(Spacer(1, 2 * mm))
        manual = [n for n in appendix_notes if 'MANUAL ACCESS REQUIRED' in (n or '')]
        other = [n for n in appendix_notes if 'MANUAL ACCESS REQUIRED' not in (n or '')]
        if manual:
            story.append(_p(
                '<b>Manual access required</b> — automated page fetching was disabled '
                'by host firewalls/WAFs for the URL(s) below. Open them manually in a browser.',
                'body',
                styles,
            ))
            story.append(Spacer(1, 1 * mm))
            for note in manual:
                # Keep the full note (includes the URL) but bold the lead-in
                safe = (note or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                if safe.startswith('MANUAL ACCESS REQUIRED'):
                    rest = safe[len('MANUAL ACCESS REQUIRED'):].lstrip(' —-')
                    story.append(_p_markup(
                        f'<b>MANUAL ACCESS REQUIRED</b> — {rest}',
                        'attorney_note',
                        styles,
                    ))
                else:
                    story.append(_p(note, 'attorney_note', styles))
            if other:
                story.append(Spacer(1, 2 * mm))
        for note in other:
            story.append(_p(note, 'attorney_note', styles))
    else:
        story.append(Spacer(1, 2 * mm))
        story.append(_p(
            'Source document and listing pages follow this section when available.',
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
    available_width: Optional[float] = None,
) -> List:
    """
    Full-width 3-column index table (transparent borders):
      id (center) | title / subtitle (left) | page (right)
    """
    story: List = [
        _p(title, 'section_title', styles),
        Spacer(1, 4 * mm),
    ]
    if not entries:
        story.append(_p('No sections to index.', 'body_center', styles))
        return story

    width = available_width if available_width is not None else available_content_width()
    col_widths = [width * 0.28, width * 0.60, width * 0.12]

    id_style = ParagraphStyle(
        'PGIndexId',
        parent=styles['index_entry'],
        alignment=1,  # TA_CENTER
    )
    title_style = styles['index_entry']
    title_sub_style = styles['index_sub']
    page_style = ParagraphStyle(
        'PGIndexPage',
        parent=styles['index_entry'],
        alignment=2,  # TA_RIGHT
    )

    def _cell(text: str, style) -> Paragraph:
        safe = (
            (text or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('\n', '<br/>')
        )
        return Paragraph(safe, style)

    data = []
    for e in entries:
        page = page_map.get(e.marker, '')
        page_str = str(page) if page != '' else ''
        id_text = e.entry_id or ''
        title_text = e.title or ''
        t_style = title_sub_style if e.level else title_style
        data.append([
            _cell(id_text, id_style),
            _cell(title_text, t_style),
            _cell(page_str, page_style),
        ])

    table = Table(data, colWidths=col_widths, repeatRows=0)
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        # Transparent / no borders — alignment only
        ('BOX', (0, 0), (-1, -1), 0, colors.Color(0, 0, 0, alpha=0)),
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.Color(0, 0, 0, alpha=0)),
    ]))
    story.append(table)
    return story


def available_content_width(pagesize=S.PAGE_PORTRAIT) -> float:
    w, _ = pagesize
    return w - S.MARGIN_LEFT - S.MARGIN_RIGHT


def patent_cover_section(patent: PatentInfo, styles: dict) -> List:
    """Cover-style opening with reference patent identity and details (no keywords/search limits)."""
    return patent_info_section(patent, styles)
