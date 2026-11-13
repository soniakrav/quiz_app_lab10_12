"""
visualization.py — побудова графіків за допомогою matplotlib.

Клас ChartBuilder створює п'ять різних діаграм (стовпчикова, лінійна,
горизонтальна стовпчикова, кругова, гістограма). Кожна має заголовок,
підписи осей, легенду та сітку. Графіки автоматично зберігаються у файли
PNG, а також усі разом у один PDF.
"""

from collections import namedtuple
from pathlib import Path

import matplotlib

matplotlib.use("Agg")   # малюємо у файли, без окремого вікна (не заважає tkinter)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from matplotlib.patches import Patch

ChartInfo = namedtuple("ChartInfo", ["title", "path"])

GREEN, RED, BLUE, GRAY = "#2e7d32", "#c62828", "#1565c0", "#555555"


class VisualizationError(Exception):
    """Не вдалося побудувати або зберегти графік."""


class ChartBuilder:
    def __init__(self, out_dir, pass_percent=60):
        self.out_dir = Path(out_dir)
        self.pass_percent = pass_percent

    # допоміжні методи
    @staticmethod
    def _decorate(ax, title, xlabel, ylabel, grid_axis="both"):
        """Єдине оформлення: заголовок, підписи осей, сітка."""
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, axis=grid_axis, linestyle=":", alpha=0.6)
        ax.set_axisbelow(True)

    @staticmethod
    def _new_figure():
        return plt.subplots(figsize=(7, 4.2))

    #  окремі діаграми
    def _attempts_bar(self, history):
        """1. Стовпчикова діаграма: результат кожної спроби."""
        data = history.tail(20)
        numbers = list(data.index + 1)
        colors = [GREEN if p >= self.pass_percent else RED for p in data["percent"]]
        fig, ax = self._new_figure()
        ax.bar(numbers, data["percent"], color=colors)
        ax.axhline(self.pass_percent, color=GRAY, linestyle="--", linewidth=1.2)
        ax.set_ylim(0, 125)    # запас зверху для легенди
        ax.set_yticks(range(0, 101, 20))
        ax.set_xticks(numbers)
        ax.legend(handles=[
            Patch(color=GREEN, label="Тест складено"),
            Patch(color=RED, label="Тест не складено"),
            Line2D([0], [0], color=GRAY, linestyle="--",
                   label=f"Прохідний бал ({self.pass_percent}%)"),
        ], loc="upper center", ncol=3, fontsize=8)
        self._decorate(ax, "Результати окремих спроб", "Номер спроби",
                       "Результат, %", grid_axis="y")
        fig.tight_layout()
        return fig

    def _dynamics_line(self, history):
        """2. Лінійний графік: динаміка результатів."""
        data = history.tail(30)
        numbers = list(data.index + 1)
        fig, ax = self._new_figure()
        ax.plot(numbers, data["percent"], marker="o", color=BLUE, label="Результат")
        if len(data) >= 3:
            moving = data["percent"].rolling(3, min_periods=1).mean()
            ax.plot(numbers, moving, linestyle="--", color="#ef6c00",
                    label="Ковзне середнє (3 спроби)")
        ax.set_ylim(0, 125)
        ax.set_yticks(range(0, 101, 20))
        ax.legend(loc="upper center", ncol=2, fontsize=8)
        self._decorate(ax, "Динаміка результатів", "Номер спроби", "Результат, %")
        fig.tight_layout()
        return fig

    def _category_bar(self, categories):
        """3. Горизонтальна діаграма: успішність за категоріями."""
        fig, ax = self._new_figure()
        ax.barh(categories["category"], categories["percent"], color=BLUE,
                label="Правильні відповіді, %")
        for i, value in enumerate(categories["percent"]):
            ax.text(value + 1, i, f"{value:.0f}%", va="center", fontsize=9)
        ax.set_xlim(0, 110)
        ax.legend(loc="lower right", fontsize=8)
        self._decorate(ax, "Успішність за категоріями", "Правильних відповідей, %",
                       "Категорія", grid_axis="x")
        fig.tight_layout()
        return fig

    def _correctness_pie(self, answers):
        """4. Кругова діаграма: частка правильних і неправильних відповідей."""
        right = int(answers["is_correct"].sum())
        wrong = int(len(answers) - right)
        fig, ax = self._new_figure()
        ax.pie([right, wrong], colors=[GREEN, RED], startangle=90,
               autopct=lambda p: f"{p:.1f}%" if p > 0 else "",
               wedgeprops={"edgecolor": "white"}, textprops={"color": "white"})
        ax.legend(handles=[Patch(color=GREEN, label=f"Правильні ({right})"),
                           Patch(color=RED, label=f"Неправильні ({wrong})")],
                  loc="lower right", fontsize=9)
        ax.set_title("Співвідношення правильних і неправильних відповідей",
                     fontsize=12, fontweight="bold")
        fig.tight_layout()
        return fig

    def _time_hist(self, answers):
        """5. Гістограма: час, витрачений на відповідь."""
        times = answers["time_spent"]
        fig, ax = self._new_figure()
        bins = max(3, min(10, len(times) // 3 or 3))
        ax.hist(times, bins=bins, color="#6a1b9a", edgecolor="white",
                label="Кількість відповідей")
        ax.axvline(times.mean(), color="#ef6c00", linestyle="--", linewidth=1.5,
                   label=f"Середнє: {times.mean():.1f} с")
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))   # лише цілі числа
        ax.set_ylim(top=ax.get_ylim()[1] * 1.25)   # місце для легенди
        ax.legend(loc="upper center", ncol=2, fontsize=8)
        self._decorate(ax, "Розподіл часу відповіді на питання",
                       "Час на відповідь, с", "Кількість відповідей", grid_axis="y")
        fig.tight_layout()
        return fig

    #  головний метод
    def build_all(self, history, answers, categories):
        """Будує всі графіки, зберігає PNG та загальний PDF.

        Повертає (список ChartInfo, шлях до PDF).
        """
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise VisualizationError(f"Не вдалося створити папку для графіків: {err}") from err

        builders = [
            ("Результати спроб", "attempts_bar.png", lambda: self._attempts_bar(history)),
            ("Динаміка", "dynamics_line.png", lambda: self._dynamics_line(history)),
            ("За категоріями", "categories_bar.png", lambda: self._category_bar(categories)),
            ("Правильні/неправильні", "correctness_pie.png", lambda: self._correctness_pie(answers)),
            ("Час відповідей", "time_hist.png", lambda: self._time_hist(answers)),
        ]
        charts, figures = [], []
        pdf_path = self.out_dir / "all_charts.pdf"
        try:
            with PdfPages(pdf_path) as pdf:
                for title, filename, make in builders:
                    fig = make()
                    figures.append(fig)
                    path = self.out_dir / filename
                    fig.savefig(path, dpi=100)
                    pdf.savefig(fig)
                    charts.append(ChartInfo(title, path))
        except OSError as err:
            raise VisualizationError(f"Не вдалося зберегти графіки: {err}") from err
        except Exception as err:   # помилка matplotlib під час побудови
            raise VisualizationError(f"Помилка під час побудови графіків: {err}") from err
        finally:
            for fig in figures:
                plt.close(fig)
        return charts, pdf_path
