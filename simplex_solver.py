"""
Симплекс-метод для розв'язання задач лінійного програмування на максимізацію.
Використовує fractions.Fraction для точних обчислень без похибок округлення.
"""

from fractions import Fraction
from typing import List, Tuple, Optional, Dict


class MValue:
    """
    Symbolic value representing a + b*M, where a and b are Fractions and M is a symbolic
    infinitely large positive constant used for Big M penalty.

    Comparisons treat M as positive infinity (i.e., b dominates a).
    Only limited arithmetic is supported: addition/subtraction with MValue or Fraction,
    multiplication/division by Fractions. Multiplication of two MValues both having
    non-zero M-part is not supported (would produce M^2 terms).
    """
    def __init__(self, a=0, m=0):
        self.a = Fraction(a)
        self.m = Fraction(m)

    @classmethod
    def zero(cls):
        return cls(0, 0)

    def copy(self):
        return MValue(self.a, self.m)

    def __add__(self, other):
        if isinstance(other, MValue):
            return MValue(self.a + other.a, self.m + other.m)
        else:
            return MValue(self.a + Fraction(other), self.m)

    __radd__ = __add__

    def __neg__(self):
        return MValue(-self.a, -self.m)

    def __sub__(self, other):
        if isinstance(other, MValue):
            return MValue(self.a - other.a, self.m - other.m)
        else:
            return MValue(self.a - Fraction(other), self.m)

    def __rsub__(self, other):
        # other - self
        if isinstance(other, MValue):
            return other.__sub__(self)
        else:
            return MValue(Fraction(other) - self.a, -self.m)

    def __mul__(self, other):
        # Support multiplication by Fraction/int or by MValue when one side has zero M-part
        if isinstance(other, MValue):
            if self.m != 0 and other.m != 0:
                raise NotImplementedError("Multiplication producing M^2 is not supported")
            # (a1 + b1 M)*(a2 + b2 M) -> a1*a2 + (a1*b2 + a2*b1) M
            a = self.a * other.a
            m = self.a * other.m + other.a * self.m
            return MValue(a, m)
        else:
            f = Fraction(other)
            return MValue(self.a * f, self.m * f)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        # Only support division by scalar Fractions/ints
        if isinstance(other, MValue):
            raise NotImplementedError("Division by MValue is not supported")
        f = Fraction(other)
        return MValue(self.a / f, self.m / f)

    def __eq__(self, other):
        if isinstance(other, MValue):
            return self.m == other.m and self.a == other.a
        else:
            return self.m == 0 and self.a == Fraction(other)

    def _cmp_key(self):
        # For comparisons: M-part dominates (treated as infinity). Compare m first,
        # then a.
        return (self.m, self.a)

    def __lt__(self, other):
        if not isinstance(other, MValue):
            other = MValue(Fraction(other), 0)
        # Compare m first
        if self.m != other.m:
            return self.m < other.m
        return self.a < other.a

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return not self.__le__(other)

    def __ge__(self, other):
        return not self.__lt__(other)

    def __repr__(self):
        return f"MValue(a={self.a}, m={self.m})"

    def __str__(self):
        parts = []
        if self.a != 0:
            parts.append(str(self.a))
        if self.m != 0:
            m_part = str(self.m) + "*M" if self.m != 1 else "M"
            parts.append(m_part)
        if not parts:
            return "0"
        return " + ".join(parts)


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
    
    def __init__(self, A: List[List], b: List, c: List, signs: Optional[List[str]] = None, goal: str = 'max'):
        """
        Ініціалізація розв'язувача.
        
        Args:
            A: матриця коефіцієнтів обмежень (m x n), де m - кількість обмежень, n - змінних
            b: вектор правих частин обмежень (довжина m)
            c: коефіцієнти цільової функції (довжина n)
            signs: список знаків обмежень для кожного рядка ("<=", ">=", "="). Якщо None — припускається "<=" для всіх.
            goal: тип оптимізації: 'max' (за замовчуванням) або 'min'
        """
        self.m = len(A)  # кількість обмежень
        self.n = len(A[0]) if A else 0  # кількість основних змінних

        # Конвертуємо в Fraction для точних обчислень
        self.A_original = [[Fraction(A[i][j]) for j in range(self.n)] for i in range(self.m)]
        self.b = [Fraction(val) for val in b]
        self.c_original = [Fraction(val) for val in c]

        # Обробка додаткових параметрів: signs та goal
        if signs is None:
            self.signs = ['<='] * self.m
        else:
            if len(signs) != self.m:
                raise ValueError(f"Розмір signs ({len(signs)}) не відповідає кількості рядків A ({self.m})")
            # Нормалізація рядків знаків
            normalized = []
            for s in signs:
                s_str = str(s).strip()
                if s_str not in ('<=', '>=', '='):
                    raise ValueError(f"Непідтримуваний знак обмеження: {s}")
                normalized.append(s_str)
            self.signs = normalized

        if goal not in ('max', 'min'):
            raise ValueError("goal має бути 'max' або 'min'")
        self.goal = goal

        # --- Канонізація перед основною логікою ---
        # 1) Якщо це задача мінімізації — переведемо в макс шляхом інверсії c
        if self.goal == 'min':
            self.c_original = [ -val for val in self.c_original ]

        # 2) Якщо b[i] < 0 — помножимо відповідний рядок на -1 і інвертуємо знак обмеження
        for i in range(self.m):
            if self.b[i] < 0:
                # помножимо рядок і RHS на -1
                self.A_original[i] = [ -a for a in self.A_original[i] ]
                self.b[i] = -self.b[i]
                # інвертуємо знак
                if self.signs[i] == '<=':
                    self.signs[i] = '>='
                elif self.signs[i] == '>=':
                    self.signs[i] = '<='
                # якщо рівність — залишаємо як є

        # Рівності та >= будуть оброблені під час формування початкової таблиці (_add_slack_variables).

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
        """Додає додаткові та штучні змінні відповідно до signs і формує початкову таблицю.

        Логіка (послідовно по рядках):
         - '<=' : додається додаткова змінна (+1) — вона може стати базисною
         - '>=' : додається від'ємна змінна (-1) та штучна змінна (+1) — штучна може стати базисною
         - '='  : додається штучна змінна (+1) — штучна може стати базисною

        Штучні змінні отримують штраф у цільовій функції як -M (для максимізації),
        тобто c_artificial = MValue(0, -1).
        """
        # Підрахуємо, які додаткові стовпці потрібні та розподілимо їх по рядках
        col_ops = [[] for _ in range(self.m)]  # для кожного рядка — список (col_idx, coeff)
        next_col = self.n
        artificial_cols = []
        slack_cols = []
        surplus_cols = []
        for i in range(self.m):
            s = self.signs[i]
            if s == '<=':
                # додати додаткову змінну (+1)
                col_ops[i].append((next_col, Fraction(1)))
                slack_cols.append(next_col)
                next_col += 1
            elif s == '>=':
                # від'ємна змінна (-1) та штучна змінна (+1)
                col_ops[i].append((next_col, Fraction(-1)))
                surplus_cols.append(next_col)
                next_col += 1
                col_ops[i].append((next_col, Fraction(1)))
                artificial_cols.append(next_col)
                next_col += 1
            elif s == '=':
                # штучна змінна (+1)
                col_ops[i].append((next_col, Fraction(1)))
                artificial_cols.append(next_col)
                next_col += 1
            else:
                raise ValueError(f"Непідтримуваний знак під час побудови таблиці: {s}")

        total_added = next_col - self.n
        self.total_vars = self.n + total_added
        # Збережемо індекс та коефіцієнт першої доданої колонки для кожного обмеження
        self.added_col_info = []
        for i in range(self.m):
            if col_ops[i]:
                first_col, first_coeff = col_ops[i][0]
                self.added_col_info.append((first_col, first_coeff))
            else:
                self.added_col_info.append((None, None))

        # Побудуємо tableau: кожний рядок = A[i] + zeros(added) + [b_i], потім встановимо коефіцієнти доданих стовпців
        self.tableau = []
        for i in range(self.m):
            row = self.A_original[i][:] + [Fraction(0)] * total_added + [self.b[i]]
            for (col_idx, coeff) in col_ops[i]:
                # перетворимо глобальний індекс col_idx на позицію у розширеному векторі
                row[col_idx] = coeff
            self.tableau.append(row)

        # Побудуємо c_extended як MValue: основні змінні з c_original, додаткові — 0 або -M для штучних
        c_list = [MValue(val, 0) for val in self.c_original]
        # Додаткові колонки за порядком індексації next_col вищому: від self.n до self.total_vars-1
        for col in range(self.n, self.total_vars):
            if col in artificial_cols:
                # штраф -M для максимізації
                c_list.append(MValue(0, -1))
            else:
                c_list.append(MValue.zero())
        self.c_extended = c_list

        # Ініціалізуємо базис: для доданих змінних, відповідні одиничні стовпці потрапляють у базис
        basis = []
        C_b = []
        non_basis = list(range(self.n))
        for i in range(self.m):
            # знайдемо, яка колонка є одиничною в цьому рядку — базисна
            found_basis = None
            for (col_idx, coeff) in col_ops[i]:
                if coeff == 1 and col_idx in artificial_cols:
                    found_basis = col_idx
                    break
                if coeff == 1 and col_idx in slack_cols:
                    found_basis = col_idx
                    break
            if found_basis is None:
                # ні одиничної колонки — знайдемо artificial у рядку якщо вона є
                for (col_idx, coeff) in col_ops[i]:
                    if col_idx in artificial_cols:
                        found_basis = col_idx
                        break
            if found_basis is None:
                # як резерв — просто взяти перший доданий стовпець
                if col_ops[i]:
                    found_basis = col_ops[i][0][0]
            basis.append(found_basis)
            # C_b — коефіцієнт цілі для базисної змінної
            if found_basis in artificial_cols:
                C_b.append(MValue(0, -1))
            else:
                C_b.append(MValue.zero())
            # якщо базисна змінна вже була у non_basis — видалимо
            if found_basis in non_basis:
                non_basis.remove(found_basis)

        self.basis = basis
        self.non_basis = non_basis
        self.C_b = C_b

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
        zero = MValue.zero()
        for j in range(self.total_vars):
            if delta[j] < zero:
                return False
        return True

    def _compute_delta(self):
        """Обчислює індексний рядок Δ_j = sum_i C_b[i] * tableau[i][j] - c_j для всіх стовпців,
        включаючи стовпець вільних членів (RHS / A0). Повертає список MValue."""
        num_cols = self.total_vars + 1  # останній стовпець - RHS (A0)
        delta = [MValue.zero() for _ in range(num_cols)]
        for j in range(num_cols):
            s = MValue.zero()
            for i in range(self.m):
                # C_b[i] is MValue, tableau entries are Fraction -> MValue * Fraction
                s = s + (self.C_b[i] * self.tableau[i][j])
            c_j = self.c_extended[j] if j < len(self.c_extended) else MValue.zero()
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
        min_val = MValue.zero()
        # Перебираємо всі стовпці змінних (без стовпця RHS/A0)
        for j in range(self.total_vars):
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
        new_Cb = self.c_extended[entering] if entering < len(self.c_extended) else MValue.zero()
        self.C_b[leaving_row] = new_Cb
        # Оновлюємо списки небазисних змінних
        if entering in self.non_basis:
            self.non_basis.remove(entering)
        self.non_basis.append(old_basis_var)
        # Після повороту індексний рядок буде обчислено знову при наступному виклику
        self.delta = None

    def iterate(self, verbose: bool = False) -> Dict:
        """Виконує одну ітерацію симплекс-методу.

        Повертає словник з інформацією про крок:
         - 'status': 'continue', 'optimal', або 'unbounded'
         - 'entering': індекс стовпця що входить у базис (або None)
         - 'leaving_row': індекс рядка що виходить з базису (або None)
         - 'tableau': (str) форматована таблиця після ітерації
        Якщо verbose=True — таблиця буде надрукована в консоль.
        """
        # Обчислюємо індексний рядок
        delta = self._compute_delta()
        # Перевіряємо оптимальність
        if self.is_optimal(delta):
            formatted = self.format_tableau()
            if verbose:
                print(formatted)
            return {'status': 'optimal', 'entering': None, 'leaving_row': None, 'tableau': formatted}
        # Вибираємо напрямний стовпець: найменше (найбільш від'ємне) значення Δ серед змінних
        entering = None
        min_delta = MValue.zero()
        for j in range(self.total_vars):
            if delta[j] < min_delta:
                min_delta = delta[j]
                entering = j
        # Якщо entering не знайдений (мабуть через числові нюанси) — вважаємо оптимум
        if entering is None:
            formatted = self.format_tableau()
            if verbose:
                print(formatted)
            return {'status': 'optimal', 'entering': None, 'leaving_row': None, 'tableau': formatted}
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
            formatted = self.format_tableau()
            if verbose:
                print(formatted)
            return {'status': 'unbounded', 'entering': entering, 'leaving_row': None, 'tableau': formatted}

        # Запам'ятовуємо назву змінної, що виходить з базису, ДО виконання повороту
        leaving_var_idx = self.basis[leaving_row]

        # Виконуємо поворот (Jordan-Gauss)
        self._pivot(entering, leaving_row)
        formatted = self.format_tableau()
        if verbose:
            print(formatted)
        return {'status': 'continue', 'entering': entering, 'leaving_row': leaving_row, 'leaving_var': leaving_var_idx, 'tableau': formatted}

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
            min_delta = MValue.zero()
            # Перебираємо тільки змінні (не включаємо стовпець RHS/A0)
            for j in range(self.total_vars):
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
        z = MValue.zero()
        for i in range(self.m):
            z = z + (self.C_b[i] * self.tableau[i][-1])
        self.optimal_value = z
        # Розв'язок для всіх змінних
        all_vars = [Fraction(0)] * self.total_vars
        for i, basis_var in enumerate(self.basis):
            all_vars[basis_var] = self.tableau[i][-1]
        self.solution = all_vars[:self.n]
        # Ensure backward compatibility: if optimal_value has no M-part, return Fraction
        obj_ret = self.optimal_value
        if isinstance(self.optimal_value, MValue) and self.optimal_value.m == 0:
            obj_ret = self.optimal_value.a
        return {'status': 'optimal', 'x': self.solution, 'objective_value': obj_ret, 'iterations': self.iterations, 'all_variables': all_vars}

    def get_solution_as_float(self) -> Dict:
        """Повертає розв'язок з float значеннями для зручності."""
        if self.solution is None:
            return None
        # objective_value may be MValue; if M-part is zero, convert to float of a
        if isinstance(self.optimal_value, MValue):
            if self.optimal_value.m == 0:
                obj = float(self.optimal_value.a)
            else:
                raise ValueError("objective contains symbolic M; cannot convert to float")
        else:
            obj = float(self.optimal_value)
        return {'status': 'optimal', 'x': [float(val) for val in self.solution], 'objective_value': obj, 'iterations': self.iterations}

    def get_solution_as_fraction(self) -> Dict:
        """Повертає розв'язок з Fraction значеннями (точні значення)."""
        if self.solution is None:
            return None
        # objective_value may be MValue; return as Fraction if possible
        if isinstance(self.optimal_value, MValue):
            if self.optimal_value.m == 0:
                obj = self.optimal_value.a
            else:
                obj = self.optimal_value
        else:
            obj = self.optimal_value
        return {'status': 'optimal', 'x': self.solution, 'objective_value': obj, 'iterations': self.iterations}

    def _frac_to_str(self, f) -> str:
        """Повертає красиве представлення Fraction або MValue.

        Якщо f — MValue, повертає вираз 'a + b*M' або просто 'a' якщо M-частина нульова.
        """
        # MValue
        if isinstance(f, MValue):
            # Якщо немає частини M — виводимо тільки a як Fraction
            if f.m == 0:
                val = f.a
                if val.denominator == 1:
                    return str(val.numerator)
                return f"{val.numerator}/{val.denominator}"
            # Інакше формуємо рядок a + b*M
            parts = []
            if f.a != 0:
                a = f.a
                if a.denominator == 1:
                    parts.append(str(a.numerator))
                else:
                    parts.append(f"{a.numerator}/{a.denominator}")
            if f.m != 0:
                m = f.m
                m_str = str(m) + "*M" if m != 1 else "M"
                parts.append(m_str)
            return " + ".join(parts)
        # Fraction-like
        if not isinstance(f, Fraction):
            f = Fraction(f)
        if f.denominator == 1:
            return str(f.numerator)
        return f"{f.numerator}/{f.denominator}"

    def format_tableau(self) -> str:
        """Повертає форматовану симплекс-таблицю як рядок.

        Таблиця містить: C_b, назву базисної змінної, коефіцієнти при змінних,
        стовпець RHS (A0) та індексний рядок Δ.
        """
        if self.tableau is None:
            return "Таблиця ще не ініціалізована. Спершу викличте build_initial_tableau() або solve()."
        # Імена змінних
        var_names = [f"x_{j+1}" for j in range(self.total_vars)] + ["A0"]
        # Обчислюємо Δ
        delta = self._compute_delta()
        # Підготуємо матрицю рядків як списки рядків
        rows = []
        header = ["C_b", "Basis"] + var_names
        rows.append(header)
        # Дані рядків
        for i in range(self.m):
            cb = self._frac_to_str(self.C_b[i])
            basis_var = self.basis[i]
            basis_name = f"x_{basis_var+1}"
            row = [cb, basis_name]
            for j in range(self.total_vars + 1):
                row.append(self._frac_to_str(self.tableau[i][j]))
            rows.append(row)
        # Додаємо Δ рядок
        delta_row = ["", "Δ"] + [self._frac_to_str(delta[j]) for j in range(self.total_vars)] + [self._frac_to_str(delta[self.total_vars])]
        rows.append(delta_row)
        # Визначаємо ширину колонок
        col_widths = [max(len(r[col]) for r in rows) for col in range(len(header))]
        # Формуємо рядки тексту
        lines = []
        # header
        hline = " | ".join(rows[0][col].rjust(col_widths[col]) for col in range(len(header)))
        lines.append(hline)
        lines.append("-" * len(hline))
        for r in rows[1:]:
            line = " | ".join(r[col].rjust(col_widths[col]) for col in range(len(header)))
            lines.append(line)
        return "\n".join(lines)

    def print_tableau(self):
        """Друкує поточну симплекс-таблицю в консоль у відформатованому вигляді.

        Використовує format_tableau()."""
        print(self.format_tableau())

    def final_report(self, as_str: bool = False) -> Dict:
        """Повертає фінальний звіт після розв'язання задачі.

        Повертає словник з ключами:
          - 'primal_x': список з 5 значень (Fraction) для x1..x5 (додає нулі якщо потрібно)
          - 'F_max': значення цільової функції (Fraction)
          - 'dual_y': список з 4 значень (Fraction) для y1..y4, взятих з Δ під початковими вільними змінними
        Якщо as_str=True — також додається 'primal_x_str', 'F_max_str', 'dual_y_str' з красиво відформатованими рядками.
        """
        if self.solution is None:
            # Якщо ще не розв'язано — спробуємо викликати solve()
            self.solve()
        # Пояснюємо x: беремо перші 5 основних змінних (або доповнюємо нулями)
        primal = list(self.solution[:5]) + [Fraction(0)] * max(0, 5 - len(self.solution))
        # F_max — оптимальне значення цільової функції
        F_max = self.optimal_value
        # Dual variables y: беремо Δ під початковими додатковими змінними
        # Обчислюємо Δ для поточної таблиці
        delta = self._compute_delta()
        # початкові додаткові змінні мали індекси n..n+added-1
        dual = []
        # Використовуємо збережену інформацію про першу додану колонку для кожного обмеження
        for i in range(self.m):
            idx, coeff = (None, None)
            if hasattr(self, 'added_col_info'):
                idx, coeff = self.added_col_info[i]
            if idx is None or idx >= len(delta) or coeff is None:
                dual.append(Fraction(0))
            else:
                val = delta[idx]
                # dual y_i = delta[idx] / coeff  (коригуємо знак коли coeff == -1)
                try:
                    if isinstance(val, MValue):
                        # MValue supports division by scalar
                        y = val / coeff
                    else:
                        y = val / coeff
                except Exception:
                    y = val
                dual.append(y)
        report = {'primal_x': primal, 'F_max': F_max, 'dual_y': dual}
        if as_str:
            report['primal_x_str'] = [self._frac_to_str(v) for v in report['primal_x']]
            report['F_max_str'] = self._frac_to_str(report['F_max'])
            report['dual_y_str'] = [self._frac_to_str(v) for v in report['dual_y']]
        return report



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
