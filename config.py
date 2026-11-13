"""
config.py — модуль керування налаштуваннями програми.

Усі параметри тестування (кількість питань, ліміт часу, перемішування,
прохідний бал, файл із питаннями тощо) зберігаються у файлі config.json.
Завдяки цьому поведінку програми можна змінювати без редагування коду:
через меню «Налаштування» або через параметри командного рядка.
"""

import json
from pathlib import Path

# Папка, у якій лежить програма. Відносні шляхи рахуються від неї.
BASE_DIR = Path(__file__).resolve().parent

# Значення за замовчуванням (використовуються, якщо файлу немає або він пошкоджений)
DEFAULT_CONFIG = {
    "questions_file": "data/questions.json",
    "category": "Усі",
    "questions_count": 10,
    "time_limit_seconds": 30,   # 0 = без обмеження часу
    "shuffle_questions": True,
    "shuffle_answers": True,
    "show_feedback": True,      # показувати правильну відповідь після кожного питання
    "pass_percent": 60,
    "results_dir": "results",
    "student_name": "",
}

# Допустимі межі для цілих параметрів
INT_RULES = {
    "questions_count": (1, 100),
    "time_limit_seconds": (0, 600),
    "pass_percent": (1, 100),
}
BOOL_KEYS = ("shuffle_questions", "shuffle_answers", "show_feedback")
NON_EMPTY_STR_KEYS = ("questions_file", "results_dir", "category")

# Назви параметрів для повідомлень про помилки
FIELD_LABELS = {
    "questions_file": "Файл з питаннями",
    "category": "Категорія",
    "questions_count": "Кількість питань",
    "time_limit_seconds": "Час на питання (с)",
    "shuffle_questions": "Перемішувати питання",
    "shuffle_answers": "Перемішувати відповіді",
    "show_feedback": "Показувати правильну відповідь",
    "pass_percent": "Прохідний бал (%)",
    "results_dir": "Папка для результатів",
    "student_name": "Ім'я студента",
}


class ConfigError(Exception):
    """Помилка в налаштуваннях програми."""


class ConfigManager:
    """Завантажує, перевіряє та зберігає налаштування."""

    def __init__(self, path=None):
        self.path = Path(path) if path else BASE_DIR / "config.json"
        self.values = dict(DEFAULT_CONFIG)
        self.messages = []  # попередження, які виникли під час завантаження

    # ---------- доступ до значень ----------
    def __getitem__(self, key):
        return self.values[key]

    def resolve_path(self, name):
        """Перетворює шлях з налаштувань в абсолютний (відносно папки програми)."""
        p = Path(name)
        return p if p.is_absolute() else BASE_DIR / p

    # ---------- перевірка ----------
    @staticmethod
    def validate_value(key, value):
        """Повертає «очищене» значення або кидає ValueError з поясненням."""
        if key in INT_RULES:
            if isinstance(value, bool):
                raise ValueError("має бути цілим числом")
            try:
                number = int(value)
            except (TypeError, ValueError):
                raise ValueError("має бути цілим числом") from None
            low, high = INT_RULES[key]
            if not low <= number <= high:
                raise ValueError(f"має бути від {low} до {high}")
            return number
        if key in BOOL_KEYS:
            if not isinstance(value, bool):
                raise ValueError("має бути true або false")
            return value
        if not isinstance(value, str):
            raise ValueError("має бути текстом")
        value = value.strip()
        if key in NON_EMPTY_STR_KEYS and not value:
            raise ValueError("не може бути порожнім")
        return value

    #  завантаження / збереження
    def load(self):
        """Читає config.json. Некоректні значення замінює на типові."""
        if not self.path.exists():
            self.messages.append(
                f"Файл налаштувань «{self.path.name}» не знайдено. "
                "Використано типові значення."
            )
            try:
                self.save()
            except ConfigError:
                pass
            return self.values

        try:
            with open(self.path, encoding="utf-8-sig") as f:
                data = json.load(f)
        except json.JSONDecodeError as err:
            self.messages.append(
                f"Файл налаштувань пошкоджено (рядок {err.lineno}). "
                "Використано типові значення."
            )
            return self.values
        except OSError as err:
            self.messages.append(f"Не вдалося прочитати налаштування: {err}")
            return self.values

        if not isinstance(data, dict):
            self.messages.append("Файл налаштувань має неправильну структуру.")
            return self.values

        for key, value in data.items():
            if key not in DEFAULT_CONFIG:
                continue  # невідомі ключі ігноруємо
            try:
                self.values[key] = self.validate_value(key, value)
            except ValueError as err:
                self.messages.append(
                    f"Параметр «{FIELD_LABELS[key]}» {err}. "
                    "Використано типове значення."
                )
        return self.values

    def update(self, new_values):
        """Перевіряє всі нові значення і лише тоді застосовує їх (все або нічого)."""
        clean, errors = {}, []
        for key, value in new_values.items():
            if key not in DEFAULT_CONFIG:
                errors.append(f"Невідомий параметр: {key}")
                continue
            try:
                clean[key] = self.validate_value(key, value)
            except ValueError as err:
                errors.append(f"«{FIELD_LABELS[key]}» {err}.")
        if errors:
            raise ConfigError("\n".join(errors))
        self.values.update(clean)

    def save(self):
        """Записує поточні налаштування у config.json."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.values, f, ensure_ascii=False, indent=4)
        except OSError as err:
            raise ConfigError(f"Не вдалося зберегти налаштування: {err}") from err
