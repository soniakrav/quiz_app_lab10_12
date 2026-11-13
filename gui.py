"""
gui.py — графічний інтерфейс на tkinter.

QuizApp          — головне вікно, керує переходами між екранами.
MenuFrame        — головне меню.
TestFrame        — екран проходження тесту (питання, таймер, прогрес).
ResultFrame      — підсумок тесту.
StatsFrame       — статистика, графіки, звіт.
SettingsWindow   — вікно налаштувань.
ChartsWindow     — перегляд побудованих графіків.
"""

import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from config import ConfigError, ConfigManager
from data_io import DataFormatError, QuestionLoader, ResultsStorage, StorageError
from models import ALL_CATEGORIES, Quiz
from report import ReportError, ReportGenerator
from stats import StatisticsAnalyzer, StatisticsError
from visualization import ChartBuilder, VisualizationError

OK_COLOR, BAD_COLOR = "#2e7d32", "#c62828"


#  допоміжні функції
def make_table(parent, columns, widths, height=10):
    """Створює таблицю (Treeview) з вертикальною прокруткою."""
    frame = ttk.Frame(parent)
    ids = [f"c{i}" for i in range(len(columns))]
    tree = ttk.Treeview(frame, columns=ids, show="headings", height=height)
    for col_id, name, width in zip(ids, columns, widths):
        tree.heading(col_id, text=name)
        tree.column(col_id, width=width, anchor="w")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return frame, tree


def fill_table(tree, rows):
    """Очищає таблицю і заповнює її новими рядками."""
    for item in tree.get_children():
        tree.delete(item)
    for row in rows:
        tree.insert("", "end", values=[str(v) for v in row])


