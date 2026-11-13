"""
report.py — автоматичне формування підсумкового HTML-звіту.

У звіт потрапляють: загальні показники, таблиці (історія, категорії,
найскладніші питання) та всі графіки (вбудовуються в файл як зображення,
тому звіт можна пересилати одним файлом).
"""

import base64
import html
from datetime import datetime
from pathlib import Path

CSS = """
body { font-family: Arial, sans-serif; max-width: 900px; margin: 30px auto; color: #222; }
h1 { color: #1565c0; border-bottom: 2px solid #1565c0; padding-bottom: 6px; }
h2 { margin-top: 32px; color: #333; }
table.tbl { border-collapse: collapse; width: 100%; font-size: 14px; }
table.tbl th, table.tbl td { border: 1px solid #bbb; padding: 5px 8px; text-align: left; }
table.tbl th { background: #e3f2fd; }
table.tbl tr:nth-child(even) { background: #fafafa; }
.cards { display: flex; flex-wrap: wrap; gap: 10px; }
.card { background: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 6px;
        padding: 10px 14px; min-width: 190px; }
.card b { display: block; font-size: 22px; color: #2e7d32; }
figure { margin: 18px 0; text-align: center; }
figure img { max-width: 100%; border: 1px solid #ddd; }
figcaption { font-size: 13px; color: #555; }
.footer { margin-top: 40px; font-size: 12px; color: #777; }
"""


class ReportError(Exception):
    """Не вдалося створити звіт."""


class ReportGenerator:
    def __init__(self, out_dir):
        self.out_dir = Path(out_dir)

    @staticmethod
    def _image_tag(chart):
        data = base64.b64encode(Path(chart.path).read_bytes()).decode("ascii")
        return (f'<figure><img src="data:image/png;base64,{data}" '
                f'alt="{html.escape(chart.title)}">'
                f'<figcaption>{html.escape(chart.title)}</figcaption></figure>')

    @staticmethod
    def _table(frame):
        return frame.to_html(index=False, classes="tbl", border=0, escape=True)

    def generate(self, summary, history_table, category_table, hardest_table, charts):
        """Створює HTML-файл і повертає шлях до нього."""
        parts = ["<!DOCTYPE html><html lang='uk'><head><meta charset='utf-8'>",
                 "<title>Звіт про результати тестування</title>",
                 f"<style>{CSS}</style></head><body>",
                 "<h1>Звіт про результати тестування</h1>",
                 "<h2>Загальні показники</h2><div class='cards'>"]
        for name, value in summary.items():
            parts.append(f"<div class='card'>{html.escape(name)}"
                         f"<b>{html.escape(str(value))}</b></div>")
        parts.append("</div>")

        parts.append("<h2>Історія спроб</h2>" + self._table(history_table))
        parts.append("<h2>Успішність за категоріями</h2>" + self._table(category_table))
        parts.append("<h2>Найскладніші питання</h2>" + self._table(hardest_table))

        parts.append("<h2>Графіки</h2>")
        try:
            parts.extend(self._image_tag(c) for c in charts)
        except OSError as err:
            raise ReportError(f"Не вдалося вбудувати графік у звіт: {err}") from err

        parts.append(f"<p class='footer'>Звіт сформовано автоматично "
                     f"{datetime.now():%d.%m.%Y %H:%M}.</p></body></html>")

        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            path = self.out_dir / f"report_{datetime.now():%Y%m%d_%H%M%S}.html"
            path.write_text("\n".join(parts), encoding="utf-8")
        except OSError as err:
            raise ReportError(f"Не вдалося записати звіт: {err}") from err
        return path
