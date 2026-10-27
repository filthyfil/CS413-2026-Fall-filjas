"""unittest suite for church.py (encodings) and observe.py (decoders).

Each encoding is tested on its own by running it with the shared evaluator
and decoding the result with the observers. Run from assigns/06:
    python3.12 -m unittest -v MySolution/test_church.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from church import (  # noqa: E402
    lam, app, num, COMBINATORS, I, TRUE, FALSE, NOT, AND, OR, PAIR, FST, SND,
    ZERO, SUCC, PRED, ISZERO, ADD, SUB, MUL, LEQ, GEQ, LT, GT, EQ, NEQ, Z,
)
from evaluator import reduce_term  # noqa: E402
from observe import (  # noqa: E402
    observe, STEP, BASE, MARK_T, MARK_F, DECODED, EXHAUSTED, MALFORMED,
)
from target import Var, Lam, App, free_vars, is_pure, term_print, alpha_equiv  # noqa: E402

EXEC, OBS = 20_000, 20_000


def run(term, kind):
    """Execute a closed target term, then observe it as kind."""
    result = reduce_term(term, EXEC)
    assert result.completed, f"execution exhausted: {term_print(term)}"
    obs = observe(result.term, kind, OBS)
    assert obs.decoded, f"observation {obs.status}: {obs.detail}"
    return obs.value


def nat(term):
    return run(term, "nat")


def boolean(term):
    return run(term, "bool")


def B(b):
    return TRUE if b else FALSE


class StructureTests(unittest.TestCase):
    def test_combinators_closed_and_pure(self):
        for name, term in COMBINATORS.items():
            with self.subTest(name):
                self.assertTrue(is_pure(term))
                self.assertEqual(free_vars(term), frozenset())
        for n in range(6):
            self.assertEqual(free_vars(num(n)), frozenset())

    def test_spec_shapes(self):
        self.assertEqual(term_print(num(0)), "(lam s. (lam z. z))")
        self.assertEqual(term_print(num(2)), "(lam s. (lam z. (s (s z))))")
        self.assertEqual(term_print(TRUE), "(lam t. (lam f. t))")
        self.assertEqual(term_print(FALSE), "(lam t. (lam f. f))")
        self.assertEqual(term_print(PAIR), "(lam a. (lam b. (lam p. ((p a) b))))")
        self.assertEqual(term_print(Z),
                         "(lam g. ((lam x. (g (lam v. ((x x) v))))"
                         " (lam x. (g (lam v. ((x x) v))))))")

    def test_zero_and_false_coincide(self):
        self.assertTrue(alpha_equiv(num(0), FALSE))

    def test_num_rejects_non_naturals(self):
        for bad in (-1, 1.0, True):
            with self.assertRaises(ValueError):
                num(bad)

    def test_helpers(self):
        self.assertEqual(lam("x", "y", Var("x")), Lam("x", Lam("y", Var("x"))))
        self.assertEqual(app(Var("f"), Var("a"), Var("b")),
                         App(App(Var("f"), Var("a")), Var("b")))


class NumeralTests(unittest.TestCase):
    def test_literals(self):
        for n in (0, 1, 2, 7, 24):
            with self.subTest(n=n):
                self.assertEqual(nat(num(n)), n)

    def test_succ(self):
        self.assertEqual(nat(app(SUCC, ZERO)), 1)
        self.assertEqual(nat(app(SUCC, num(4))), 5)

    def test_pred(self):
        self.assertEqual(nat(app(PRED, ZERO)), 0)        # pred 0 = 0
        self.assertEqual(nat(app(PRED, num(1))), 0)
        self.assertEqual(nat(app(PRED, num(5))), 4)

    def test_iszero(self):
        self.assertIs(boolean(app(ISZERO, ZERO)), True)
        self.assertIs(boolean(app(ISZERO, num(3))), False)

    def test_add(self):
        self.assertEqual(nat(app(ADD, ZERO, ZERO)), 0)
        self.assertEqual(nat(app(ADD, num(2), num(3))), 5)
        self.assertEqual(nat(app(ADD, num(4), ZERO)), 4)

    def test_sub_truncated(self):
        self.assertEqual(nat(app(SUB, num(5), num(2))), 3)
        self.assertEqual(nat(app(SUB, num(3), num(3))), 0)
        self.assertEqual(nat(app(SUB, num(2), num(5))), 0)
        self.assertEqual(nat(app(SUB, ZERO, num(1))), 0)
        self.assertEqual(nat(app(SUB, num(4), ZERO)), 4)

    def test_mul(self):
        self.assertEqual(nat(app(MUL, num(3), num(4))), 12)
        self.assertEqual(nat(app(MUL, num(5), ZERO)), 0)
        self.assertEqual(nat(app(MUL, ZERO, num(5))), 0)
        self.assertEqual(nat(app(MUL, num(1), num(6))), 6)

    def test_nested_arithmetic(self):
        # 2 + 3 * 4 = 14
        self.assertEqual(nat(app(ADD, num(2), app(MUL, num(3), num(4)))), 14)


class ComparisonTests(unittest.TestCase):
    PAIRS = [(0, 0), (0, 1), (1, 0), (2, 3), (3, 2), (3, 3), (4, 7)]
    OPS = {"<=": (LEQ, lambda m, n: m <= n), ">=": (GEQ, lambda m, n: m >= n),
           "<": (LT, lambda m, n: m < n), ">": (GT, lambda m, n: m > n),
           "==": (EQ, lambda m, n: m == n), "!=": (NEQ, lambda m, n: m != n)}

    def test_all_comparisons(self):
        # Expected answers come from Python comparisons on the test inputs;
        # the encoded comparison itself runs only by beta reduction.
        for name, (comb, expected) in self.OPS.items():
            outcomes = set()
            for m, n in self.PAIRS:
                with self.subTest(op=name, m=m, n=n):
                    got = boolean(app(comb, num(m), num(n)))
                    self.assertIs(got, expected(m, n))
                    outcomes.add(got)
            self.assertEqual(outcomes, {True, False}, f"{name} needs both outcomes")


class BooleanTests(unittest.TestCase):
    def test_literals(self):
        self.assertIs(boolean(TRUE), True)
        self.assertIs(boolean(FALSE), False)

    def test_truth_tables(self):
        for a in (True, False):
            self.assertIs(boolean(app(NOT, B(a))), not a)
            for b in (True, False):
                with self.subTest(a=a, b=b):
                    self.assertIs(boolean(app(AND, B(a), B(b))), a and b)
                    self.assertIs(boolean(app(OR, B(a), B(b))), a or b)


class PairTests(unittest.TestCase):
    def test_projections(self):
        p = app(PAIR, num(2), TRUE)
        self.assertEqual(nat(app(FST, p)), 2)
        self.assertIs(boolean(app(SND, p)), True)

    def test_observe_pair(self):
        self.assertEqual(run(app(PAIR, num(2), TRUE), ("nat", "bool")), (2, True))

    def test_nested_pair(self):
        # ACC-12: pair (pair 2 true) 3
        term = app(PAIR, app(PAIR, num(2), TRUE), num(3))
        self.assertEqual(run(term, (("nat", "bool"), "nat")), ((2, True), 3))


def fact_term():
    """Z (lam f. lam n. (ISZERO n (lam u. 1) (lam u. n * f (PRED n))) I)."""
    body = app(app(ISZERO, Var("n")),
               lam("u", num(1)),
               lam("u", app(MUL, Var("n"), app(Var("f"), app(PRED, Var("n"))))))
    return app(Z, lam("f", "n", app(body, I)))


class RecursionTests(unittest.TestCase):
    def test_z_factorial(self):
        for n, expected in ((0, 1), (1, 1), (3, 6), (4, 24)):
            with self.subTest(n=n):
                self.assertEqual(nat(app(fact_term(), num(n))), expected)

    def test_z_is_a_value_before_application(self):
        # Z g reduces to a lambda without unfolding the recursion forever.
        result = reduce_term(fact_term(), 100)
        self.assertTrue(result.completed)
        self.assertIsInstance(result.term, Lam)

    def test_y_diverges_under_call_by_value(self):
        # Y = lam g. (lam x. g (x x)) (lam x. g (x x)) unfolds forever.
        half = lam("x", app(Var("g"), app(Var("x"), Var("x"))))
        Y = lam("g", app(half, half))
        result = reduce_term(app(Y, lam("f", "n", Var("n"))), 1000)
        self.assertEqual(result.status, "exhausted")


class ObserverTests(unittest.TestCase):
    def test_alpha_renamed_literals(self):
        two = lam("succ", "zero", app(Var("succ"), app(Var("succ"), Var("zero"))))
        self.assertEqual(observe(two, "nat", 100).value, 2)
        yes = lam("a", "b", Var("a"))
        self.assertIs(observe(yes, "bool", 100).value, True)

    def test_computed_values_with_redexes_under_lambdas(self):
        # ADD 2 3 evaluates to lam s. lam z. 2 s (3 s z), not a normal form.
        value = reduce_term(app(ADD, num(2), num(3)), 100).term
        self.assertFalse(alpha_equiv(value, num(5)))
        self.assertEqual(observe(value, "nat", 100).value, 5)

    def test_zero_under_both_kinds(self):
        self.assertEqual(observe(num(0), "nat", 10).value, 0)
        self.assertIs(observe(num(0), "bool", 10).value, False)

    def test_malformed(self):
        # Not every invalid untyped term is detectable: lam x. x is the
        # eta-reduced numeral one, and observing it as "nat" yields 1.
        self.assertEqual(observe(lam("x", Var("x")), "nat", 100).value, 1)
        for value, kind in [(lam("x", "y", "z", Var("x")), "nat"),
                            (num(2), "bool"), (num(1), "bool"),
                            (lam("x", "y", "z", Var("x")), "bool"),
                            (lam("s", "z", Var("s")), "nat")]:
            with self.subTest(value=term_print(value), kind=kind):
                self.assertEqual(observe(value, kind, 100).status, MALFORMED)

    def test_observation_budget_exhausted(self):
        self.assertEqual(observe(num(5), "nat", 2).status, EXHAUSTED)
        obs = observe(num(5), "nat", 100)
        self.assertEqual((obs.status, obs.value), (DECODED, 5))
        # A value that diverges when observed.
        omega_half = lam("x", app(Var("x"), Var("x")))
        bad = lam("s", "z", app(omega_half, omega_half))
        self.assertEqual(observe(bad, "nat", 50).status, EXHAUSTED)

    def test_steps_reported(self):
        # NUM(n) STEP BASE: 2 steps to apply the numeral, then n STEP calls.
        self.assertEqual(observe(num(3), "nat", 100).steps, 5)
        self.assertEqual(observe(TRUE, "bool", 100).steps, 2)

    def test_rejects_non_values(self):
        with self.assertRaises(TypeError):
            observe(App(I, I), "nat", 10)
        with self.assertRaises(ValueError):
            observe(I, "string", 10)

    def test_contexts_closed(self):
        for term in (STEP, BASE, MARK_T, MARK_F):
            self.assertEqual(free_vars(term), frozenset())
        self.assertFalse(alpha_equiv(MARK_T, MARK_F))


if __name__ == "__main__":
    unittest.main()