#  головне вікно
class QuizApp(tk.Tk):
    def __init__(self, config: ConfigManager):
        super().__init__()
        self.title("Система тестування знань")
        self.geometry("920x680")
        self.minsize(800, 600)

        self.config_mgr = config
        self.loader = QuestionLoader()
        self.questions = []
        self.student_name = tk.StringVar(value=config["student_name"])

        self._setup_style()
        self.container = ttk.Frame(self, padding=15)
        self.container.pack(fill="both", expand=True)
        self.current_frame = None

        self.reload_questions()
        self.show_menu()
        if config.messages:   # попередження, що виникли під час читання налаштувань
            self.after(300, lambda: messagebox.showwarning(
                "Налаштування", "\n".join(config.messages)))

    #  оформлення
    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        tkfont.nametofont("TkDefaultFont").configure(size=11)
        tkfont.nametofont("TkTextFont").configure(size=11)
        style.configure("Title.TLabel", font=("Arial", 22, "bold"))
        style.configure("Sub.TLabel", font=("Arial", 11), foreground="#555555")
        style.configure("Big.TButton", font=("Arial", 12), padding=8)
        style.configure("Treeview", rowheight=24)

    #  перемикання екранів
    def show_frame(self, frame_class, **kwargs):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame_class(self.container, self, **kwargs)
        self.current_frame.pack(fill="both", expand=True)

    def show_menu(self):
        self.show_frame(MenuFrame)

    #  питання
    def reload_questions(self):
        """Завантажує питання з файлу, вказаного в налаштуваннях."""
        path = self.config_mgr.resolve_path(self.config_mgr["questions_file"])
        try:
            self.questions = self.loader.load(path)
        except FileNotFoundError as err:
            self.questions = []
            messagebox.showerror("Файл не знайдено", str(err))
        except DataFormatError as err:
            self.questions = []
            messagebox.showerror("Некоректний формат даних", str(err))
        except OSError as err:
            self.questions = []
            messagebox.showerror("Помилка читання файлу", str(err))
        else:
            if self.loader.warnings:
                shown = self.loader.warnings[:8]
                extra = len(self.loader.warnings) - len(shown)
                text = "\n".join(shown) + (f"\n...та ще {extra}" if extra > 0 else "")
                messagebox.showwarning("Деякі питання пропущено", text)

    def categories(self):
        return sorted({q.category for q in self.questions})

    def import_questions(self):
        """Дозволяє обрати інший файл з питаннями (JSON або CSV)."""
        path = filedialog.askopenfilename(
            title="Оберіть файл з питаннями",
            filetypes=[("Питання (JSON, CSV)", "*.json *.csv"), ("Усі файли", "*.*")])
        if not path:
            return
        try:
            self.config_mgr.update({"questions_file": path, "category": ALL_CATEGORIES})
            self.config_mgr.save()
        except ConfigError as err:
            messagebox.showerror("Помилка налаштувань", str(err))
            return
        self.reload_questions()
        self.show_menu()

    #  запуск і завершення тесту
    def storage(self):
        return ResultsStorage(self.config_mgr.resolve_path(self.config_mgr["results_dir"]))

    def start_test(self):
        name = self.student_name.get().strip()
        if not name:
            messagebox.showwarning("Увага", "Введіть своє ім'я перед початком тесту.")
            return
        if len(name) > 40:
            messagebox.showwarning("Увага", "Ім'я не може бути довшим за 40 символів.")
            return
        if not self.questions:
            messagebox.showerror("Немає питань",
                                 "Спочатку завантажте файл з питаннями (JSON або CSV).")
            return
        cfg = self.config_mgr
        try:
            quiz = Quiz(self.questions, count=cfg["questions_count"],
                        shuffle_questions=cfg["shuffle_questions"],
                        shuffle_answers=cfg["shuffle_answers"],
                        category=cfg["category"])
        except ValueError as err:
            messagebox.showerror("Не вдалося почати тест", str(err))
            return
        try:   # запам'ятовуємо ім'я для наступного запуску
            cfg.update({"student_name": name})
            cfg.save()
        except ConfigError:
            pass
        self.show_frame(TestFrame, quiz=quiz, student=name)

    def finish_test(self, result):
        saved = None
        try:
            saved = self.storage().save(result)
        except StorageError as err:
            messagebox.showerror("Помилка збереження", str(err))
        self.show_frame(ResultFrame, result=result, saved=saved)

    def export_result(self, result):
        path = filedialog.asksaveasfilename(
            title="Зберегти результат", defaultextension=".txt",
            filetypes=[("Текст", "*.txt"), ("CSV", "*.csv"), ("JSON", "*.json")])
        if not path:
            return
        try:
            self.storage().export_result(result, path)
            messagebox.showinfo("Готово", f"Результат збережено:\n{path}")
        except StorageError as err:
            messagebox.showerror("Помилка збереження", str(err))

    #  налаштування
    def open_settings(self):
        SettingsWindow(self)

    #  статистика
    def open_stats(self):
        store = self.storage()
        analyzer = StatisticsAnalyzer(store.history_path, store.answers_path)
        try:
            analyzer.load()
        except StatisticsError as err:
            messagebox.showinfo("Статистика", str(err))
            return
        self.show_frame(StatsFrame, analyzer=analyzer)

    def build_charts(self, analyzer):
        out_dir = self.storage().results_dir / "charts"
        builder = ChartBuilder(out_dir, self.config_mgr["pass_percent"])
        return builder.build_all(analyzer.history, analyzer.answers,
                                 analyzer.category_stats())

    def show_charts(self, analyzer):
        try:
            charts, pdf_path = self.build_charts(analyzer)
        except VisualizationError as err:
            messagebox.showerror("Помилка побудови графіків", str(err))
            return
        ChartsWindow(self, charts, pdf_path)

    def make_report(self, analyzer):
        try:
            charts, _ = self.build_charts(analyzer)
            path = ReportGenerator(self.storage().results_dir).generate(
                analyzer.summary(), analyzer.history_table(),
                analyzer.category_table(), analyzer.hardest_table(), charts)
        except (VisualizationError, ReportError) as err:
            messagebox.showerror("Помилка створення звіту", str(err))
            return
        if messagebox.askyesno("Звіт створено",
                               f"Звіт збережено:\n{path}\n\nВідкрити його в браузері?"):
            webbrowser.open(path.as_uri())

    def export_history(self, analyzer):
        path = filedialog.asksaveasfilename(
            title="Експорт історії", defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("JSON", "*.json"), ("Текст", "*.txt")])
        if not path:
            return
        try:
            analyzer.export_history(path)
            messagebox.showinfo("Готово", f"Історію збережено:\n{path}")
        except StatisticsError as err:
            messagebox.showerror("Помилка експорту", str(err))


