"""
models.py — класи предметної області: питання, тест, результат.

Тут немає нічого, що стосується вікон чи файлів: тільки логіка тестування.
Завдяки цьому модуль можна повторно використати і перевірити окремо від
графічного інтерфейсу.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime

ALL_CATEGORIES = "Усі"          # службове значення фільтра категорій
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class Question:
    """Одне питання тесту з вибором однієї правильної відповіді.

    Поля зроблені «приватними» (інкапсуляція): змінити їх ззовні не можна,
    читати можна лише через властивості.
    """

    def __init__(self, text, options, correct_index, category="Загальні", explanation=""):
        text = str(text).strip()
        if not text:
            raise ValueError("текст питання порожній")
        if not isinstance(options, (list, tuple)):
            raise ValueError("варіанти відповіді мають бути списком")
        options = [str(o).strip() for o in options]
        if len(options) < 2:
            raise ValueError("потрібно щонайменше два варіанти відповіді")
        if any(not o for o in options):
            raise ValueError("є порожній варіант відповіді")
        if len(set(o.lower() for o in options)) != len(options):
            raise ValueError("варіанти відповіді повторюються")
        if isinstance(correct_index, bool) or not isinstance(correct_index, int):
            raise ValueError("номер правильної відповіді має бути цілим числом")
        if not 0 <= correct_index < len(options):
            raise ValueError("номер правильної відповіді виходить за межі списку")

        self.__text = text
        self.__options = options
        self.__correct_index = correct_index
        self.__category = str(category).strip() or "Загальні"
        self.__explanation = str(explanation).strip()

    #  властивості лише для читання
    @property
    def text(self):
        return self.__text

    @property
    def options(self):
        return list(self.__options)  # копія, щоб не змінили список ззовні

    @property
    def correct_index(self):
        return self.__correct_index

    @property
    def correct_answer(self):
        return self.__options[self.__correct_index]

    @property
    def category(self):
        return self.__category

    @property
    def explanation(self):
        return self.__explanation

    #  методи
    def is_correct(self, index):
        """Перевіряє, чи обраний варіант є правильним."""
        return index == self.__correct_index

    def with_shuffled_options(self, rng=None):
        """Повертає копію питання з перемішаними варіантами відповідей."""
        rng = rng or random
        order = list(range(len(self.__options)))
        rng.shuffle(order)
        new_options = [self.__options[i] for i in order]
        new_correct = order.index(self.__correct_index)
        return Question(self.__text, new_options, new_correct,
                        self.__category, self.__explanation)

    def __repr__(self):
        return f"Question({self.__text[:30]!r}..., category={self.__category!r})"


@dataclass
class AnswerRecord:
    """Запис про відповідь на одне питання."""
    question_text: str
    category: str
    selected_text: str          # None, якщо студент не встиг відповісти
    correct_text: str
    is_correct: bool
    time_spent: float
    explanation: str = ""


@dataclass
class TestResult:
    """Підсумок однієї спроби проходження тесту."""
    student: str
    started_at: datetime
    duration_sec: float
    answers: list = field(default_factory=list)
    pass_percent: int = 60

    @property
    def total(self):
        return len(self.answers)

    @property
    def correct(self):
        return sum(1 for a in self.answers if a.is_correct)

    @property
    def percent(self):
        return round(self.correct / self.total * 100, 1) if self.total else 0.0

    @property
    def passed(self):
        return self.percent >= self.pass_percent

    def summary_row(self):
        """Рядок для файлу історії спроб."""
        return {
            "date": self.started_at.strftime(DATE_FORMAT),
            "student": self.student,
            "total": self.total,
            "correct": self.correct,
            "percent": self.percent,
            "duration_sec": round(self.duration_sec, 1),
            "passed": int(self.passed),
        }

    def answer_rows(self):
        """Рядки для файлу з відповідями на кожне питання."""
        date = self.started_at.strftime(DATE_FORMAT)
        return [
            {
                "date": date,
                "student": self.student,
                "category": a.category,
                "question": a.question_text,
                "selected": a.selected_text if a.selected_text is not None else "",
                "correct_answer": a.correct_text,
                "is_correct": int(a.is_correct),
                "time_spent": round(a.time_spent, 1),
            }
            for a in self.answers
        ]


class Quiz:
    """Один сеанс тестування: добирає питання та веде облік відповідей."""

    def __init__(self, questions, count=10, shuffle_questions=True,
                 shuffle_answers=True, category=None, rng=None):
        rng = rng or random.Random()
        pool = [q for q in questions
                if category in (None, "", ALL_CATEGORIES) or q.category == category]
        if not pool:
            raise ValueError("Немає питань для обраної категорії.")
        if shuffle_questions:
            rng.shuffle(pool)
        pool = pool[:count]
        if shuffle_answers:
            pool = [q.with_shuffled_options(rng) for q in pool]

        self._questions = pool
        self._index = 0
        self._records = []
        self._started = datetime.now()

    @property
    def total(self):
        return len(self._questions)

    @property
    def current_index(self):
        return self._index

    @property
    def is_finished(self):
        return self._index >= len(self._questions)

    @property
    def current_question(self):
        return None if self.is_finished else self._questions[self._index]

    @property
    def correct_so_far(self):
        return sum(1 for r in self._records if r.is_correct)

    def answer(self, selected_index, time_spent):
        """Фіксує відповідь на поточне питання й переходить до наступного.

        selected_index = None означає, що час вийшов і відповіді немає.
        """
        question = self.current_question
        if question is None:
            raise RuntimeError("Тест уже завершено.")
        options = question.options
        if selected_index is not None and not 0 <= selected_index < len(options):
            raise ValueError("Обрано неіснуючий варіант відповіді.")

        record = AnswerRecord(
            question_text=question.text,
            category=question.category,
            selected_text=None if selected_index is None else options[selected_index],
            correct_text=question.correct_answer,
            is_correct=selected_index is not None and question.is_correct(selected_index),
            time_spent=float(time_spent),
            explanation=question.explanation,
        )
        self._records.append(record)
        self._index += 1
        return record

    def build_result(self, student, pass_percent):
        """Формує підсумок після завершення тесту."""
        elapsed = (datetime.now() - self._started).total_seconds()
        return TestResult(student=student, started_at=self._started,
                          duration_sec=elapsed, answers=list(self._records),
                          pass_percent=pass_percent)
