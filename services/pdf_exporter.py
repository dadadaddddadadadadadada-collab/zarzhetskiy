from pathlib import Path
from html import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models.scenario import Scenario
from services.duration_calculator import DurationCalculator


class PdfExporter:
    @staticmethod
    def find_cyrillic_font() -> str:
        possible_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]

        for path in possible_paths:
            if Path(path).exists():
                return path

        raise RuntimeError(
            "Не найден шрифт с поддержкой кириллицы. "
            "Проверьте наличие Arial, Calibri или DejaVu Sans."
        )

    @staticmethod
    def register_font() -> str:
        font_name = "AppCyrillicFont"
        font_path = PdfExporter.find_cyrillic_font()

        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))

        return font_name

    @staticmethod
    def export_scenario_to_pdf(scenario: Scenario, file_path: str):
        font_name = PdfExporter.register_font()

        document = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="TitleStyle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=18,
        )

        heading_style = ParagraphStyle(
            name="HeadingStyle",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=14,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
        )

        normal_style = ParagraphStyle(
            name="NormalStyle",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=11,
            leading=15,
            spaceAfter=8,
        )

        note_style = ParagraphStyle(
            name="NoteStyle",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=10,
            leading=14,
            leftIndent=16,
            spaceAfter=6,
        )

        content = []

        title = scenario.title.strip() or "Без названия"
        content.append(Paragraph(escape(title), title_style))

        full_text = " ".join(block.text for block in scenario.blocks)
        minutes = DurationCalculator.calculate_minutes(full_text)
        formatted_duration = DurationCalculator.format_duration(minutes)

        content.append(Paragraph(f"<b>Дата создания:</b> {escape(scenario.created_at)}", normal_style))
        content.append(Paragraph(f"<b>Дата изменения:</b> {escape(scenario.updated_at)}", normal_style))
        content.append(Paragraph(f"<b>Примерная длительность озвучивания:</b> {escape(formatted_duration)}", normal_style))

        if scenario.template_name:
            content.append(Paragraph(f"<b>Использованный шаблон:</b> {escape(scenario.template_name)}", normal_style))

        content.append(Spacer(1, 12))

        sorted_blocks = sorted(scenario.blocks, key=lambda block: block.order_index)

        for block in sorted_blocks:
            block_title = block.title.strip() or "Без названия"
            content.append(Paragraph(escape(block_title), heading_style))

            block_text = block.text.strip()

            if block_text:
                paragraphs = block_text.split("\n")

                for paragraph in paragraphs:
                    if paragraph.strip():
                        content.append(Paragraph(escape(paragraph.strip()), normal_style))
                    else:
                        content.append(Spacer(1, 6))
            else:
                content.append(Paragraph("<i>Текст блока отсутствует.</i>", normal_style))

            if block.notes:
                content.append(Paragraph("<b>Заметки:</b>", normal_style))

                for note in block.notes:
                    if note.text.strip():
                        content.append(
                            Paragraph(
                                f"• {escape(note.text.strip())}",
                                note_style,
                            )
                        )

            content.append(Spacer(1, 10))

        document.build(content)