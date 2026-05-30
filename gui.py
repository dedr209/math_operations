"""
Простий GUI для SimplexSolver на tkinter.
Надає форму для введення матриці A (4 ресурси x 5 технологій), векторів b (4) та c (5).
Виводить покроково симплекс-таблиці в текстове поле з прокруткою.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from fractions import Fraction
from copy import deepcopy
from simplex_solver import SimplexSolver


class SimplexGUI:
    def __init__(self, root):
        self.root = root
        root.title("Simplex Solver GUI")

        # Розміри: 5 технологій (змінних), 4 ресурси (обмеження)
        self.n = 5
        self.m = 4

        self.entries_A = [[None for _ in range(self.n)] for _ in range(self.m)]
        self.entries_b = [None for _ in range(self.m)]
        self.sign_vars = [None for _ in range(self.m)]
        self.entries_c = [None for _ in range(self.n)]
        self.goal_var = tk.StringVar(value='max')

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.grid(row=0, column=0, sticky='nsew')

        ttk.Label(frm, text="Матриця A (4 x 5): ресурси ↓ / технології →").grid(row=0, column=0, columnspan=self.n)

        # Заголовки стовпців
        for j in range(self.n):
            ttk.Label(frm, text=f"x{j+1}").grid(row=1, column=j)

        # Поля матриці A
        for i in range(self.m):
            ttk.Label(frm, text=f"r{i+1}").grid(row=2 + i, column=self.n, sticky='e')
            for j in range(self.n):
                e = ttk.Entry(frm, width=8)
                e.grid(row=2 + i, column=j, padx=2, pady=2)
                e.insert(0, '0')
                self.entries_A[i][j] = e
                e.bind('<KeyRelease>', self._on_input_change)

        # Правая частина b та знак обмеження (заголовок над колонкою)
        ttk.Label(frm, text="RHS (b):").grid(row=1, column=self.n + 1, sticky='w')
        ttk.Label(frm, text="Знак").grid(row=1, column=self.n + 2, sticky='w')
        for i in range(self.m):
            eb = ttk.Entry(frm, width=8)
            eb.grid(row=2 + i, column=self.n + 1, padx=4)
            eb.insert(0, '0')
            self.entries_b[i] = eb
            eb.bind('<KeyRelease>', self._on_input_change)
            cb = ttk.Combobox(frm, values=['<=','>=','='], width=3)
            cb.grid(row=2 + i, column=self.n + 2)
            cb.set('<=')
            self.sign_vars[i] = cb
            cb.bind('<<ComboboxSelected>>', self._on_input_change)

        # Цільова функція c
        ttk.Label(frm, text="Коефіцієнти цільової функції c (5):").grid(row=7, column=0, columnspan=3, pady=(8,0))
        for j in range(self.n):
            ec = ttk.Entry(frm, width=8)
            ec.grid(row=8, column=j, padx=2, pady=2)
            ec.insert(0, '0')
            self.entries_c[j] = ec
            ec.bind('<KeyRelease>', self._on_input_change)

        # Кнопки та вибір мети (max/min)
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=9, column=0, columnspan=self.n+3, pady=(8,0))
        calc_btn = ttk.Button(btn_frame, text='Розрахувати', command=self.on_calculate)
        calc_btn.grid(row=0, column=0, padx=4)
        clear_btn = ttk.Button(btn_frame, text='Очистити', command=self.on_clear)
        clear_btn.grid(row=0, column=1, padx=4)
        load_btn = ttk.Button(btn_frame, text='Завантажити тестовий варіант', command=self.load_test)
        load_btn.grid(row=0, column=2, padx=4)
        save_btn = ttk.Button(btn_frame, text='Зберегти звіт у файл', command=self.save_report)
        save_btn.grid(row=0, column=3, padx=4)
        ttk.Label(btn_frame, text='Goal:').grid(row=0, column=4, padx=(12,2))
        goal_cb = ttk.Combobox(btn_frame, values=['max','min'], width=5, textvariable=self.goal_var)
        goal_cb.grid(row=0, column=5)

        # Праворуч — жива панель моделі та панель керування ітераціями
        right_frame = ttk.Frame(self.root, padding=8)
        right_frame.grid(row=0, column=1, rowspan=2, sticky='nsew')
        self.root.columnconfigure(1, weight=0)

        # Live preview
        ttk.Label(right_frame, text='Живий перегляд моделі', font=('TkDefaultFont', 10, 'bold')).grid(row=0, column=0, sticky='w')
        self.preview_var = tk.StringVar()
        self.preview_label = ttk.Label(right_frame, textvariable=self.preview_var, justify='left')
        self.preview_label.grid(row=1, column=0, sticky='w')

        # Текстове поле для однієї таблиці з прокруткою
        out_frame = ttk.Frame(right_frame)
        out_frame.grid(row=2, column=0, sticky='nsew')
        right_frame.rowconfigure(2, weight=1)
        right_frame.columnconfigure(0, weight=1)

        self.text = tk.Text(out_frame, wrap='none', height=20, font=('Courier', 10))
        self.text.grid(row=0, column=0, sticky='nsew')
        out_frame.rowconfigure(0, weight=1)
        out_frame.columnconfigure(0, weight=1)

        vsb = ttk.Scrollbar(out_frame, orient='vertical', command=self.text.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        hsb = ttk.Scrollbar(out_frame, orient='horizontal', command=self.text.xview)
        hsb.grid(row=1, column=0, sticky='ew')
        self.text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Навігація між кроками
        nav_frame = ttk.Frame(right_frame)
        nav_frame.grid(row=3, column=0, pady=(6,0), sticky='ew')
        prev_btn = ttk.Button(nav_frame, text='<- Попередня ітерація', command=self.on_prev)
        prev_btn.grid(row=0, column=0, padx=4)
        self.step_label = ttk.Label(nav_frame, text='Крок: 0/0')
        self.step_label.grid(row=0, column=1, padx=6)
        next_btn = ttk.Button(nav_frame, text='Наступна ітерація ->', command=self.on_next)
        next_btn.grid(row=0, column=2, padx=4)

        # Пояснення кроку
        ttk.Label(right_frame, text='Пояснення кроку', font=('TkDefaultFont', 10, 'bold')).grid(row=4, column=0, sticky='w', pady=(8,0))
        self.explain_text = tk.Text(right_frame, height=6, wrap='word')
        self.explain_text.grid(row=5, column=0, sticky='ew')
        self.explain_text.configure(state='disabled')

        # Налаштуємо теги підсвічування
        self.text.tag_config('enter_col', background='#d0f0c0')  # green-ish
        self.text.tag_config('enter_row', background='#f8d7da')  # red-ish
        self.text.tag_config('pivot', background='#fff7a8', font=('Courier', 10, 'bold'))  # yellow-ish

        # Ініціалізація керування кроками
        self.steps = []
        self.current_step = 0

    def _parse_fraction(self, s: str) -> Fraction:
        """Парсить рядок у Fraction. Кидає ValueError якщо рядок некоректний.

        Підтримує випадки 'a/b', десяткові, та коми як роздільник дробової частини.
        """
        if s is None:
            raise ValueError('Порожнє значення')
        s = s.strip().replace(',', '.')  # Безпечна заміна коми на крапку
        if s == '':
            raise ValueError('Порожнє значення')
        try:
            return Fraction(s)
        except Exception:
            try:
                return Fraction(float(s))
            except Exception:
                raise ValueError(f"Некоректне число: {s}")

    def on_clear(self):
        self.text.delete('1.0', tk.END)
        self.explain_text.configure(state='normal')
        self.explain_text.delete('1.0', tk.END)
        self.explain_text.configure(state='disabled')
        self.preview_var.set('')
        self.steps = []
        self.current_step = 0

    def _on_input_change(self, event=None):
        # Called on key release or combobox change — update live preview
        self.update_live_preview()

    def update_live_preview(self):
        # Build objective function string and constraints
        try:
            c = [self._parse_fraction(e.get()) for e in self.entries_c]
        except Exception:
            c = [None]*self.n
        lines = []
        # Objective
        obj_terms = []
        for j, coeff in enumerate(c):
            if coeff is None:
                term = f"c{j+1}*x{j+1}"
            else:
                term = f"{coeff}*x{j+1}"
            obj_terms.append(term)
        goal = self.goal_var.get() or 'max'
        lines.append(f"{goal} Z = " + ' + '.join(obj_terms))
        # Constraints
        for i in range(self.m):
            row_terms = []
            for j in range(self.n):
                try:
                    val = self._parse_fraction(self.entries_A[i][j].get())
                except Exception:
                    val = None
                if val is None:
                    term = f"a{i+1}{j+1}*x{j+1}"
                else:
                    term = f"{val}*x{j+1}"
                row_terms.append(term)
            sign = self.sign_vars[i].get() if self.sign_vars[i] is not None else '<='
            try:
                rhs = self._parse_fraction(self.entries_b[i].get())
            except Exception:
                rhs = 'b'+str(i+1)
            lines.append(' + '.join(row_terms) + f" {sign} {rhs}")
        self.preview_var.set('\n'.join(lines))

    def on_prev(self):
        if not self.steps:
            return
        if self.current_step > 0:
            self.current_step -= 1
            self.display_step(self.current_step)

    def on_next(self):
        if not self.steps:
            return
        if self.current_step < len(self.steps)-1:
            self.current_step += 1
            self.display_step(self.current_step)

    def display_step(self, idx: int):
        # Display pre-pivot tableau for step idx and highlight entering/row/pivot
        step = self.steps[idx]
        text = step.get('pre')
        self.text.configure(state='normal')
        self.text.delete('1.0', tk.END)
        self.text.insert('1.0', text)
        lines = text.splitlines()
        # compute column starts from header
        if not lines:
            return
        header = lines[0]
        cols = header.split(' | ')
        starts = []
        pos = 0
        for i, col in enumerate(cols):
            starts.append((pos, len(col)))
            pos += len(col) + 3  # account for ' | '
        # Clear tags
        for tag in ('enter_col','enter_row','pivot'):
            self.text.tag_remove(tag, '1.0', tk.END)
        entering = step.get('entering')
        leaving = step.get('leaving_row')
        pivot = step.get('pivot')
        # Highlight entering column (column index in header = 2 + entering)
        if entering is not None:
            col_idx = 2 + entering
            if col_idx < len(starts):
                start, width = starts[col_idx]
                for line_no in range(1, len(lines)+1):
                    line_text = lines[line_no-1]
                    # ensure bounds
                    if start <= len(line_text):
                        end = min(start+width, len(line_text))
                        try:
                            self.text.tag_add('enter_col', f"{line_no}.{start}", f"{line_no}.{end}")
                        except Exception:
                            pass
        # Highlight leaving row (data rows start at line index 2 -> Text line 3)
        if leaving is not None:
            data_row_line = 3 + leaving  # 1-based
            if 1 <= data_row_line <= len(lines):
                line_text = lines[data_row_line-1]
                self.text.tag_add('enter_row', f"{data_row_line}.0", f"{data_row_line}.{len(line_text)}")
        # Highlight pivot cell
        if entering is not None and leaving is not None and pivot is not None:
            col_idx = 2 + entering
            if col_idx < len(starts):
                start, width = starts[col_idx]
                data_row_line = 3 + leaving
                if 1 <= data_row_line <= len(lines):
                    line_text = lines[data_row_line-1]
                    end = min(start+width, len(line_text))
                    self.text.tag_add('pivot', f"{data_row_line}.{start}", f"{data_row_line}.{end}")
        self.text.configure(state='disabled')
        # Update step label
        self.step_label.config(text=f"Крок: {self.current_step+1}/{len(self.steps)}")
        # Update explanation
        expl = ''
        if step.get('entering') is None:
            expl = 'Оптимум досягнуто або немає напрямної змінної.'
        else:
            entering = step.get('entering')
            leaving = step.get('leaving_row')
            theta = step.get('theta')
            pivot = step.get('pivot')
            expl += f"Введено змінну x_{entering+1}.\n"
            if leaving is not None:
                expl += f"Вибрано рядок {leaving+1} як напрямний за мінімальним θ = {theta}.\n"
                expl += f"Опорний елемент = {pivot}.\n"
            else:
                expl += "Задача необмежена або не знайдено напрямного рядка.\n"
            pre_obj = step.get('pre_obj')
            if pre_obj is not None:
                expl += f"Значення цілі на цьому кроці: {pre_obj}.\n"
        self.explain_text.configure(state='normal')
        self.explain_text.delete('1.0', tk.END)
        self.explain_text.insert('1.0', expl)
        self.explain_text.configure(state='disabled')

    def append_text(self, txt: str):
        self.text.insert(tk.END, txt + "\n")
        self.text.see(tk.END)

    def save_report(self):
        """Зберегти вміст текстового поля у файл .txt або .doc"""
        content = self.text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showinfo("Збереження", "Немає даних для збереження.")
            return
        filetypes = [('Text files', '*.txt'), ('Word documents', '*.doc'), ('All files', '*.*')]
        filename = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=filetypes)
        if not filename:
            return
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo('Збережено', f'Звіт збережено у {filename}')
        except Exception as e:
            messagebox.showerror('Помилка при збереженні', str(e))

    def load_test(self):
        """Заповнює поля тестовим варіантом задачі."""
        # Цільова функція
        c_vals = [300, 260, 320, 400, 450]
        for j, val in enumerate(c_vals):
            self.entries_c[j].delete(0, tk.END)
            self.entries_c[j].insert(0, str(val))
        # Рядки A та обмеження b
        A_vals = [
            [15, 20, 12, 14, 18],           # Сировина
            [0.2, 0.3, 0.15, 0.25, 0.3],    # Електроенергія
            [4, 5, 6, 3, 2],               # Накладні витрати
            [5, 3, 4, 6, 3]                # Зарплата
        ]
        b_vals = [2000, 300, 1000, 1600]
        for i in range(self.m):
            for j in range(self.n):
                self.entries_A[i][j].delete(0, tk.END)
                self.entries_A[i][j].insert(0, str(A_vals[i][j]))
            self.entries_b[i].delete(0, tk.END)
            self.entries_b[i].insert(0, str(b_vals[i]))
            # default signs
            if self.sign_vars[i] is not None:
                self.sign_vars[i].set('<=')
        # default goal
        self.goal_var.set('max')

    def on_calculate(self):
        try:
            # Читання матриці A
            A = []
            for i in range(self.m):
                row = []
                for j in range(self.n):
                    val = self.entries_A[i][j].get()
                    row.append(self._parse_fraction(val))
                A.append(row)
            # Читання b
            b = [self._parse_fraction(e.get()) for e in self.entries_b]
            # Читання c
            c = [self._parse_fraction(e.get()) for e in self.entries_c]
        except ValueError as ex:
            messagebox.showerror("Помилка введення", f"Некоректне значення у полях вводу: {ex}")
            return

        # Збираємо знаки обмежень та goal
        signs = [cb.get() if cb is not None else '<=' for cb in self.sign_vars]
        goal = self.goal_var.get() or 'max'
        # Створюємо розв'язувач
        solver = SimplexSolver(A, b, c, signs=signs, goal=goal)
        solver.build_initial_tableau()

        # Підготуємо послідовність кроків (pre-таблиці перед поворотом)
        self.steps = []
        self.current_step = 0
        max_iter = 1000
        it = 0

        # Початковий стан
        pre = solver.format_tableau()
        # обчислимо значення цілі на початковому кроці (може бути MValue)
        try:
            z = sum([solver.C_b[i] * solver.tableau[i][-1] for i in range(solver.m)], 0)
        except Exception:
            z = None
        self.steps.append({'pre': pre, 'entering': None, 'leaving_row': None, 'pivot': None, 'theta': None, 'pre_obj': z})

        while True:
            it += 1
            if it > max_iter:
                messagebox.showwarning('Повідомлення', 'Перевищено максимум ітерацій')
                break
            pre_table = deepcopy(solver.tableau)
            pre_formatted = solver.format_tableau()
            res = solver.iterate(verbose=False)
            status = res.get('status')
            entering = res.get('entering')
            leaving_row = res.get('leaving_row')
            if status == 'continue':
                # compute pivot and theta from pre_table
                pivot = None
                theta = None
                try:
                    if entering is not None and leaving_row is not None:
                        pivot = pre_table[leaving_row][entering]
                        if pivot != 0:
                            theta = pre_table[leaving_row][-1] / pivot
                except Exception:
                    pivot = None
                    theta = None
                post_formatted = res.get('tableau') or solver.format_tableau()
                # compute objective on pre-step
                try:
                    z = sum([solver.C_b[i] * pre_table[i][-1] for i in range(solver.m)], 0)
                except Exception:
                    z = None
                self.steps.append({'pre': pre_formatted, 'entering': entering, 'leaving_row': leaving_row, 'pivot': pivot, 'theta': theta, 'pre_obj': z, 'post': post_formatted})
                continue
            elif status == 'unbounded':
                messagebox.showinfo('Результат', f'Задача необмежена. Напрямний стовпець: x_{entering+1}')
                break
            elif status == 'optimal':
                # append final pre-state
                pre_formatted = solver.format_tableau()
                try:
                    z = sum([solver.C_b[i] * solver.tableau[i][-1] for i in range(solver.m)], 0)
                except Exception:
                    z = None
                self.steps.append({'pre': pre_formatted, 'entering': None, 'leaving_row': None, 'pivot': None, 'theta': None, 'pre_obj': z})
                messagebox.showinfo('Результат', f'Знайдено оптимум після {it-1} ітерацій')
                break
            else:
                messagebox.showerror('Помилка', f'Невідомий статус: {status}')
                break

        # Показати перший крок
        if self.steps:
            self.display_step(0)
            self.step_label.config(text=f"Крок: 1/{len(self.steps)}")

        # Фінальний звіт — обчислюємо через final_report
        report = solver.final_report(as_str=True)
        self.explain_text.configure(state='normal')
        self.explain_text.delete('1.0', tk.END)
        self.explain_text.insert('1.0', f"Оптимальні значення x1..x5: {report['primal_x_str']}\nF_max = {report['F_max_str']}")
        self.explain_text.configure(state='disabled')


if __name__ == '__main__':
    root = tk.Tk()
    app = SimplexGUI(root)
    root.geometry('900x700')
    root.mainloop()
