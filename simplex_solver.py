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
    слабких змінних: A*x + s = b, де s >= 0 (слабкі змінні).
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
        self.n = len(A[0]) if A else 0  # кількість оригінальних змінних
        
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
        """Додає слабкі змінні для перетворення нерівностей <= у рівняння."""
        # Розширена матриця: [A | I | b] (I - одиничні вектори для слабких змінних)
        self.tableau = []
        for i in range(self.m):
            row = self.A_original[i][:] + [Fraction(0)] * self.m + [self.b[i]]
            # Додаємо одиничну матрицю для слабких змінних
            row[self.n + i] = Fraction(1)
            self.tableau.append(row)
        
        # Рядок цільової функції: [c | 0 | 0]
        # (для максимізації: симплекс-метод робить коефіцієнти від'ємними)
        objective_row = self.c_original[:] + [Fraction(0)] * (self.m + 1)
        self.tableau.append(objective_row)
        
        # Ініціалізуємо базові та вільні змінні
        # Базові: слабкі змінні (s_1, s_2, ..., s_m)
        self.basis = list(range(self.n, self.n + self.m))
        # Вільні: оригінальні змінні (x_1, x_2, ..., x_n)
        self.non_basis = list(range(self.n))
    
    def _find_entering_variable(self) -> Optional[int]:
        """
        Знаходить змінну для введення в базис.
        Вибираємо стовпець з найбільшим позитивним коефіцієнтом в рядку цільової функції
        (для максимізації).
        
        Returns:
            Індекс змінної або None, якщо розв'язок оптимальний.
        """
        objective_row = self.tableau[-1]
        max_coeff = Fraction(0)
        entering = None
        
        # Шукаємо найбільший позитивний коефіцієнт (стовпець останній не враховуємо)
        for j in range(len(objective_row) - 1):
            if objective_row[j] > max_coeff:
                max_coeff = objective_row[j]
                entering = j
        
        return entering
    
    def _find_leaving_variable(self, entering: int) -> Optional[int]:
        """
        Знаходить змінну для виведення з базису за правилом мінімального відношення.
        
        Args:
            entering: індекс змінної що входить в базис
            
        Returns:
            Індекс рядка (базисної змінної) або None, якщо проблема необмежена.
        """
        min_ratio = None
        leaving_row = None
        
        for i in range(self.m):
            if self.tableau[i][entering] > 0:
                ratio = self.tableau[i][-1] / self.tableau[i][entering]
                if min_ratio is None or ratio < min_ratio:
                    min_ratio = ratio
                    leaving_row = i
        
        if leaving_row is None:
            raise ValueError("Задача необмежена (необмежений розв'язок)")
        
        return leaving_row
    
    def _pivot(self, entering: int, leaving_row: int):
        """
        Виконує крок симплекс-методу (поворот таблиці).
        
        Args:
            entering: індекс стовпця для введення
            leaving_row: індекс рядка для виведення
        """
        pivot_element = self.tableau[leaving_row][entering]
        
        # Нормалізуємо рядок з розв'язуючим елементом
        for j in range(len(self.tableau[leaving_row])):
            self.tableau[leaving_row][j] /= pivot_element
        
        # Приводимо всі інші рядки
        for i in range(len(self.tableau)):
            if i != leaving_row:
                factor = self.tableau[i][entering]
                for j in range(len(self.tableau[i])):
                    self.tableau[i][j] -= factor * self.tableau[leaving_row][j]
        
        # Оновлюємо базис
        old_basis_var = self.basis[leaving_row]
        self.basis[leaving_row] = entering
        self.non_basis.remove(entering)
        self.non_basis.append(old_basis_var)
    
    def solve(self) -> Dict:
        """
        Розв'язує задачу лінійного програмування методом симплекс.
        
        Returns:
            Словник з результатами:
            - 'status': 'optimal', 'unbounded', або 'error'
            - 'x': оптимальне рішення (список значень для оригінальних змінних)
            - 'objective_value': оптимальне значення цільової функції
            - 'iterations': кількість ітерацій симплекс-методу
            - 'all_variables': значення всіх змінних (включаючи слабкі)
        """
        # Додаємо слабкі змінни
        self._add_slack_variables()
        
        max_iterations = 10000  # Захист від нескінченного циклу
        
        while True:
            self.iterations += 1
            
            if self.iterations > max_iterations:
                return {
                    'status': 'error',
                    'message': f'Перевищена максимальна кількість ітерацій ({max_iterations})',
                    'iterations': self.iterations
                }
            
            # Знаходимо змінну для введення
            entering = self._find_entering_variable()
            
            # Якщо немає від'ємних коефіцієнтів - знайшли оптимум
            if entering is None:
                break
            
            # Знаходимо змінну для виведення
            try:
                leaving_row = self._find_leaving_variable(entering)
            except ValueError as e:
                return {
                    'status': 'unbounded',
                    'message': str(e),
                    'iterations': self.iterations
                }
            
            # Виконуємо крок симплекс-методу
            self._pivot(entering, leaving_row)
        
        # Вилучаємо розв'язок
        self.optimal_value = -self.tableau[-1][-1]  # Таблиця зберігає -z, тому беремо з протилежним знаком
        
        # Розв'язок для всіх змінних
        all_vars = [Fraction(0)] * (self.n + self.m)
        for i, basis_var in enumerate(self.basis):
            all_vars[basis_var] = self.tableau[i][-1]
        
        # Вилучаємо значення оригінальних змінних (без слабких)
        self.solution = all_vars[:self.n]
        
        return {
            'status': 'optimal',
            'x': self.solution,
            'objective_value': self.optimal_value,
            'iterations': self.iterations,
            'all_variables': all_vars
        }
    
    def get_solution_as_float(self) -> Dict:
        """Повертає розв'язок з float значеннями для зручності."""
        if self.solution is None:
            return None
        
        return {
            'status': 'optimal',
            'x': [float(val) for val in self.solution],
            'objective_value': float(self.optimal_value),
            'iterations': self.iterations
        }
    
    def get_solution_as_fraction(self) -> Dict:
        """Повертає розв'язок з Fraction значеннями (точні значення)."""
        if self.solution is None:
            return None
        
        return {
            'status': 'optimal',
            'x': self.solution,
            'objective_value': self.optimal_value,
            'iterations': self.iterations
        }
    
    def print_tableau(self):
        """Виводить поточну симплекс-таблицю."""
        if self.tableau is None:
            print("Таблиця ще не ініціалізована. Спершу викличте solve().")
            return
        
        print("\nСимплекс-таблиця:")
        print("=" * 80)
        
        # Заголовок
        header = "Базис | "
        for j in range(self.n + self.m):
            if j < self.n:
                header += f"x_{j+1:2d}     | "
            else:
                header += f"s_{j-self.n+1:2d}     | "
        header += "RHS"
        print(header)
        print("-" * 80)
        
        # Рядки таблиці
        for i in range(self.m):
            basis_var = self.basis[i]
            if basis_var < self.n:
                basis_name = f"x_{basis_var+1}"
            else:
                basis_name = f"s_{basis_var-self.n+1}"
            
            row_str = f"{basis_name:6s}| "
            for j in range(self.n + self.m):
                row_str += f"{str(self.tableau[i][j]):8s}| "
            row_str += str(self.tableau[i][-1])
            print(row_str)
        
        # Рядок цільової функції
        print("-" * 80)
        row_str = "z     | "
        for j in range(self.n + self.m):
            row_str += f"{str(self.tableau[-1][j]):8s}| "
        row_str += str(self.tableau[-1][-1])
        print(row_str)
        print("=" * 80)


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
