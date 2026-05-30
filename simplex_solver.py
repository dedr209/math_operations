"""
Симплекс-метод для розв'язання задач лінійного програмування на максимізацію.
Використовує fractions.Fraction для точних обчислень без похибок округлення.
"""

from fractions import Fraction
from typing import List, Tuple, Optional, Dict


class SimplexSolver:
    """
    Клас для розв'язання задач лінійного програмування методом симплекс.
    
    Задача в стандартному вигляді:
        max c^T * x
        s.t. A*x <= b
             x >= 0
    
    Система автоматично перетворюється в канонічний вигляд з додаванням
    вільних змінних: A*x + s = b, де s >= 0 (вільні змінні).
    """
    
    def __init__(self, A: List[List], b: List, c: List):
        """
        Ініціалізація розв'язувача.
        
        Args:
            A: матриця коефіцієнтів обмежень (m x n), де m - кількість обмежень, n - змінних
            b: вектор правих частин обмежень (довжина m)
            c: коефіцієнти цільової функції (довжина n)
        """
        self.m = len(A)  # кількість обмежень
        self.n = len(A[0]) if A else 0  # кількість основних змінних
        
        # Конвертуємо в Fraction для точних обчислень
        self.A_original = [[Fraction(A[i][j]) for j in range(self.n)] for i in range(self.m)]
        self.b = [Fraction(val) for val in b]
        self.c_original = [Fraction(val) for val in c]
        
        # Перевірка коректності вхідних даних
        if len(self.b) != self.m:
            raise ValueError(f"Розмір b ({len(self.b)}) не відповідає кількості рядків A ({self.m})")
        if len(self.c_original) != self.n:
            raise ValueError(f"Розмір c ({len(self.c_original)}) не відповідає кількості стовпців A ({self.n})")
        
        # Розширена таблиця з додатковими змінними
        self.tableau = None
        self.basis = None
        self.non_basis = None
        self.solution = None
        self.optimal_value = None
        self.iterations = 0
        
    def _add_slack_variables(self):
        """Додає вільні змінні для перетворення нерівностей <= у рівняння.

        Підбирає розширену таблицю без додаткового рядка цільової функії.
        Ініціалізує вектор C_b (коефіцієнти цільової функції для базисних змінних)
        та розширений вектор коефіцієнтів цільової функції c_extended.
        """
        # Розширена матриця: [A | I | b] (I - одиничні вектори для вільних змінних)
        self.tableau = []
        for i in range(self.m):
            row = self.A_original[i][:] + [Fraction(0)] * self.m + [self.b[i]]
            # Додаємо одиничну матрицю для слабких змінних
            row[self.n + i] = Fraction(1)
            self.tableau.append(row)

        # Розширений вектор коефіцієнтів цільової функії: c для основних змінних + 0 для вільних
        self.c_extended = self.c_original[:] + [Fraction(0)] * self.m

        # Ініціалізуємо вектор C_b (коефіцієнти цільової функції для базисних змінних)
        # Спочатку в базисі вільні змінні з нульовими коефіцієнтами
        self.C_b = [Fraction(0)] * self.m

        # Ініціалізуємо базові та небазові змінні
        self.basis = list(range(self.n, self.n + self.m))
        self.non_basis = list(range(self.n))

        # Індексний рядок (Delta) ще не обчислено
        self.delta = None

    def build_initial_tableau(self):
        """Формує початкову симплекс-таблицю з вільними змінними як початковим базисом.

        Це публічний метод-обгортка над внутрішнім _add_slack_variables(),
        щоб виклик формування таблиці був зрозумілішим у публічному API.
        """
        self._add_slack_variables()

    def compute_delta(self):
        """Публічний метод для обчислення індексного рядка Δ.

        Повертає список оцінок Δ_j для всіх стовпців (включно з RHS/A0 в кінці).
        """
        return self._compute_delta()

    def is_optimal(self, delta: Optional[list] = None) -> bool:
        """Перевіряє критерій оптимальності для задачі максимізації.

        Якщо немає від'ємних оцінок Δ_j серед стовпців змінних (без RHS/A0),
        план вважається оптимальним.
        """
        if delta is None:
            delta = self._compute_delta()
        # Перевіряємо тільки стовпці змінних (не включаємо RHS/A0)
        for j in range(self.n + self.m):
            if delta[j] < 0:
                return False
        return True

    def _compute_delta(self):
        """Обчислює індексний рядок Δ_j = sum_i C_b[i] * tableau[i][j] - c_j для всіх стовпців,
        включаючи стовпець вільних членів (RHS / A0)."""
        num_cols = self.n + self.m + 1  # останній стовпець - RHS (A0)
        delta = [Fraction(0)] * num_cols
        for j in range(num_cols):
            s = Fraction(0)
            for i in range(self.m):
                s += self.C_b[i] * self.tableau[i][j]
            c_j = self.c_extended[j] if j < len(self.c_extended) else Fraction(0)
            delta[j] = s - c_j
        self.delta = delta
        return delta

    def _find_entering_variable(self) -> Optional[int]:
        """
        Знаходить змінну для введення в базис за правилом: вибираємо стовпець з
        найбільш від'ємним значенням Δ (по модулю — тобто найменше значення Δ).
        Повертає None якщо всі Δ_j >= 0 (оптимум).
        """
        delta = self._compute_delta()
        entering = None
        min_val = Fraction(0)
        # Перебираємо всі стовпці змінних (без стовпця RHS/A0)
        for j in range(self.n + self.m):
            if delta[j] < min_val:
                min_val = delta[j]
                entering = j
        return entering

    def _find_leaving_variable(self, entering: int) -> Optional[int]:
        """
        Знаходить змінну для виведення з базису за правилом мінімального відношення.
        """
        min_ratio = None
        leaving_row = None
        for i in range(self.m):
            coeff = self.tableau[i][entering]
            if coeff > 0:
                ratio = self.tableau[i][-1] / coeff
                if min_ratio is None or ratio < min_ratio:
                    min_ratio = ratio
                    leaving_row = i
        if leaving_row is None:
            raise ValueError("Задача необмежена (необмежений розв'язок)")
        return leaving_row

    def _pivot(self, entering: int, leaving_row: int):
        """
        Виконує крок симплекс-методу (поворот таблиці) і оновлює C_b відповідно до нового базису.
        (Реалізація методом Жордана-Гаусса — нормалізація опорного рядка і
        занулення відповідного стовпця у всіх інших рядках.)
        """
        pivot_element = self.tableau[leaving_row][entering]
        # Нормалізуємо опорний рядок
        row_len = len(self.tableau[leaving_row])
        for j in range(row_len):
            self.tableau[leaving_row][j] /= pivot_element
        # Застосовуємо правило прямокутника (Jordan-Gauss): занулюємо стовпець entering
        for i in range(self.m):
            if i != leaving_row:
                factor = self.tableau[i][entering]
                for j in range(row_len):
                    # a_ij := a_ij - factor * a_pivotj
                    self.tableau[i][j] -= factor * self.tableau[leaving_row][j]
        # Оновлюємо базис і C_b
        old_basis_var = self.basis[leaving_row]
        self.basis[leaving_row] = entering
        # Оновлюємо C_b для нової базисної змінної
        new_Cb = self.c_extended[entering] if entering < len(self.c_extended) else Fraction(0)
        self.C_b[leaving_row] = new_Cb
        # Оновлюємо списки небазисних змінних
        if entering in self.non_basis:
            self.non_basis.remove(entering)
        self.non_basis.append(old_basis_var)
        # Після повороту індексний рядок буде обчислено знову при наступному виклику
        self.delta = None

    def iterate(self) -> Dict:
        """Виконує одну ітерацію симплекс-методу.

        Повертає словник з інформацією про крок:
         - 'status': 'continue', 'optimal', або 'unbounded'
         - 'entering': індекс стовпця що входить у базис (або None)
         - 'leaving_row': індекс рядка що виходить з базису (або None)
        """
        # Обчислюємо індексний рядок
        delta = self._compute_delta()
        # Перевіряємо оптимальність
        if self.is_optimal(delta):
            return {'status': 'optimal', 'entering': None, 'leaving_row': None}
        # Вибираємо напрямний стовпець: найменше (найбільш від'ємне) значення Δ серед змінних
        entering = None
        min_delta = Fraction(0)
        for j in range(self.n + self.m):
            if delta[j] < min_delta:
                min_delta = delta[j]
                entering = j
        # Якщо entering не знайдений (мабуть через числові нюанси) — вважаємо оптимум
        if entering is None:
            return {'status': 'optimal', 'entering': None, 'leaving_row': None}
        # Шукаємо напрямний рядок за мінімальним позитивним симплекс-відношенням θ = RHS / a_ij
        min_ratio = None
        leaving_row = None
        for i in range(self.m):
            a_ij = self.tableau[i][entering]
            if a_ij > 0:
                theta = self.tableau[i][-1] / a_ij
                if min_ratio is None or theta < min_ratio:
                    min_ratio = theta
                    leaving_row = i
        if leaving_row is None:
            return {'status': 'unbounded', 'entering': entering, 'leaving_row': None}
        # Виконуємо поворот (Jordan-Gauss)
        self._pivot(entering, leaving_row)
        return {'status': 'continue', 'entering': entering, 'leaving_row': leaving_row}

    def solve(self) -> Dict:
        """
        Розв'язує задачу лінійного програмування методом симплекс.
        Реалізовано згідно з академічною методикою: індексний рядок Δ обчислюється
        як Δ_j = sum(C_b[i] * tableau[i][j]) - c_j; умова оптимальності — всі Δ_j >= 0.
        """
        # Додаємо вільні змінні і підготуємо структури
        self._add_slack_variables()
        max_iterations = 10000
        while True:
            self.iterations += 1
            if self.iterations > max_iterations:
                return {'status': 'error', 'message': f'Перевищена максимальна кількість ітерацій ({max_iterations})', 'iterations': self.iterations}
            # Обчислюємо індексний рядок
            delta = self._compute_delta()
            # Критерій оптимальності: всі Δ_j >= 0
            entering = None
            min_delta = Fraction(0)
            # Перебираємо тільки змінні (не включаємо стовпець RHS/A0)
            for j in range(self.n + self.m):
                val = delta[j]
                if val < min_delta:
                    min_delta = val
                    entering = j
            if entering is None:
                break
            # Знаходимо вихідну змінну
            try:
                leaving_row = self._find_leaving_variable(entering)
            except ValueError as e:
                return {'status': 'unbounded', 'message': str(e), 'iterations': self.iterations}
            # Повертаємо таблицю
            self._pivot(entering, leaving_row)
        # Після оптимізації обчислюємо значення цільової функції: z = sum(C_b[i] * RHS_i)
        z = Fraction(0)
        for i in range(self.m):
            z += self.C_b[i] * self.tableau[i][-1]
        self.optimal_value = z
        # Розв'язок для всіх змінних
        all_vars = [Fraction(0)] * (self.n + self.m)
        for i, basis_var in enumerate(self.basis):
            all_vars[basis_var] = self.tableau[i][-1]
        self.solution = all_vars[:self.n]
        return {'status': 'optimal', 'x': self.solution, 'objective_value': self.optimal_value, 'iterations': self.iterations, 'all_variables': all_vars}

    def get_solution_as_float(self) -> Dict:
        """Повертає розв'язок з float значеннями для зручності."""
        if self.solution is None:
            return None
        return {'status': 'optimal', 'x': [float(val) for val in self.solution], 'objective_value': float(self.optimal_value), 'iterations': self.iterations}

    def get_solution_as_fraction(self) -> Dict:
        """Повертає розв'язок з Fraction значеннями (точні значення)."""
        if self.solution is None:
            return None
        return {'status': 'optimal', 'x': self.solution, 'objective_value': self.optimal_value, 'iterations': self.iterations}

    def print_tableau(self):
        """Виводить поточну симплекс-таблицю у форматі академічної методики.

        Виводить стовпець C_b, назви змінних (x1..xn та вільні x_{n+1}..), матрицю коефіцієнтів,
        RHS (A0) та нижній рядок оцінок Δ.
        """
        if self.tableau is None:
            print("Таблиця ще не ініціалізована. Спершу викличте solve().")
            return
        # Заголовок
        var_names = []
        for j in range(self.n + self.m):
            if j < self.n:
                var_names.append(f"x_{j+1}")
            else:
                var_names.append(f"x_{j+1}")  # вільні як продовження нумерації
        var_names.append("A0")  # RHS
        # Обчислюємо індексний рядок перед виводом
        delta = self._compute_delta()
        # Друкуємо таблицю
        col_width = 10
        sep = " | "
        # Header line
        header = f"{'C_b':>{col_width}}{sep}{'Basis':>{col_width}}"
        for name in var_names:
            header += f"{sep}{name:>{col_width}}"
        print("\n" + header)
        print('-' * len(header))
        # Rows
        for i in range(self.m):
            cb = str(self.C_b[i])
            basis_var = self.basis[i]
            if basis_var < self.n:
                basis_name = f"x_{basis_var+1}"
            else:
                basis_name = f"x_{basis_var+1}"
            row = f"{cb:>{col_width}}{sep}{basis_name:>{col_width}}"
            for j in range(self.n + self.m + 1):
                row += f"{sep}{str(self.tableau[i][j]):>{col_width}}"
            print(row)
        # Footer: Delta row and objective value
        print('-' * len(header))
        delta_row = f"{'':>{col_width}}{sep}{'Δ':>{col_width}}"
        for j in range(self.n + self.m + 1):
            delta_row += f"{sep}{str(delta[j]):>{col_width}}"
        print(delta_row)
        # Objective value (right-bottom corner) — z = sum(C_b * RHS)
        z = sum(self.C_b[i] * self.tableau[i][-1] for i in range(self.m))
        print(f"\nObjective z = {z}")
        print('=' * len(header))


