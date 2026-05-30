"""
Тести для розв'язувача симплекс-методу.
"""

import unittest
from fractions import Fraction
from simplex_solver import SimplexSolver


class TestSimplexSolver(unittest.TestCase):
    """Тести базової функціональності SimplexSolver"""
    
    def test_simple_problem(self):
        """Тест простої задачі з 2 змінними і 2 обмеженнями"""
        # max 3x1 + 2x2
        # s.t. 2x1 + x2 <= 100
        #      x1 + x2 <= 80
        
        A = [[2, 1], [1, 1]]
        b = [100, 80]
        c = [3, 2]
        
        solver = SimplexSolver(A, b, c)
        result = solver.solve()
        
        self.assertEqual(result['status'], 'optimal')
        self.assertEqual(result['x'][0], Fraction(20))
        self.assertEqual(result['x'][1], Fraction(60))
        self.assertEqual(result['objective_value'], Fraction(180))
        
    def test_three_variables(self):
        """Тест задачі з 3 змінними"""
        # max 5x1 + 4x2 + 3x3
        # s.t. 2x1 + 3x2 + x3 <= 5
        #      4x1 + x2 + 2x3 <= 11
        #      3x1 + 4x2 + 2x3 <= 8
        
        A = [[2, 3, 1], [4, 1, 2], [3, 4, 2]]
        b = [5, 11, 8]
        c = [5, 4, 3]
        
        solver = SimplexSolver(A, b, c)
        result = solver.solve()
        
        self.assertEqual(result['status'], 'optimal')
        self.assertEqual(result['x'][0], Fraction(2))
        self.assertEqual(result['x'][1], Fraction(0))
        self.assertEqual(result['x'][2], Fraction(1))
        self.assertEqual(result['objective_value'], Fraction(13))
    
    def test_fractional_coefficients(self):
        """Тест задачі з дробовими коефіцієнтами"""
        # max (1/2)x1 + (3/2)x2
        # s.t. x1 + x2 <= 4
        #      x1 - 0.5x2 <= 1
        
        A = [[1, 1], [1, Fraction(-1, 2)]]
        b = [4, 1]
        c = [Fraction(1, 2), Fraction(3, 2)]
        
        solver = SimplexSolver(A, b, c)
        result = solver.solve()
        
        self.assertEqual(result['status'], 'optimal')
        self.assertEqual(result['x'][0], Fraction(0))
        self.assertEqual(result['x'][1], Fraction(4))
        self.assertEqual(result['objective_value'], Fraction(6))
    
    def test_zero_solution(self):
        """Тест задачі з оптимальним розв'язком (0, 0)"""
        # max -x1 - x2
        # s.t. x1 + x2 <= 1
        
        A = [[1, 1]]
        b = [1]
        c = [-1, -1]
        
        solver = SimplexSolver(A, b, c)
        result = solver.solve()
        
        self.assertEqual(result['status'], 'optimal')
        self.assertEqual(result['x'][0], Fraction(0))
        self.assertEqual(result['x'][1], Fraction(0))
        self.assertEqual(result['objective_value'], Fraction(0))
    
    def test_single_variable(self):
        """Тест задачі з однією змінною"""
        # max 5x1
        # s.t. x1 <= 10
        
        A = [[1]]
        b = [10]
        c = [5]
        
        solver = SimplexSolver(A, b, c)
        result = solver.solve()
        
        self.assertEqual(result['status'], 'optimal')
        self.assertEqual(result['x'][0], Fraction(10))
        self.assertEqual(result['objective_value'], Fraction(50))
    
    def test_slack_variables_created(self):
        """Тест того, що слабкі змінні автоматично додаються"""
        A = [[1, 1], [2, 1]]
        b = [10, 15]
        c = [2, 3]
        
        solver = SimplexSolver(A, b, c)
        solver._add_slack_variables()
        
        # Матриця має розмір (m+1) x (n+m+1)
        # m=2, n=2, отже (3) x (5)
        self.assertEqual(len(solver.tableau), 3)  # 2 обмеження + 1 рядок z
        self.assertEqual(len(solver.tableau[0]), 5)  # 2 оригінальні + 2 слабкі + 1 RHS
    
    def test_fractions_precision(self):
        """Тест точності без похибок округлення"""
        # max (1/3)x1 + (1/7)x2
        # s.t. x1 + x2 <= 100
        
        A = [[1, 1]]
        b = [100]
        c = [Fraction(1, 3), Fraction(1, 7)]
        
        solver = SimplexSolver(A, b, c)
        result = solver.solve()
        
        self.assertEqual(result['status'], 'optimal')
        # Оптимум досягається коли x1 = 100, x2 = 0 (max(1/3, 1/7) = 1/3)
        # або коли максимізується перший коефіцієнт
        # Перевіримо, що результат точний (використовуючи Fraction)
        self.assertIsInstance(result['objective_value'], Fraction)


class TestSimplexSolverEdgeCases(unittest.TestCase):
    """Тести граничних випадків"""
    
    def test_degenerate_case(self):
        """Тест виродженого випадку"""
        # max 2x1 + x2
        # s.t. x1 <= 5
        #      x2 <= 10
        
        A = [[1, 0], [0, 1]]
        b = [5, 10]
        c = [2, 1]
        
        solver = SimplexSolver(A, b, c)
        result = solver.solve()
        
        self.assertEqual(result['status'], 'optimal')
        self.assertEqual(result['x'][0], Fraction(5))
        self.assertEqual(result['x'][1], Fraction(10))
        self.assertEqual(result['objective_value'], Fraction(20))
    
    def test_negative_coefficients_in_objective(self):
        """Тест цільової функції з від'ємними коефіцієнтами"""
        # max -x1 + 3x2
        # s.t. x1 + x2 <= 10
        
        A = [[1, 1]]
        b = [10]
        c = [-1, 3]
        
        solver = SimplexSolver(A, b, c)
        result = solver.solve()
        
        self.assertEqual(result['status'], 'optimal')
        # x1=0, x2=10 для максимізації -x1 + 3x2 = 30
        self.assertEqual(result['x'][0], Fraction(0))
        self.assertEqual(result['x'][1], Fraction(10))
        self.assertEqual(result['objective_value'], Fraction(30))


class TestSimplexInputValidation(unittest.TestCase):
    """Тести валідації вхідних даних"""
    
    def test_mismatched_dimensions(self):
        """Тест на помилку при невідповідних розмірах"""
        A = [[1, 2]]
        b = [10, 20]  # Невідповідна довжина
        c = [1, 1]
        
        with self.assertRaises(ValueError):
            SimplexSolver(A, b, c)
    
    def test_mismatched_objective_dimensions(self):
        """Тест на помилку при невідповідних розмірах цільової функції"""
        A = [[1, 2, 3]]
        b = [10]
        c = [1, 1]  # Невідповідна довжина
        
        with self.assertRaises(ValueError):
            SimplexSolver(A, b, c)


if __name__ == '__main__':
    unittest.main(verbosity=2)
