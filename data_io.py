"""
data_io.py — імпорт питань і збереження результатів.

QuestionLoader  — читає питання з файлів JSON та CSV, перевіряє й «чистить» дані.
ResultsStorage  — записує результати у CSV, JSON та TXT.
"""

import csv
import json
from pathlib import Path

from models import Question, TestResult

HISTORY_COLUMNS = ["date", "student", "total", "correct", "percent",
                   "duration_sec", "passed"]
ANSWER_COLUMNS = ["date", "student", "category", "question", "selected",
                  "correct_answer", "is_correct", "time_spent"]


class DataFormatError(Exception):
    """Файл з даними має некоректний формат."""


class StorageError(Exception):
    """Не вдалося записати результати."""


class QuestionLoader:
    """Завантажує питання з JSON або CSV.

    Формат JSON: список об'єктів
        {"question": "...", "options": ["...", "..."], "correct": 0,
         "category": "...", "explanation": "..."}      (correct — з нуля)

    Формат CSV: заголовок
        question,option1,option2,option3,option4,correct,category,explanation
        (correct — номер правильного варіанта, починаючи з 1)
    """

    def __init__(self):
        self.warnings = []   # пропущені або виправлені записи

    def load(self, path):
        path = Path(path)
        self.warnings = []
        if not path.exists():
            raise FileNotFoundError(f"Файл з питаннями не знайдено: {path}")
        extension = path.suffix.lower()
        if extension == ".json":
            raw_items = self._read_json(path)
        elif extension == ".csv":
            raw_items = self._read_csv(path)
        else:
            raise DataFormatError(
                f"Формат «{extension or 'без розширення'}» не підтримується. "
                "Використовуйте файли .json або .csv."
            )
        questions = self._build_questions(raw_items)
        if not questions:
            raise DataFormatError("У файлі не знайдено жодного коректного питання.")
        return questions

    #  читання JSON
    def _read_json(self, path):
        try:
            with open(path, encoding="utf-8-sig") as f:
                data = json.load(f)
        except json.JSONDecodeError as err:
            raise DataFormatError(
                f"Файл JSON пошкоджено: помилка в рядку {err.lineno}, "
                f"позиція {err.colno}."
            ) from err
        except UnicodeDecodeError as err:
            raise DataFormatError("Файл має неправильне кодування (потрібно UTF-8).") from err

        if isinstance(data, dict) and "questions" in data:
            data = data["questions"]
        if not isinstance(data, list):
            raise DataFormatError("У JSON-файлі очікується список питань.")

        items = []
        for item in data:
            if not isinstance(item, dict):
                items.append(None)
                continue
            items.append({
                "text": item.get("question", item.get("text", "")),
                "options": item.get("options"),
                "correct": item.get("correct"),
                "category": item.get("category", "Загальні"),
                "explanation": item.get("explanation", ""),
            })
        return items

    #  читання CSV
    def _read_csv(self, path):
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                # роздільник визначаємо за заголовком: Excel в українській
                # локалізації зберігає CSV з крапкою з комою, а не з комою
                header = f.readline()
                f.seek(0)
                delimiter = max(",;\t", key=header.count)
                reader = csv.DictReader(f, delimiter=delimiter)
                fields = [name.strip().lower() for name in (reader.fieldnames or [])]
                if "question" not in fields or "correct" not in fields:
                    raise DataFormatError(
                        "У CSV-файлі мають бути стовпці «question» та «correct»."
                    )
                items = []
                for row in reader:
                    # зайві комірки (ключ None) ігноруємо
                    row = {k.strip().lower(): (v or "").strip()
                           for k, v in row.items() if k is not None}
                    option_keys = sorted(
                        (k for k in row if k.startswith("option")),
                        key=lambda k: int(k[6:]) if k[6:].isdigit() else 0,
                    )
                    options = [row[k] for k in option_keys if row[k]]
                    try:
                        correct = int(row["correct"]) - 1   # у CSV нумерація з 1
                    except ValueError:
                        correct = None
                    items.append({
                        "text": row.get("question", ""),
                        "options": options,
                        "correct": correct,
                        "category": row.get("category") or "Загальні",
                        "explanation": row.get("explanation", ""),
                    })
                return items
        except UnicodeDecodeError as err:
            raise DataFormatError("Файл має неправильне кодування (потрібно UTF-8).") from err
        except csv.Error as err:
            raise DataFormatError(f"Помилка читання CSV: {err}") from err

    # ---------- очищення та перевірка ----------
    def _build_questions(self, raw_items):
        questions, seen = [], set()
        for number, item in enumerate(raw_items, start=1):
            if item is None:
                self.warnings.append(f"Запис №{number} пропущено: це не об'єкт.")
                continue
            try:
                question = Question(item["text"], item["options"], item["correct"],
                                    item["category"], item["explanation"])
            except (ValueError, TypeError) as err:
                self.warnings.append(f"Питання №{number} пропущено: {err}.")
                continue
            key = question.text.lower()
            if key in seen:
                self.warnings.append(f"Питання №{number} пропущено: дублікат.")
                continue
            seen.add(key)
            questions.append(question)
        return questions


