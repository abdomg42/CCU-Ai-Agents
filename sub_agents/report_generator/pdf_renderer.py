"""Générateur de rapport PDF via fpdf2.

Avantages par rapport au générateur "pur Python" précédent :
- placement d'images (logo) natif,
- retour à la ligne automatique des paragraphes,
- mise en page compacte (tableaux, badges colorés, en-tête/pied de page).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from config.settings import get_settings


# Chemins courants de polices Unicode sur Windows / Linux / macOS
_UNICODE_FONT_CANDIDATES = [
    # Windows
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    # Linux (Debian/Ubuntu, RHEL/CentOS, Alpine)
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    # macOS
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]


def _find_unicode_font() -> dict[str, str] | None:
    """Trouve une police Unicode système avec sa version grasse."""
    for regular, bold in _UNICODE_FONT_CANDIDATES:
        reg_path = Path(regular)
        bold_path = Path(bold)
        if reg_path.exists():
            return {
                "": str(reg_path),
                "B": str(bold_path) if bold_path.exists() else str(reg_path),
            }
    return None


PAGE_WIDTH_MM = 210
PAGE_HEIGHT_MM = 297

MARGIN_LEFT = 15
MARGIN_RIGHT = 15
MARGIN_TOP = 15
MARGIN_BOTTOM = 15

LOGO_PATH = Path(__file__).resolve().parents[2] / "reports" / "logo.png"
LOGO_WIDTH_MM = 65

DISCLAIMER = (
    "This report is generated automatically by the CCU Diagnostic Agent. "
    "No technical action is executed on production systems."
)

# Couleurs RVB normalisées 0..1 -> fpdf attend 0..255
BRAND_DARK = (0, 43, 82)
BRAND_MID = (30, 89, 153)
BRAND_LIGHT = (230, 240, 250)
GREY_LABEL = (102, 102, 102)
GREY_FOOTER = (128, 128, 128)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

CONFIDENCE_COLOURS = {
    "high": (26, 140, 51),
    "medium": (217, 140, 0),
    "low": (179, 38, 38),
    "unknown": (102, 102, 102),
}

PRIORITY_COLOURS = {
    "p1": (179, 26, 26),
    "p2": (217, 115, 0),
    "p3": (26, 128, 51),
    "unknown": (102, 102, 102),
}


def _safe(value: Any, default: str = "--") -> str:
    return str(value) if value not in (None, "", "-", "*") else default


def _confidence_label(confidence: str | None) -> str:
    key = (confidence or "").lower()
    if key in {"forte", "high", "élevée"}:
        return "high"
    if key in {"moyenne", "medium"}:
        return "medium"
    if key in {"faible", "low"}:
        return "low"
    return "unknown"


def _priority_colour(priority: str) -> tuple[int, int, int]:
    return PRIORITY_COLOURS.get(str(priority).lower().replace(" ", ""), PRIORITY_COLOURS["unknown"])


def _confidence_colour(confidence: str | None) -> tuple[int, int, int]:
    return CONFIDENCE_COLOURS.get(_confidence_label(confidence), CONFIDENCE_COLOURS["unknown"])


def _format_iso(iso: str) -> str:
    """Raccourcit une date ISO en format lisible."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso


class _DiagnosticPDF(FPDF):
    """FPDF personnalisé avec en-tête (logo) et pied de page."""

    def __init__(self, report_id: str = "") -> None:
        super().__init__()
        self.report_id = report_id
        self.set_auto_page_break(auto=True, margin=MARGIN_BOTTOM)
        self.set_margins(MARGIN_LEFT, MARGIN_TOP, MARGIN_RIGHT)

        # Police Unicode si disponible, sinon Helvetica (Latin-1)
        font_family = "ReportFont"
        font_files = _find_unicode_font()
        if font_files:
            for style, path in font_files.items():
                self.add_font(font_family, style, path)
        else:
            # Fallback : on reste sur Helvetica et on nettoiera le texte
            font_family = "Helvetica"
        self._font_family = font_family

    def header(self) -> None:
        # Logo sur fond blanc en haut à gauche
        logo_path = self._logo_path()
        logo_height = LOGO_WIDTH_MM * (371 / 1280)  # ratio du logo Inetum
        if logo_path.exists():
            self.image(str(logo_path), x=MARGIN_LEFT, y=4, w=LOGO_WIDTH_MM)

        # Titre et ID du rapport à droite, alignés verticalement avec le logo
        title_y = 4 + (logo_height / 2) - 6
        self.set_xy(MARGIN_LEFT + LOGO_WIDTH_MM + 8, title_y)
        self.set_font(self._font_family, "B", 14)
        self.set_text_color(*BRAND_DARK)
        self.cell(0, 9, "CCU DIAGNOSTIC REPORT", align="L")

        self.set_xy(-MARGIN_RIGHT - 70, title_y + 7)
        self.set_font(self._font_family, "", 8)
        self.set_text_color(*GREY_LABEL)
        self.cell(70, 5, self.report_id, align="R")

        # Bandeau de marque sous le logo (fond bleu foncé)
        self.set_fill_color(*BRAND_DARK)
        self.rect(0, 22, PAGE_WIDTH_MM, 7, style="F")

        # Trait de séparation
        self.set_draw_color(*BRAND_MID)
        self.set_line_width(0.5)
        self.line(MARGIN_LEFT, 31, PAGE_WIDTH_MM - MARGIN_RIGHT, 31)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_draw_color(*BRAND_MID)
        self.set_line_width(0.3)
        self.line(MARGIN_LEFT, self.get_y(), PAGE_WIDTH_MM - MARGIN_RIGHT, self.get_y())
        self.set_font(self._font_family, "", 7)
        self.set_text_color(*GREY_FOOTER)
        self.cell(0, 5, DISCLAIMER, align="L")
        self.set_x(-MARGIN_RIGHT - 20)
        self.cell(20, 5, f"Page {self.page_no()}", align="R")

    def _logo_path(self) -> Path:
        # Permet d'outrepasser le chemin via les settings si un logo alternatif est défini.
        settings = get_settings()
        custom = getattr(settings, "REPORT_LOGO_PATH", None)
        if custom:
            return Path(custom)
        return LOGO_PATH


