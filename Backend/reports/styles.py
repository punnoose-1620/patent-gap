"""
Shared visual constants and ReportLab styles for Patent Gap PDF reports.

Global print rules (all report types):
- Never truncate with ellipsis; full text wraps and row heights grow.
- Default alignment: center. Claims and justifications are left-aligned.
- Claim matrix / claim chart tables use dark-green borders (--deep).
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
# Brand tokens (aligned with patent-gap.css)
DEEP = colors.HexColor('#0D2818')
ACCENT = colors.HexColor('#2E7D32')
BG = colors.HexColor('#FAFAF7')
SURF = colors.HexColor('#F5F2EC')
INK = colors.HexColor('#1A1A1A')
INK2 = colors.HexColor('#52524C')
INK3 = colors.HexColor('#8C8C84')
RULE = colors.Color(13 / 255, 40 / 255, 24 / 255, alpha=0.12)
WHITE = colors.white

# Matrix / chart border — menu-bar dark green
TABLE_BORDER = DEEP
TABLE_BORDER_WIDTH = 0.8

# Tick when similarity >= this (matches high-risk dashboard threshold)
MATCH_TICK_THRESHOLD = 0.8

# Switch full claim matrix to landscape when hit count exceeds this
LANDSCAPE_HIT_THRESHOLD = 7

PAGE_PORTRAIT = A4
PAGE_LANDSCAPE = landscape(A4)

MARGIN_LEFT = 18 * mm
MARGIN_RIGHT = 18 * mm
MARGIN_TOP = 22 * mm
MARGIN_BOTTOM = 18 * mm

WATERMARK_TEXT = 'Patent Gap AI'
BRAND_NAME = 'Patent Gap AI'

# Header/footer band
HEADER_HEIGHT = 14 * mm
FOOTER_HEIGHT = 12 * mm


def _safe_register_fonts():
    """Best-effort register of nicer fonts; fall back to Helvetica family."""
    # Intentionally minimal — ReportLab built-ins are always available.
    return {
        'body': 'Helvetica',
        'body_bold': 'Helvetica-Bold',
        'body_oblique': 'Helvetica-Oblique',
        'display': 'Helvetica-Bold',
        'mono': 'Courier',
    }


FONTS = _safe_register_fonts()


def build_paragraph_styles():
    """Return a dict of named ParagraphStyles used across components."""
    base = getSampleStyleSheet()
    styles = {
        'body': ParagraphStyle(
            'PGBody',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=9,
            leading=12,
            textColor=INK,
            alignment=TA_JUSTIFY,
        ),
        'body_center': ParagraphStyle(
            'PGBodyCenter',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=9,
            leading=12,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        'claim': ParagraphStyle(
            'PGClaim',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=9,
            leading=12,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        'justification': ParagraphStyle(
            'PGJustification',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=8.5,
            leading=11,
            textColor=INK2,
            alignment=TA_LEFT,
        ),
        'note': ParagraphStyle(
            'PGNote',
            parent=base['Normal'],
            fontName=FONTS['body_oblique'],
            fontSize=8,
            leading=10.5,
            textColor=INK2,
            alignment=TA_LEFT,
            leftIndent=8,
        ),
        'attorney_note': ParagraphStyle(
            'PGAttorneyNote',
            parent=base['Normal'],
            fontName=FONTS['body_oblique'],
            fontSize=8,
            leading=10.5,
            textColor=INK3,
            alignment=TA_LEFT,
        ),
        'section_title': ParagraphStyle(
            'PGSectionTitle',
            parent=base['Heading2'],
            fontName=FONTS['body_bold'],
            fontSize=12,
            leading=15,
            textColor=DEEP,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=6,
        ),
        'hero_id': ParagraphStyle(
            'PGHeroId',
            parent=base['Heading1'],
            fontName=FONTS['display'],
            fontSize=22,
            leading=26,
            textColor=DEEP,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=4,
        ),
        'hero_title': ParagraphStyle(
            'PGHeroTitle',
            parent=base['Heading1'],
            fontName=FONTS['display'],
            fontSize=16,
            leading=20,
            textColor=DEEP,
            alignment=TA_CENTER,
            spaceBefore=2,
            spaceAfter=12,
        ),
        'meta_label': ParagraphStyle(
            'PGMetaLabel',
            parent=base['Normal'],
            fontName=FONTS['body_bold'],
            fontSize=8,
            leading=10,
            textColor=INK3,
            alignment=TA_CENTER,
        ),
        'meta_value': ParagraphStyle(
            'PGMetaValue',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=9,
            leading=12,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        'table_cell': ParagraphStyle(
            'PGTableCell',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=7.5,
            leading=9.5,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        'table_cell_left': ParagraphStyle(
            'PGTableCellLeft',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=7.5,
            leading=9.5,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        'table_header': ParagraphStyle(
            'PGTableHeader',
            parent=base['Normal'],
            fontName=FONTS['body_bold'],
            fontSize=8,
            leading=10,
            textColor=WHITE,
            alignment=TA_CENTER,
        ),
        'cover_title': ParagraphStyle(
            'PGCoverTitle',
            parent=base['Heading1'],
            fontName=FONTS['display'],
            fontSize=24,
            leading=30,
            textColor=DEEP,
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        'cover_subtitle': ParagraphStyle(
            'PGCoverSubtitle',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=11,
            leading=15,
            textColor=INK2,
            alignment=TA_CENTER,
            spaceAfter=24,
        ),
        'cover_meta': ParagraphStyle(
            'PGCoverMeta',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=10,
            leading=14,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        'index_entry': ParagraphStyle(
            'PGIndexEntry',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=10,
            leading=14,
            textColor=INK,
            alignment=TA_LEFT,
        ),
        'index_sub': ParagraphStyle(
            'PGIndexSub',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=9,
            leading=12,
            textColor=INK2,
            alignment=TA_LEFT,
            leftIndent=18,
        ),
        'header': ParagraphStyle(
            'PGHeader',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=7.5,
            leading=9,
            textColor=INK2,
            alignment=TA_LEFT,
        ),
        'header_right': ParagraphStyle(
            'PGHeaderRight',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=7.5,
            leading=9,
            textColor=INK2,
            alignment=TA_RIGHT,
        ),
        'footer': ParagraphStyle(
            'PGFooter',
            parent=base['Normal'],
            fontName=FONTS['body'],
            fontSize=7.5,
            leading=9,
            textColor=INK3,
            alignment=TA_CENTER,
        ),
        'watermark': ParagraphStyle(
            'PGWatermark',
            parent=base['Normal'],
            fontName=FONTS['body_oblique'],
            fontSize=7.5,
            leading=9,
            textColor=INK3,
            alignment=TA_RIGHT,
        ),
    }
    return styles