class ResultsStorage:
    """Зберігає результати тестування у зовнішніх файлах."""

    def __init__(self, results_dir):
        self.results_dir = Path(results_dir)

    @property
    def history_path(self):
        return self.results_dir / "history.csv"

    @property
    def answers_path(self):
        return self.results_dir / "answers.csv"

    def save(self, result: TestResult):
        """Дописує спробу до історії та створює окремі файли TXT і JSON."""
        try:
            self.results_dir.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise StorageError(f"Не вдалося створити папку результатів: {err}") from err

        stamp = result.started_at.strftime("%Y%m%d_%H%M%S")
        txt_path = self.results_dir / f"attempt_{stamp}.txt"
        json_path = self.results_dir / f"attempt_{stamp}.json"

        self._append_csv(self.history_path, HISTORY_COLUMNS, [result.summary_row()])
        self._append_csv(self.answers_path, ANSWER_COLUMNS, result.answer_rows())
        self.export_result(result, txt_path)
        self.export_result(result, json_path)
        return {"history": self.history_path, "txt": txt_path, "json": json_path}

    def _append_csv(self, path, columns, rows):
        is_new = not path.exists()
        # BOM потрібен лише на початку файлу, щоб Excel правильно прочитав кирилицю
        encoding = "utf-8-sig" if is_new else "utf-8"
        try:
            with open(path, "a", encoding=encoding, newline="") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                if is_new:
                    writer.writeheader()
                writer.writerows(rows)
        except PermissionError as err:
            raise StorageError(
                f"Немає доступу до файлу «{path.name}». "
                "Якщо він відкритий в іншій програмі (наприклад, Excel), закрийте його."
            ) from err
        except OSError as err:
            raise StorageError(f"Помилка запису файлу «{path.name}»: {err}") from err

    def export_result(self, result: TestResult, path):
        """Зберігає одну спробу у файл CSV, JSON або TXT (залежно від розширення)."""
        path = Path(path)
        extension = path.suffix.lower()
        try:
            if extension == ".csv":
                with open(path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=ANSWER_COLUMNS)
                    writer.writeheader()
                    writer.writerows(result.answer_rows())
            elif extension == ".json":
                payload = {"summary": result.summary_row(),
                           "answers": result.answer_rows()}
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            elif extension == ".txt":
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._format_txt(result))
            else:
                raise StorageError("Підтримуються лише формати CSV, JSON і TXT.")
        except OSError as err:
            raise StorageError(f"Не вдалося записати файл «{path.name}»: {err}") from err

    @staticmethod
    def _format_txt(result: TestResult):
        lines = [
            "РЕЗУЛЬТАТ ТЕСТУВАННЯ",
            "=" * 60,
            f"Студент: {result.student}",
            f"Дата: {result.started_at:%d.%m.%Y %H:%M}",
            f"Правильних відповідей: {result.correct} з {result.total} ({result.percent}%)",
            f"Тривалість: {result.duration_sec:.0f} с",
            f"Підсумок: {'тест складено' if result.passed else 'тест не складено'} "
            f"(прохідний бал {result.pass_percent}%)",
            "=" * 60,
            "",
        ]
        for i, a in enumerate(result.answers, start=1):
            mark = "правильно" if a.is_correct else "неправильно"
            chosen = a.selected_text if a.selected_text is not None else "— (час вийшов)"
            lines.append(f"{i}. [{a.category}] {a.question_text}")
            lines.append(f"   Ваша відповідь: {chosen} — {mark}")
            if not a.is_correct:
                lines.append(f"   Правильна відповідь: {a.correct_text}")
            lines.append("")
        return "\n".join(lines)