class ReportRenderer:
    """Facade conservée pour compatibilité ascendante."""

    def __init__(self) -> None:
        self._pdf: _DiagnosticPDF | None = None

    def add_heading1(self, text: str) -> None:
        pdf = self._pdf
        assert pdf is not None
        pdf.set_font(pdf._font_family, "B", 16)
        pdf.set_text_color(*WHITE)
        pdf.set_fill_color(*BRAND_DARK)
        pdf.set_draw_color(*BRAND_DARK)
        pdf.cell(0, 8, f"  {text}  ", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.ln(2)

    def add_heading2(self, text: str) -> None:
        pdf = self._pdf
        assert pdf is not None
        pdf.set_font(pdf._font_family, "B", 11)
        pdf.set_text_color(*BRAND_MID)
        pdf.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(*BRAND_MID)
        pdf.set_line_width(0.3)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.line(x, y, PAGE_WIDTH_MM - MARGIN_RIGHT, y)
        pdf.ln(1)

    def add_paragraph(self, text: str, size: int = 10) -> None:
        pdf = self._pdf
        assert pdf is not None
        pdf.set_font(pdf._font_family, "", size)
        pdf.set_text_color(*BLACK)
        safe_text = _safe(text, "No information provided")
        pdf.multi_cell(0, 4.5, safe_text)
        pdf.ln(1)

    def add_metadata_block(self, pairs: list[tuple[str, str]]) -> None:
        pdf = self._pdf
        assert pdf is not None

        col1_w = 55
        col2_w = PAGE_WIDTH_MM - MARGIN_LEFT - MARGIN_RIGHT - col1_w
        row_h = 5.5

        pdf.set_fill_color(*BRAND_LIGHT)
        pdf.set_draw_color(*BRAND_MID)
        pdf.set_line_width(0.2)

        # Bordure extérieure
        start_y = pdf.get_y()
        total_h = len(pairs) * row_h + 3
        pdf.rect(MARGIN_LEFT, start_y, PAGE_WIDTH_MM - MARGIN_LEFT - MARGIN_RIGHT, total_h, style="D")

        for i, (label, value) in enumerate(pairs):
            y = start_y + 1.5 + i * row_h
            pdf.set_xy(MARGIN_LEFT + 2, y)
            pdf.set_font(pdf._font_family, "B", 9)
            pdf.set_text_color(*GREY_LABEL)
            pdf.cell(col1_w, row_h, label)

            pdf.set_xy(MARGIN_LEFT + col1_w + 2, y)
            pdf.set_font(pdf._font_family, "", 9)
            pdf.set_text_color(*BLACK)
            display_value = _safe(value)
            if label.lower() in {"generated", "detected"} and display_value not in ("--", "N/A"):
                display_value = _format_iso(display_value)
            pdf.cell(col2_w, row_h, display_value)

        pdf.set_xy(MARGIN_LEFT, start_y + total_h + 1)

    def add_priority_badge(self, priority: str) -> None:
        pdf = self._pdf
        assert pdf is not None
        colour = _priority_colour(priority)
        label = f"  Priority: {str(priority).upper()}  "
        pdf.set_font(pdf._font_family, "B", 9)
        pdf.set_fill_color(*colour)
        pdf.set_text_color(*WHITE)
        pdf.cell(pdf.get_string_width(label) + 4, 7, label, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*BLACK)

    def add_confidence_badge(self, confidence: str | None) -> None:
        pdf = self._pdf
        assert pdf is not None
        colour = _confidence_colour(confidence)
        label = f"  Confidence: {_confidence_label(confidence).upper()}  "
        pdf.set_font(pdf._font_family, "B", 9)
        pdf.set_fill_color(*colour)
        pdf.set_text_color(*WHITE)
        pdf.cell(pdf.get_string_width(label) + 4, 7, label, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*BLACK)

    def add_key_value(self, label: str, value: Any) -> None:
        pdf = self._pdf
        assert pdf is not None
        pdf.set_font(pdf._font_family, "B", 9)
        pdf.set_text_color(*GREY_LABEL)
        pdf.cell(50, 5, f"{label}:")
        pdf.set_font(pdf._font_family, "", 9)
        pdf.set_text_color(*BLACK)
        pdf.cell(0, 5, _safe(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    def add_list(self, items: list[str] | None) -> None:
        pdf = self._pdf
        assert pdf is not None
        pdf.set_font(pdf._font_family, "", 10)
        pdf.set_text_color(*BLACK)
        for item in items or ["No data available"]:
            pdf.set_x(MARGIN_LEFT + 4)
            pdf.cell(4, 5, "\xb7", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.multi_cell(0, 5, _safe(item))
        pdf.ln(1)

    def add_section_break(self) -> None:
        pdf = self._pdf
        assert pdf is not None
        pdf.ln(2)

    def save(self, path: Path) -> Path:
        assert self._pdf is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        self._pdf.output(str(path))
        return path


def generate_diagnostic_report(report: dict[str, Any], output_path: Path) -> Path:
    """Génère un rapport PDF de diagnostic CCU avec logo et mise en page compacte."""
    renderer = ReportRenderer()
    renderer._pdf = _DiagnosticPDF(report_id=_safe(report.get("report_id")))
    pdf = renderer._pdf
    pdf.add_page()

    # L'origine d'écriture commence sous l'en-tête dessiné automatiquement
    pdf.set_xy(MARGIN_LEFT, 33)

    renderer.add_heading1(_safe(report.get("title"), "CCU Diagnostic Report"))

    # Badges côte à côte pour gagner de la place verticale
    renderer.add_priority_badge(report.get("priority"))
    renderer.add_confidence_badge(report.get("confidence_level"))
    pdf.ln(8)

    renderer.add_metadata_block(
        [
            ("Incident ID", _safe(report.get("incident_id"))),
            ("Generated", _safe(report.get("generated_at"))),
            ("Detected", _safe(report.get("detected_at"))),
            ("Client ID", _safe(report.get("client_id"))),
            ("Order ID", _safe(report.get("order_id"))),
            ("Product Type", _safe(report.get("product_type"))),
            ("Category", _safe(report.get("category"))),
        ]
    )

    renderer.add_heading2("What Happened")
    renderer.add_paragraph(report.get("what_happened", ""))

    renderer.add_heading2("Root Cause")
    renderer.add_paragraph(report.get("root_cause", "undetermined"))

    renderer.add_heading2("Sources")
    renderer.add_list(report.get("sources"))

    renderer.add_heading2("Similar Incident Lookup")
    mapping_status = report.get("mapping_status", "created_new")
    renderer.add_key_value("Status", mapping_status.replace("_", " "))
    renderer.add_key_value("Ticket ID", _safe(report.get("mapping_ticket_id")))
    renderer.add_key_value("Similarity Score", _safe(report.get("mapping_score")))

    renderer.add_heading2("Recommendation")
    renderer.add_paragraph(report.get("recommendation", ""))

    return renderer.save(output_path)
