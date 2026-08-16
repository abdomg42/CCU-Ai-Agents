"""Générateur de rapport PDF pur Python (sans HTML/WeasyPrint).

Génère un PDF A4 structuré directement via des opérateurs PDF bas niveau.
Aucune dépendance externe (Jinja2/WeasyPrint/Pango) n'est requise.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

Colour = tuple[float, float, float]

PAGE_WIDTH = 595
PAGE_HEIGHT = 842

MARGIN_LEFT = 50
MARGIN_RIGHT = 50
MARGIN_TOP = 80
MARGIN_BOTTOM = 60

LINE_HEIGHT = 14
LINE_HEIGHT_LARGE = 28

CHARS_PER_LINE = 90
LABEL_COLUMN_OFFSET = 160

BULLET = "\xb7"

DISCLAIMER = (
    "This report is generated automatically by the CCU Diagnostic Agent. "
    "No technical action is executed on production systems."
)

BLACK: Colour = (0.0, 0.0, 0.0)
WHITE: Colour = (1.0, 1.0, 1.0)
GREY_LABEL: Colour = (0.4, 0.4, 0.4)
BRAND_DARK: Colour = (0.0, 0.2, 0.4)
BRAND_MID: Colour = (0.12, 0.35, 0.6)
BRAND_LIGHT: Colour = (0.9, 0.94, 0.98)
RULE_LIGHT: Colour = (0.82, 0.86, 0.9)
PAGE_NUM_C: Colour = (0.75, 0.85, 0.95)

CONFIDENCE_COLOURS: dict[str, Colour] = {
    "high": (0.1, 0.55, 0.2),
    "medium": (0.85, 0.55, 0.0),
    "low": (0.7, 0.15, 0.15),
    "unknown": (0.4, 0.4, 0.4),
}

PRIORITY_COLOURS: dict[str, Colour] = {
    "p1": (0.7, 0.1, 0.1),
    "p2": (0.85, 0.45, 0.0),
    "p3": (0.1, 0.5, 0.2),
    "unknown": (0.4, 0.4, 0.4),
}


def _escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


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


def _priority_colour(priority: str) -> Colour:
    return PRIORITY_COLOURS.get(str(priority).lower().replace(" ", ""), PRIORITY_COLOURS["unknown"])


def _confidence_colour(confidence: str | None) -> Colour:
    return CONFIDENCE_COLOURS.get(_confidence_label(confidence), CONFIDENCE_COLOURS["unknown"])


@dataclass
class _PDFBuilder:
    _pages: list[list[str]] = field(default_factory=list)
    _current_page: list[str] = field(default_factory=list)
    _page_number: int = field(default=1)
    current_y: int = PAGE_HEIGHT - MARGIN_TOP

    def _advance(self, amount: int) -> None:
        self.current_y -= amount

    def _ensure_space(self, needed: int) -> None:
        if self.current_y < MARGIN_BOTTOM + needed:
            self._new_page()

    def _new_page(self) -> None:
        if self._current_page:
            self._pages.append(self._current_page)
        self._current_page = []
        self._page_number += 1
        self.current_y = PAGE_HEIGHT - MARGIN_TOP

    @staticmethod
    def _text_op(text: str, x: float, y: float, size: int, colour: Colour) -> str:
        r, g, b = colour
        return (
            f"BT /F1 {size} Tf {x:.1f} {y:.1f} Td "
            f"{r:.3f} {g:.3f} {b:.3f} rg ({_escape(text)}) Tj ET"
        )

    @staticmethod
    def _rect_op(x: float, y: float, w: float, h: float, colour: Colour) -> str:
        r, g, b = colour
        return f"{r:.3f} {g:.3f} {b:.3f} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f"

    @staticmethod
    def _line_op(
        x1: float, y1: float, x2: float, y2: float, colour: Colour, width: float = 0.5
    ) -> str:
        r, g, b = colour
        return (
            f"{width:.2f} w {r:.3f} {g:.3f} {b:.3f} RG "
            f"{x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S"
        )

    def _emit(self, op: str) -> None:
        self._current_page.append(op)

    def draw_text(
        self, text: str, x: float, size: int, colour: Colour = BLACK, advance: bool = True
    ) -> None:
        self._emit(self._text_op(text, x, self.current_y, size, colour))
        if advance:
            self._advance(LINE_HEIGHT)

    def draw_rect(self, x: float, y: float, w: float, h: float, colour: Colour = BRAND_LIGHT) -> None:
        self._emit(self._rect_op(x, y, w, h, colour))

    def draw_line(
        self, x1: float, y1: float, x2: float, y2: float, colour: Colour = BLACK, width: float = 0.5
    ) -> None:
        self._emit(self._line_op(x1, y1, x2, y2, colour, width))

    def build(self, path: Path, total_pages: int) -> None:
        if self._current_page:
            self._pages.append(self._current_page)

        objects: list[str] = []

        def add_obj(content: str) -> int:
            objects.append(content)
            return len(objects)

        font_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        page_ids: list[int] = []
        content_ids: list[int] = []

        for page_idx, page in enumerate(self._pages, 1):
            ops = list(page)

            br, bg, bb = BRAND_DARK
            ops.insert(0, f"{br:.3f} {bg:.3f} {bb:.3f} rg 0 {PAGE_HEIGHT - 50:.1f} {PAGE_WIDTH:.1f} 50 re f")
            ops.insert(1, self._text_op("CCU DIAGNOSTIC REPORT", 50, PAGE_HEIGHT - 22, 9, WHITE))
            ops.insert(
                2,
                self._text_op(
                    f"Page {page_idx} of {total_pages}", PAGE_WIDTH - 110, PAGE_HEIGHT - 22, 8, PAGE_NUM_C
                ),
            )

            footer_y = MARGIN_BOTTOM - 20
            ops.append(
                self._line_op(
                    MARGIN_LEFT, footer_y + 12, PAGE_WIDTH - MARGIN_RIGHT, footer_y + 12, BRAND_DARK, 0.5
                )
            )
            ops.append(self._text_op(DISCLAIMER, MARGIN_LEFT, footer_y, 7, GREY_LABEL))

            stream = "\n".join(ops)
            enc_len = len(stream.encode("latin-1", "replace"))
            content_id = add_obj(f"<< /Length {enc_len} >>\nstream\n{stream}\nendstream")
            content_ids.append(content_id)
            page_ids.append(add_obj(""))

        kids = " ".join(f"{p} 0 R" for p in page_ids)
        pages_id = add_obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")

        for i, pid in enumerate(page_ids):
            objects[pid - 1] = (
                "<< /Type /Page "
                f"/Parent {pages_id} 0 R "
                "/MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                f"/Contents {content_ids[i]} 0 R >>"
            )

        catalog_id = add_obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

        parts: list[str] = ["%PDF-1.4\n"]
        offsets: list[int] = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(sum(len(p.encode("latin-1", "replace")) for p in parts))
            parts.append(f"{i} 0 obj\n{obj}\nendobj\n")

        xref_offset = sum(len(p.encode("latin-1", "replace")) for p in parts)
        parts.append(f"xref\n0 {len(objects) + 1}\n")
        parts.append("0000000000 65535 f \n")
        for off in offsets[1:]:
            parts.append(f"{off:010d} 00000 n \n")
        parts.append(
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes("".join(parts).encode("latin-1", "replace"))


class ReportRenderer:
    def __init__(self) -> None:
        self._pdf = _PDFBuilder()

    def add_heading1(self, text: str) -> None:
        self._pdf._ensure_space(60)
        band_h = 40
        self._pdf.draw_rect(0, self._pdf.current_y - band_h + 24, PAGE_WIDTH, band_h, BRAND_DARK)
        self._pdf.draw_text(text, MARGIN_LEFT, 20, WHITE)
        self._pdf._advance(20)

    def add_heading2(self, text: str) -> None:
        self._pdf._ensure_space(50)
        self._pdf._advance(12)
        self._pdf.draw_text(text, MARGIN_LEFT, 13, BRAND_MID)
        rule_y = self._pdf.current_y + 2
        self._pdf.draw_line(MARGIN_LEFT, rule_y, PAGE_WIDTH - MARGIN_RIGHT, rule_y, BRAND_MID, 0.8)
        self._pdf._advance(8)

    def add_paragraph(self, text: str, size: int = 10) -> None:
        self._pdf._ensure_space(40)
        safe_text = _escape(_safe(text, "No information provided"))
        line_buffer = ""
        for word in safe_text.split():
            if len(line_buffer) + len(word) > CHARS_PER_LINE:
                self._pdf.draw_text(line_buffer, MARGIN_LEFT, size)
                self._pdf._ensure_space(20)
                line_buffer = word
            else:
                line_buffer += (" " if line_buffer else "") + word
        if line_buffer:
            self._pdf.draw_text(line_buffer, MARGIN_LEFT, size)
        self._pdf._advance(6)

    def add_key_value(self, label: str, value: Any) -> None:
        self._pdf._ensure_space(20)
        self._pdf._emit(
            self._pdf._text_op(
                _escape(_safe(label, "N/A")),
                MARGIN_LEFT,
                self._pdf.current_y,
                9,
                GREY_LABEL,
            )
        )
        self._pdf._emit(
            self._pdf._text_op(
                _escape(_safe(value, "Unknown")),
                MARGIN_LEFT + LABEL_COLUMN_OFFSET,
                self._pdf.current_y,
                9,
                BLACK,
            )
        )
        self._pdf._advance(LINE_HEIGHT)

    def add_metadata_block(self, pairs: list[tuple[str, str]]) -> None:
        self._pdf._ensure_space(len(pairs) * LINE_HEIGHT + 24)
        box_top = self._pdf.current_y + 8
        box_h = len(pairs) * LINE_HEIGHT + 14
        self._pdf.draw_rect(
            MARGIN_LEFT,
            box_top - box_h,
            PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT,
            box_h,
            BRAND_LIGHT,
        )
        self._pdf.draw_line(MARGIN_LEFT, box_top, PAGE_WIDTH - MARGIN_RIGHT, box_top, BRAND_MID, 0.4)
        self._pdf.draw_line(
            MARGIN_LEFT,
            box_top - box_h,
            PAGE_WIDTH - MARGIN_RIGHT,
            box_top - box_h,
            BRAND_MID,
            0.4,
        )
        self._pdf._advance(8)
        for label, value in pairs:
            self._pdf._emit(
                self._pdf._text_op(
                    _escape(label),
                    MARGIN_LEFT + 8,
                    self._pdf.current_y,
                    9,
                    GREY_LABEL,
                )
            )
            self._pdf._emit(
                self._pdf._text_op(
                    _escape(value),
                    MARGIN_LEFT + 8 + LABEL_COLUMN_OFFSET,
                    self._pdf.current_y,
                    9,
                    BLACK,
                )
            )
            self._pdf._advance(LINE_HEIGHT)
        self._pdf._advance(10)

    def add_priority_badge(self, priority: str) -> None:
        self._pdf._ensure_space(30)
        colour = _priority_colour(priority)
        label = f"  Priority: {str(priority).upper()}  "
        badge_w = len(label) * 5.8
        self._pdf.draw_rect(MARGIN_LEFT, self._pdf.current_y - 4, badge_w, 17, colour)
        self._pdf._emit(self._pdf._text_op(_escape(label), MARGIN_LEFT, self._pdf.current_y + 2, 9, WHITE))
        self._pdf._advance(24)

    def add_confidence_badge(self, confidence: str | None) -> None:
        self._pdf._ensure_space(30)
        colour = _confidence_colour(confidence)
        label = f"  Confidence: {_confidence_label(confidence).upper()}  "
        badge_w = len(label) * 5.8
        self._pdf.draw_rect(MARGIN_LEFT, self._pdf.current_y - 4, badge_w, 17, colour)
        self._pdf._emit(self._pdf._text_op(_escape(label), MARGIN_LEFT, self._pdf.current_y + 2, 9, WHITE))
        self._pdf._advance(24)

    def add_list(self, items: list[str] | None) -> None:
        for item in items or ["No data available"]:
            self._pdf._ensure_space(20)
            self._pdf._emit(self._pdf._text_op(BULLET, MARGIN_LEFT + 4, self._pdf.current_y, 12, BRAND_MID))
            self._pdf._emit(
                self._pdf._text_op(
                    _escape(_safe(item, "N/A")),
                    MARGIN_LEFT + 18,
                    self._pdf.current_y,
                    9,
                    BLACK,
                )
            )
            self._pdf._advance(LINE_HEIGHT)
        self._pdf._advance(6)

    def add_section_break(self) -> None:
        self._pdf._advance(LINE_HEIGHT_LARGE)

    def save(self, path: Path) -> Path:
        total = len(self._pdf._pages) + (1 if self._pdf._current_page else 0)
        self._pdf.build(path, total)
        return path


def generate_diagnostic_report(report: dict[str, Any], output_path: Path) -> Path:
    """Génère un rapport PDF de diagnostic CCU.

    `report` attend les clés utilisées par `ReportGeneratorAgent._build_report_data`.
    """
    renderer = ReportRenderer()

    renderer.add_heading1(_safe(report.get("title"), "CCU Diagnostic Report"))
    renderer.add_priority_badge(report.get("priority"))
    renderer.add_confidence_badge(report.get("confidence_level"))

    renderer.add_metadata_block(
        [
            ("Report ID", _safe(report.get("report_id"))),
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