#  головне меню
class MenuFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        cfg = app.config_mgr
        ttk.Label(self, text="Система тестування знань", style="Title.TLabel").pack(pady=(30, 5))
        ttk.Label(self, text="Програма на Python (tkinter, pandas, matplotlib)",
                  style="Sub.TLabel").pack()

        limit = cfg["time_limit_seconds"]
        info = (f"Питань у файлі: {len(app.questions)}   |   Питань у тесті: "
                f"{cfg['questions_count']}   |   Категорія: {cfg['category']}   |   "
                f"Час на питання: {'без ліміту' if limit == 0 else str(limit) + ' с'}")
        ttk.Label(self, text=info, style="Sub.TLabel").pack(pady=15)

        row = ttk.Frame(self)
        row.pack(pady=10)
        ttk.Label(row, text="Ваше ім'я:").pack(side="left", padx=5)
        entry = ttk.Entry(row, textvariable=app.student_name, width=30)
        entry.pack(side="left")
        entry.focus_set()
        entry.bind("<Return>", lambda e: app.start_test())

        buttons = [
            ("Почати тест", app.start_test),
            ("Завантажити питання з файлу", app.import_questions),
            ("Налаштування", app.open_settings),
            ("Статистика та графіки", app.open_stats),
            ("Вихід", app.destroy),
        ]
        for text, command in buttons:
            ttk.Button(self, text=text, command=command, style="Big.TButton",
                       width=34).pack(pady=5)


