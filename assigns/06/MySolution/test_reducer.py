"""unittest suite for the target path of evaluator.py.

Run from assigns/06:
    python3.12 -m unittest -v MySolution/test_reducer.py
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from target import Var, Lam, App, alpha_equiv  # noqa: E402
from evaluator import (  # noqa: E402
    reduce_term, Reduction, OpenTermError, VALUE, EXHAUSTED,
)

x, y = Var("x"), Var("y")
I = Lam("x", x)
K = Lam("x", Lam("y", x))                  # lam x. lam y. x
OMEGA_HALF = Lam("x", App(x, x))
OMEGA = App(OMEGA_HALF, OMEGA_HALF)        # diverges, one step per loop


class BudgetBoundaryTests(unittest.TestCase):
    # ACC-03
    def test_value_with_budget_zero(self):
        self.assertEqual(reduce_term(I, 0), Reduction(VALUE, I, 0))

    def test_redex_with_budget_zero_exhausts(self):
        result = reduce_term(App(I, I), 0)
        self.assertEqual(result.status, EXHAUSTED)
        self.assertEqual(result.steps, 0)
        self.assertEqual(result.term, App(I, I))

    def test_value_on_last_permitted_step_completes(self):
        self.assertEqual(reduce_term(App(I, I), 1), Reduction(VALUE, I, 1))

    def test_extra_budget_unused(self):
        self.assertEqual(reduce_term(App(I, I), 100), Reduction(VALUE, I, 1))

    def test_invalid_budgets(self):
        for bad in (-1, 1.5, None, True):
            with self.subTest(budget=bad):
                with self.assertRaises(ValueError):
                    reduce_term(I, bad)


class StrategyTests(unittest.TestCase):
    def test_no_reduction_under_lambda(self):
        # ACC-02: lam x. ((lam y. y) x) is already a value.
        term = Lam("x", App(Lam("y", y), x))
        self.assertEqual(reduce_term(term, 10), Reduction(VALUE, term, 0))

    def test_left_then_right_then_outer(self):
        # ACC-02: (I I) (I I) contracts the left child, the right, then the outer.
        trace = []
        result = reduce_term(App(App(I, I), App(I, I)), 10, trace)
        self.assertEqual(result, Reduction(VALUE, I, 3))
        self.assertEqual(trace, [App(I, I), App(I, I), App(I, I)])

    def test_left_to_right_order_distinguishable(self):
        # Mark which side reduces first: ((lam a. a) K) ((lam b. b) I)
        left = App(Lam("a", Var("a")), K)
        right = App(Lam("b", Var("b")), I)
        trace = []
        reduce_term(App(left, right), 10, trace)
        self.assertEqual(trace[0], left)
        self.assertEqual(trace[1], right)

    def test_argument_evaluated_before_substitution(self):
        # (lam x. I) ((lam y. y) I): the argument redex is contracted first.
        trace = []
        result = reduce_term(App(Lam("x", I), App(Lam("y", y), I)), 10, trace)
        self.assertEqual(result, Reduction(VALUE, I, 2))
        self.assertEqual(trace[0], App(Lam("y", y), I))

    def test_call_by_value_diverging_argument(self):
        # (lam x. I) OMEGA: the unused argument is still evaluated, so exhaust.
        result = reduce_term(App(Lam("x", I), OMEGA), 50)
        self.assertEqual(result.status, EXHAUSTED)
        self.assertEqual(result.steps, 50)

    def test_diverging_function_position_skips_argument(self):
        # OMEGA ((lam y. y) I): the argument is never reached.
        trace = []
        reduce_term(App(OMEGA, App(Lam("y", y), I)), 20, trace)
        self.assertTrue(all(redex == OMEGA for redex in trace))

    def test_divergence_exhausts_budget(self):
        for budget in (0, 1, 7, 1000):
            with self.subTest(budget=budget):
                result = reduce_term(OMEGA, budget)
                self.assertEqual(result.status, EXHAUSTED)
                self.assertEqual(result.steps, budget)
                self.assertEqual(result.term, OMEGA)

    def test_large_budget_does_not_overflow_stack(self):
        result = reduce_term(OMEGA, 100_000)
        self.assertEqual((result.status, result.steps), (EXHAUSTED, 100_000))

    def test_k_combinator(self):
        result = reduce_term(App(App(K, I), OMEGA_HALF), 10)
        self.assertEqual(result, Reduction(VALUE, I, 2))

    def test_exhausted_residual_is_whole_program(self):
        # Budget runs out inside the right child; the residual keeps the context.
        term = App(Lam("f", Var("f")), App(I, I))
        result = reduce_term(term, 0)
        self.assertEqual(result.term, term)
        result = reduce_term(term, 1)
        self.assertEqual(result.status, EXHAUSTED)
        self.assertEqual(result.term, App(Lam("f", Var("f")), I))


class SafetyTests(unittest.TestCase):
    def test_deterministic_and_input_unchanged(self):
        # ACC-04
        term = App(App(K, App(I, I)), OMEGA_HALF)
        snapshot = copy.deepcopy(term)
        first = reduce_term(term, 10)
        second = reduce_term(term, 10)
        self.assertEqual(first, second)
        self.assertEqual(term, snapshot)

    def test_open_term_rejected(self):
        with self.assertRaises(OpenTermError):
            reduce_term(App(I, y), 10)
        with self.assertRaises(OpenTermError):
            reduce_term(Lam("x", y), 10)

    def test_result_up_to_alpha(self):
        # (lam a. lam b. a) (lam z. z) gives lam b. (lam z. z).
        term = App(Lam("a", Lam("b", Var("a"))), Lam("z", Var("z")))
        result = reduce_term(term, 5)
        self.assertTrue(alpha_equiv(result.term, Lam("q", I)))


if __name__ == "__main__":
    unittest.main()
