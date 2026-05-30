"""
Простий GUI для SimplexSolver на tkinter.
Надає форму для введення матриці A (4 ресурси x 5 технологій), векторів b (4) та c (5).
Виводить покроково симплекс-таблиці в текстове поле з прокруткою.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from fractions import Fraction
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
        self.entries_c = [None for _ in range(self.n)]

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
            ttk.Label(frm, text=f"r{i+1}").grid(row=2 + i, column= -1)  # not visible but for alignment
            for j in range(self.n):
                e = ttk.Entry(frm, width=8)
                e.grid(row=2 + i, column=j, padx=2, pady=2)
                e.insert(0, '0')
                self.entries_A[i][j] = e

        # Правая частина b
        ttk.Label(frm, text="RHS (b):").grid(row=2, column=self.n + 1, sticky='w')
        for i in range(self.m):
            eb = ttk.Entry(frm, width=8)
            eb.grid(row=2 + i, column=self.n + 1, padx=4)
            eb.insert(0, '0')
            self.entries_b[i] = eb

        # Цільова функція c
        ttk.Label(frm, text="Коефіцієнти цільової функції c (5):").grid(row=7, column=0, columnspan=3, pady=(8,0))
        for j in range(self.n):
            ec = ttk.Entry(frm, width=8)
            ec.grid(row=8, column=j, padx=2, pady=2)
            ec.insert(0, '0')
            self.entries_c[j] = ec

        # Кнопки
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=9, column=0, columnspan=self.n+2, pady=(8,0))
        calc_btn = ttk.Button(btn_frame, text='Розрахувати', command=self.on_calculate)
        calc_btn.grid(row=0, column=0, padx=4)
        clear_btn = ttk.Button(btn_frame, text='Очистити', command=self.on_clear)
        clear_btn.grid(row=0, column=1, padx=4)
        load_btn = ttk.Button(btn_frame, text='Завантажити тестовий варіант', command=self.load_test)
        load_btn.grid(row=0, column=2, padx=4)
        save_btn = ttk.Button(btn_frame, text='Зберегти звіт у файл', command=self.save_report)
        save_btn.grid(row=0, column=3, padx=4)

        # Текстове поле для виводу з прокруткою
        out_frame = ttk.Frame(self.root)
        out_frame.grid(row=1, column=0, sticky='nsew')
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)

        self.text = tk.Text(out_frame, wrap='none', height=20)
        self.text.grid(row=0, column=0, sticky='nsew')
        out_frame.rowconfigure(0, weight=1)
        out_frame.columnconfigure(0, weight=1)

        vsb = ttk.Scrollbar(out_frame, orient='vertical', command=self.text.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        hsb = ttk.Scrollbar(out_frame, orient='horizontal', command=self.text.xview)
        hsb.grid(row=1, column=0, sticky='ew')
        self.text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

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

        # Створюємо розв'язувач
        solver = SimplexSolver(A, b, c)
        solver.build_initial_tableau()

        # Виводимо початкову таблицю
        self.append_text("Початкова симплекс-таблиця:")
        self.append_text(solver.format_tableau())

        # Ітерації
        max_iter = 1000
        it = 0
        while True:
            it += 1
            if it > max_iter:
                self.append_text("Перевищено максимум ітерацій")
                break
            res = solver.iterate(verbose=False)
            status = res.get('status')
            entering = res.get('entering')
            leaving = res.get('leaving_row')
            if status == 'continue':
                leaving_var = res.get('leaving_var')
                self.append_text(f"Ітерація {it}: введено змінну x_{entering+1}, виведено з базису змінну x_{leaving_var+1}")
                self.append_text(res.get('tableau') or solver.format_tableau())
                continue
            elif status == 'unbounded':
                self.append_text(f"Задача необмежена (unbounded). Напрямний стовпець: x_{entering+1}")
                break
            elif status == 'optimal':
                self.append_text(f"Знайдено оптимум після {it-1} ітерацій")
                self.append_text(solver.format_tableau())
                break
            else:
                self.append_text(f"Невідомий статус: {status}")
                break

        # Фінальний звіт
        report = solver.final_report(as_str=True)
        self.append_text("\nФінальний звіт:")
        self.append_text(f"Оптимальні значення x1..x5: {report['primal_x_str']}")
        self.append_text(f"F_max = {report['F_max_str']}")
        self.append_text(f"Оптимальний план двоїстої задачі y1..y4: {report['dual_y_str']}")


if __name__ == '__main__':
    root = tk.Tk()
    app = SimplexGUI(root)
    root.geometry('900x700')
    root.mainloop()
