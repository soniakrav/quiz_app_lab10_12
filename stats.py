"""
stats.py — статистичний аналіз результатів за допомогою pandas.

Клас StatisticsAnalyzer читає файли історії, очищає дані (прибирає
некоректні рядки, перетворює типи) і обчислює підсумкові показники.
"""

from pathlib import Path

import pandas as pd

from data_io import ANSWER_COLUMNS, HISTORY_COLUMNS


class StatisticsError(Exception):
    """Не вдалося прочитати або проаналізувати історію результатів."""


class StatisticsAnalyzer:
    def __init__(self, history_path, answers_path):
        self.history_path = Path(history_path)
        self.answers_path = Path(answers_path)
        self.history = pd.DataFrame()
        self.answers = pd.DataFrame()

    #  Крок 1. Імпорт і підготовка даних
    @staticmethod
    def _read(path, required_columns):
        if not path.exists():
            raise StatisticsError(
                "Історія результатів порожня. Спочатку пройдіть хоча б один тест."
            )
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as err:
            raise StatisticsError(f"Файл «{path.name}» пошкоджено: {err}") from err
        except OSError as err:
            raise StatisticsError(f"Не вдалося відкрити «{path.name}»: {err}") from err
        missing = [c for c in required_columns if c not in frame.columns]
        if missing:
            raise StatisticsError(
                f"У файлі «{path.name}» немає стовпців: {', '.join(missing)}."
            )
        return frame

    def load(self):
        """Читає файли й очищає дані. Кидає StatisticsError, якщо даних немає."""
        history = self._read(self.history_path, HISTORY_COLUMNS)
        answers = self._read(self.answers_path, ANSWER_COLUMNS)

        for col in ("total", "correct", "percent", "duration_sec", "passed"):
            history[col] = pd.to_numeric(history[col], errors="coerce")
        history["date"] = pd.to_datetime(history["date"], errors="coerce")
        history = (history.dropna(subset=["date", "total", "percent"])
                          .sort_values("date")
                          .reset_index(drop=True))

        for col in ("is_correct", "time_spent"):
            answers[col] = pd.to_numeric(answers[col], errors="coerce")
        answers = answers.dropna(subset=["is_correct", "time_spent"]).reset_index(drop=True)

        if history.empty or answers.empty:
            raise StatisticsError("У файлах історії немає коректних записів.")
        self.history, self.answers = history, answers

    #  Крок 2. Розрахунки
    def summary(self):
        """Основні показники по всіх спробах."""
        h = self.history
        return {
            "Кількість спроб": int(len(h)),
            "Середній результат, %": round(float(h["percent"].mean()), 1),
            "Найкращий результат, %": round(float(h["percent"].max()), 1),
            "Найгірший результат, %": round(float(h["percent"].min()), 1),
            "Середня тривалість, с": round(float(h["duration_sec"].mean()), 1),
            "Частка складених тестів, %": round(float((h["passed"] == 1).mean() * 100), 1),
            "Середній час на питання, с": round(float(self.answers["time_spent"].mean()), 1),
        }

    def category_stats(self):
        """Успішність за категоріями (повертає числовий DataFrame)."""
        grouped = (self.answers.groupby("category")
                   .agg(answered=("is_correct", "size"), correct=("is_correct", "sum"))
                   .reset_index())
        grouped["percent"] = (grouped["correct"] / grouped["answered"] * 100).round(1)
        return grouped.sort_values("percent").reset_index(drop=True)

    def hardest_questions(self, n=5):
        """Питання з найменшим відсотком правильних відповідей."""
        grouped = (self.answers.groupby("question")
                   .agg(attempts=("is_correct", "size"), correct=("is_correct", "sum"))
                   .reset_index())
        grouped["percent"] = (grouped["correct"] / grouped["attempts"] * 100).round(1)
        return grouped.sort_values(["percent", "attempts"], ascending=[True, False]).head(n)

    #  Крок 3. Таблиці для показу користувачеві
    def history_table(self):
        h = self.history
        table = pd.DataFrame({
            "№": range(1, len(h) + 1),
            "Дата": h["date"].dt.strftime("%d.%m.%Y %H:%M"),
            "Студент": h["student"],
            "Питань": h["total"].astype(int),
            "Правильних": h["correct"].astype(int),
            "Результат, %": h["percent"],
            "Тривалість, с": h["duration_sec"],
            "Склав": h["passed"].map({1: "Так", 0: "Ні"}),
        })
        return table

    def category_table(self):
        c = self.category_stats()
        return pd.DataFrame({
            "Категорія": c["category"],
            "Відповідей": c["answered"].astype(int),
            "Правильних": c["correct"].astype(int),
            "Успішність, %": c["percent"],
        })

    def hardest_table(self, n=5):
        q = self.hardest_questions(n)
        return pd.DataFrame({
            "Питання": q["question"],
            "Спроб": q["attempts"].astype(int),
            "Успішність, %": q["percent"],
        })

    #  Експорт
    def export_history(self, path):
        """Зберігає таблицю історії у CSV, JSON або TXT."""
        path = Path(path)
        table = self.history_table()
        extension = path.suffix.lower()
        try:
            if extension == ".csv":
                table.to_csv(path, index=False, encoding="utf-8-sig")
            elif extension == ".json":
                table.to_json(path, orient="records", force_ascii=False, indent=2)
            elif extension == ".txt":
                path.write_text(table.to_string(index=False), encoding="utf-8")
            else:
                raise StatisticsError("Підтримуються лише формати CSV, JSON і TXT.")
        except OSError as err:
            raise StatisticsError(f"Не вдалося записати файл: {err}") from err