#  екран тесту
class TestFrame(ttk.Frame):
    def __init__(self, master, app, quiz, student):
        super().__init__(master)
        self.app, self.quiz, self.student = app, quiz, student
        cfg = app.config_mgr
        self.limit = cfg["time_limit_seconds"]
        self.show_feedback = cfg["show_feedback"]
        self.pass_percent = cfg["pass_percent"]

        self.var = tk.IntVar(value=-1)       # номер обраного варіанта
        self.state = "answering"             # answering -> feedback
        self.timer_id = None
        self.remaining = 0
        self.question_started = time.monotonic()
        self.option_widgets = []

        # верхня панель: хід тесту
        top = ttk.Frame(self)
        top.pack(fill="x")
        self.header = ttk.Label(top, font=("Arial", 13, "bold"))
        self.header.pack(side="left")
        self.timer_label = ttk.Label(top, font=("Arial", 13, "bold"))
        self.timer_label.pack(side="right")

        self.progress = ttk.Progressbar(self, maximum=quiz.total)
        self.progress.pack(fill="x", pady=8)
        self.score_label = ttk.Label(self, style="Sub.TLabel")
        self.score_label.pack(anchor="w")

        self.category_label = ttk.Label(self, style="Sub.TLabel")
        self.category_label.pack(anchor="w", pady=(15, 0))
        self.question_label = ttk.Label(self, font=("Arial", 15), wraplength=820,
                                        justify="left")
        self.question_label.pack(anchor="w", pady=10)

        self.options_frame = ttk.Frame(self)
        self.options_frame.pack(fill="x", pady=5)

        self.feedback = ttk.Label(self, wraplength=820, justify="left",
                                  font=("Arial", 12, "bold"))
        self.feedback.pack(anchor="w", pady=10)

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", pady=10)
        ttk.Button(bottom, text="Перервати тест", command=self._abort).pack(side="left")
        self.submit_btn = ttk.Button(bottom, text="Відповісти", style="Big.TButton",
                                     command=self._on_submit)
        self.submit_btn.pack(side="right")

        self._show_question()

    #  показ питання
    def _show_question(self):
        q = self.quiz.current_question
        self.state = "answering"
        self.var.set(-1)
        number = self.quiz.current_index + 1
        self.header.config(text=f"Питання {number} з {self.quiz.total}")
        self.progress["value"] = self.quiz.current_index
        self.score_label.config(
            text=f"Правильних відповідей поки що: {self.quiz.correct_so_far}")
        self.category_label.config(text=f"Категорія: {q.category}")
        self.question_label.config(text=q.text)
        self.feedback.config(text="")

        for widget in self.options_frame.winfo_children():
            widget.destroy()
        self.option_widgets = []
        for i, option in enumerate(q.options):
            rb = tk.Radiobutton(self.options_frame, text=f"{chr(65 + i)}.  {option}",
                                variable=self.var, value=i, anchor="w", justify="left",
                                wraplength=800, font=("Arial", 13), pady=4)
            rb.pack(fill="x", anchor="w")
            self.option_widgets.append(rb)

        self.submit_btn.config(text="Відповісти")
        self.question_started = time.monotonic()
        self.remaining = self.limit
        self._cancel_timer()
        self._tick()

    #  таймер
    def _tick(self):
        if self.limit <= 0:
            self.timer_label.config(text="Час: без обмеження", foreground="#555555")
            return
        color = BAD_COLOR if self.remaining <= 5 else "#222222"
        self.timer_label.config(text=f"Залишилось: {self.remaining} с", foreground=color)
        if self.remaining <= 0:
            self._on_timeout()
            return
        self.remaining -= 1
        self.timer_id = self.after(1000, self._tick)

    def _cancel_timer(self):
        if self.timer_id is not None:
            self.after_cancel(self.timer_id)
            self.timer_id = None

    #  відповідь
    def _on_submit(self):
        if self.state == "feedback":
            self._next()
            return
        selected = self.var.get()
        if selected < 0:
            messagebox.showwarning("Увага", "Спочатку оберіть варіант відповіді.")
            return
        self._cancel_timer()
        spent = time.monotonic() - self.question_started
        if self.limit > 0:
            spent = min(spent, self.limit)
        record = self.quiz.answer(selected, round(spent, 1))
        self._after_answer(record, timed_out=False)

    def _on_timeout(self):
        self._cancel_timer()
        record = self.quiz.answer(None, float(self.limit))
        self._after_answer(record, timed_out=True)

    def _after_answer(self, record, timed_out):
        for widget in self.option_widgets:
            widget.config(state="disabled")
        self.score_label.config(
            text=f"Правильних відповідей поки що: {self.quiz.correct_so_far}")
        self.progress["value"] = self.quiz.current_index

        if not self.show_feedback:
            self._next()
            return
        if timed_out:
            text, color = f"Час вийшов! Правильна відповідь: {record.correct_text}", BAD_COLOR
        elif record.is_correct:
            text, color = "Правильно!", OK_COLOR
        else:
            text, color = f"Неправильно. Правильна відповідь: {record.correct_text}", BAD_COLOR
        if record.explanation:
            text += f"\n{record.explanation}"
        self.feedback.config(text=text, foreground=color)
        self.state = "feedback"
        self.submit_btn.config(
            text="Завершити тест" if self.quiz.is_finished else "Далі")

    def _next(self):
        if self.quiz.is_finished:
            result = self.quiz.build_result(self.student, self.pass_percent)
            self.app.finish_test(result)
        else:
            self._show_question()

    def _abort(self):
        if messagebox.askyesno("Перервати тест",
                               "Результат цієї спроби не буде збережено. Вийти в меню?"):
            self._cancel_timer()
            self.app.show_menu()

    def destroy(self):
        self._cancel_timer()   # щоб таймер не спрацював після закриття екрана
        super().destroy()


