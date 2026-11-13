"""
main.py — точка входу в програму.

Запуск:
    python main.py
    python main.py --questions data/questions_example.csv --count 3 --time 15

Параметри командного рядка тимчасово (лише на цей запуск) змінюють значення
з config.json.
"""

import argparse
import sys

from config import ConfigError, ConfigManager


def parse_args():
    parser = argparse.ArgumentParser(description="Програма для тестування знань (tkinter).")
    parser.add_argument("--config", help="шлях до файлу налаштувань (за замовчуванням config.json)")
    parser.add_argument("--questions", help="файл з питаннями (.json або .csv)")
    parser.add_argument("--count", type=int, help="кількість питань у тесті")
    parser.add_argument("--time", type=int, help="секунд на питання (0 = без ліміту)")
    parser.add_argument("--category", help="категорія питань")
    return parser.parse_args()


def main():
    args = parse_args()
    config = ConfigManager(args.config)
    config.load()

    overrides = {}
    if args.questions:
        overrides["questions_file"] = args.questions
    if args.count is not None:
        overrides["questions_count"] = args.count
    if args.time is not None:
        overrides["time_limit_seconds"] = args.time
    if args.category:
        overrides["category"] = args.category
    try:
        config.update(overrides)
    except ConfigError as err:
        print("Помилка параметрів командного рядка:\n" + str(err))
        sys.exit(2)

    try:
        import tkinter as tk
        from gui import QuizApp
    except ImportError:
        print("Не вдалося імпортувати tkinter.")
        sys.exit(1)

    try:
        app = QuizApp(config)
    except tk.TclError as err:
        print(f"Не вдалося відкрити графічне вікно: {err}")
        sys.exit(1)
    app.mainloop()


if __name__ == "__main__":
    main()