# Приклади використання
if __name__ == "__main__":
    print("=" * 80)
    print("ПРИКЛАД 1: Простої задача")
    print("=" * 80)
    print("\nЗадача:")
    print("max  3x₁ + 2x₂")
    print("s.t. 2x₁ +  x₂ ≤ 100")
    print("      x₁ + x₂ ≤ 80")
    print("     x₁, x₂ ≥ 0")
    
    # Матриця коефіцієнтів обмежень
    A = [
        [2, 1],
        [1, 1]
    ]
    # Вектор правих частин
    b = [100, 80]
    # Коефіцієнти цільової функції
    c = [3, 2]
    
    solver = SimplexSolver(A, b, c)
    result = solver.solve()
    
    print(f"\nРезультат: {result['status']}")
    print(f"x₁ = {result['x'][0]} ≈ {float(result['x'][0]):.4f}")
    print(f"x₂ = {result['x'][1]} ≈ {float(result['x'][1]):.4f}")
    print(f"Макс. значення z = {result['objective_value']} ≈ {float(result['objective_value']):.4f}")
    print(f"Кількість ітерацій: {result['iterations']}")
    
    print("\n" + "=" * 80)
    print("ПРИКЛАД 2: Задача з більшою кількістю обмежень")
    print("=" * 80)
    print("\nЗадача:")
    print("max  5x₁ + 4x₂ + 3x₃")
    print("s.t. 2x₁ + 3x₂ +  x₃ ≤ 5")
    print("     4x₁ +  x₂ + 2x₃ ≤ 11")
    print("     3x₁ + 4x₂ + 2x₃ ≤ 8")
    print("    x₁, x₂, x₃ ≥ 0")
    
    A2 = [
        [2, 3, 1],
        [4, 1, 2],
        [3, 4, 2]
    ]
    b2 = [5, 11, 8]
    c2 = [5, 4, 3]
    
    solver2 = SimplexSolver(A2, b2, c2)
    result2 = solver2.solve()
    
    print(f"\nРезультат: {result2['status']}")
    print(f"x₁ = {result2['x'][0]} ≈ {float(result2['x'][0]):.4f}")
    print(f"x₂ = {result2['x'][1]} ≈ {float(result2['x'][1]):.4f}")
    print(f"x₃ = {result2['x'][2]} ≈ {float(result2['x'][2]):.4f}")
    print(f"Макс. значення z = {result2['objective_value']} ≈ {float(result2['objective_value']):.4f}")
    print(f"Кількість ітерацій: {result2['iterations']}")
    
    print("\n" + "=" * 80)
    print("ПРИКЛАД 3: Задача з дробовими коефіцієнтами")
    print("=" * 80)
    print("\nЗадача:")
    print("max  1/2·x₁ + 3/2·x₂")
    print("s.t.  x₁ +  x₂ ≤ 4")
    print("      x₁ - 0.5x₂ ≤ 1")
    print("    x₁, x₂ ≥ 0")
    
    A3 = [
        [1, 1],
        [1, Fraction(-1, 2)]
    ]
    b3 = [4, 1]
    c3 = [Fraction(1, 2), Fraction(3, 2)]
    
    solver3 = SimplexSolver(A3, b3, c3)
    result3 = solver3.solve()
    
    print(f"\nРезультат: {result3['status']}")
    print(f"x₁ = {result3['x'][0]} ≈ {float(result3['x'][0]):.4f}")
    print(f"x₂ = {result3['x'][1]} ≈ {float(result3['x'][1]):.4f}")
    print(f"Макс. значення z = {result3['objective_value']} ≈ {float(result3['objective_value']):.4f}")
    print(f"Кількість ітерацій: {result3['iterations']}")