# підсумок тесту
class ResultFrame(ttk.Frame):
    def __init__(self, master, app, result, saved):
        super().__init__(master)
        self.app, self.result = app, result

        ttk.Label(self, text="Тест завершено", style="Title.TLabel").pack(pady=(10, 5))
        verdict = "Тест складено" if result.passed else "Тест не складено"
        color = OK_COLOR if result.passed else BAD_COLOR
        ttk.Label(self, text=verdict, font=("Arial", 16, "bold"),
                  foreground=color).pack()
        ttk.Label(self, text=(f"Правильних відповідей: {result.correct} з {result.total} "
                              f"({result.percent}%)   |   Прохідний бал: "
                              f"{result.pass_percent}%   |   Час: "
                              f"{result.duration_sec:.0f} с"),
                  style="Sub.TLabel").pack(pady=8)
        if saved:
            ttk.Label(self, text=f"Результат збережено у папку: {saved['history'].parent}",
                      style="Sub.TLabel").pack()

        frame, tree = make_table(
            self, ["№", "Категорія", "Питання", "Ваша відповідь", "Правильна відповідь", "Оцінка"],
            [35, 130, 280, 150, 150, 90], height=11)
        frame.pack(fill="both", expand=True, pady=10)
        rows = []
        for i, a in enumerate(result.answers, start=1):
            chosen = a.selected_text if a.selected_text is not None else "— (час вийшов)"
            rows.append([i, a.category, a.question_text, chosen, a.correct_text,
                         "правильно" if a.is_correct else "неправильно"])
        fill_table(tree, rows)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="У меню", command=app.show_menu).pack(side="left")
        ttk.Button(buttons, text="Статистика та графіки",
                   command=app.open_stats).pack(side="left", padx=8)
        ttk.Button(buttons, text="Зберегти результат як...",
                   command=lambda: app.export_result(result)).pack(side="right")


#  статистика
class StatsFrame(ttk.Frame):
    def __init__(self, master, app, analyzer):
        super().__init__(master)
        self.app, self.analyzer = app, analyzer
        ttk.Label(self, text="Статистика результатів", style="Title.TLabel").pack(pady=(0, 10))

        summary = ttk.Frame(self)
        summary.pack(fill="x")
        for i, (name, value) in enumerate(analyzer.summary().items()):
            ttk.Label(summary, text=f"{name}:").grid(row=i // 2, column=(i % 2) * 2,
                                                      sticky="w", padx=(0, 6), pady=2)
            ttk.Label(summary, text=str(value), font=("Arial", 11, "bold")).grid(
                row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 40), pady=2)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, pady=10)
        self._add_tab(notebook, "Історія спроб", analyzer.history_table(),
                      [40, 130, 130, 70, 90, 100, 110, 60])
        self._add_tab(notebook, "За категоріями", analyzer.category_table(),
                      [330, 110, 110, 130])
        self._add_tab(notebook, "Найскладніші питання", analyzer.hardest_table(),
                      [520, 80, 130])

        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Назад", command=app.show_menu).pack(side="left")
        ttk.Button(buttons, text="Графіки", command=lambda: app.show_charts(analyzer)
                   ).pack(side="left", padx=8)
        ttk.Button(buttons, text="Створити HTML-звіт",
                   command=lambda: app.make_report(analyzer)).pack(side="left")
        ttk.Button(buttons, text="Експорт історії...",
                   command=lambda: app.export_history(analyzer)).pack(side="right")

    @staticmethod
    def _add_tab(notebook, title, table, widths):
        tab = ttk.Frame(notebook, padding=5)
        notebook.add(tab, text=title)
        frame, tree = make_table(tab, list(table.columns), widths, height=10)
        frame.pack(fill="both", expand=True)
        fill_table(tree, table.values.tolist())


#  налаштування
class SettingsWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Налаштування")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        cfg = app.config_mgr

        self.vars = {
            "questions_file": tk.StringVar(value=cfg["questions_file"]),
            "category": tk.StringVar(value=cfg["category"]),
            "questions_count": tk.StringVar(value=str(cfg["questions_count"])),
            "time_limit_seconds": tk.StringVar(value=str(cfg["time_limit_seconds"])),
            "pass_percent": tk.StringVar(value=str(cfg["pass_percent"])),
            "results_dir": tk.StringVar(value=cfg["results_dir"]),
            "shuffle_questions": tk.BooleanVar(value=cfg["shuffle_questions"]),
            "shuffle_answers": tk.BooleanVar(value=cfg["shuffle_answers"]),
            "show_feedback": tk.BooleanVar(value=cfg["show_feedback"]),
        }

        body = ttk.Frame(self, padding=15)
        body.pack(fill="both", expand=True)

        def label(row, key):
            from config import FIELD_LABELS
            ttk.Label(body, text=FIELD_LABELS[key] + ":").grid(row=row, column=0,
                                                              sticky="w", pady=5)

        label(0, "questions_file")
        ttk.Entry(body, textvariable=self.vars["questions_file"], width=38).grid(
            row=0, column=1, pady=5, padx=5)
        ttk.Button(body, text="Огляд...", command=self._browse).grid(row=0, column=2)

        label(1, "category")
        ttk.Combobox(body, textvariable=self.vars["category"], state="readonly",
                     values=[ALL_CATEGORIES] + app.categories(), width=35).grid(
            row=1, column=1, pady=5, padx=5, sticky="w")

        for row, key in enumerate(["questions_count", "time_limit_seconds",
                                   "pass_percent"], start=2):
            label(row, key)
            ttk.Entry(body, textvariable=self.vars[key], width=10).grid(
                row=row, column=1, sticky="w", pady=5, padx=5)
        ttk.Label(body, text="(0 = без обмеження часу)", style="Sub.TLabel").grid(
            row=3, column=1, sticky="e")

        label(5, "results_dir")
        ttk.Entry(body, textvariable=self.vars["results_dir"], width=38).grid(
            row=5, column=1, pady=5, padx=5)

        checks = [("shuffle_questions", "Перемішувати питання"),
                  ("shuffle_answers", "Перемішувати варіанти відповідей"),
                  ("show_feedback", "Показувати правильну відповідь після питання")]
        for row, (key, text) in enumerate(checks, start=6):
            ttk.Checkbutton(body, text=text, variable=self.vars[key]).grid(
                row=row, column=0, columnspan=3, sticky="w", pady=2)

        buttons = ttk.Frame(body)
        buttons.grid(row=9, column=0, columnspan=3, pady=(15, 0), sticky="e")
        ttk.Button(buttons, text="Скасувати", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Зберегти", command=self._save).pack(side="right", padx=8)

    def _browse(self):
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("Питання (JSON, CSV)", "*.json *.csv"),
                                    ("Усі файли", "*.*")])
        if path:
            self.vars["questions_file"].set(path)

    def _save(self):
        values = {key: var.get() for key, var in self.vars.items()}
        try:
            # цілі числа перевіряє ConfigManager (текст -> int, межі значень)
            self.app.config_mgr.update(values)
            self.app.config_mgr.save()
        except ConfigError as err:
            messagebox.showerror("Некоректні значення", str(err), parent=self)
            return
        self.app.reload_questions()
        self.destroy()
        self.app.show_menu()


#  перегляд графіків
class ChartsWindow(tk.Toplevel):
    def __init__(self, app, charts, pdf_path):
        super().__init__(app)
        self.title("Графіки")
        self.images = []   # посилання на зображення, інакше tkinter їх «забуде»
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        for chart in charts:
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=chart.title)
            image = tk.PhotoImage(file=str(chart.path))
            self.images.append(image)
            ttk.Label(tab, image=image).pack()
        folder = charts[0].path.parent if charts else ""
        ttk.Label(self, style="Sub.TLabel",
                  text=f"Графіки збережено у файли PNG та PDF: {folder}").pack(pady=(0, 8))
