"""Tests for pairs and projections in the extended interpreter.

Run with: python3 TEST/test02_lambda0.py
Requires Python 3.12 or later, like lambda0.py.
"""

import sys
import unittest
from pathlib import Path

# Allow this file to run directly from any working directory, and make sure
# it imports MySolution/lambda0.py rather than the starter file.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lambda0 import (
    T0Mint, T0Mbtf, T0Mstr, T0Mvar, T0Mlam, T0Mfix, T0Mapp, T0Mif0, T0Mop1, T0Mop2,
    T0Mpair, T0Mpfst, T0Mpsnd,
    t0erm_size, t0erm_fvset, t0erm_subst0, t0erm_cbv_evaluate0,
)

x, y, z = T0Mvar("x"), T0Mvar("y"), T0Mvar("z")
one, two, three = T0Mint(1), T0Mint(2), T0Mint(3)
DIV_BY_ZERO = T0Mop2("/", one, T0Mint(0))
BAD_NEGATION = T0Mop1("-", T0Mstr("bad"))


class TestSize(unittest.TestCase):
    def test_assignment_example(self):
        self.assertEqual(t0erm_size(T0Mpair(one, two)), 3)

    def test_pair_and_projections(self):
        for term, expected in [
            (T0Mpfst(x), 2),
            (T0Mpsnd(x), 2),
            (T0Mpair(x, y), 3),
            (T0Mpfst(T0Mpair(one, two)), 4),
            (T0Mpsnd(T0Mpair(one, two)), 4),
        ]:
            with self.subTest(term=term):
                self.assertEqual(t0erm_size(term), expected)

    def test_nested(self):
        # Pair of pairs: 1 + (1+1+1) + (1+1+1) = 7.
        self.assertEqual(t0erm_size(T0Mpair(T0Mpair(one, two), T0Mpair(x, y))), 7)
        # Pair inside a lambda inside an application: app(lam x.(x, x+1), 2)
        term = T0Mapp(T0Mlam("x", T0Mpair(x, T0Mop2("+", x, one))), two)
        self.assertEqual(t0erm_size(term), 1 + (1 + (1 + 1 + (1 + 1 + 1))) + 1)
        # Projections wrapped in a conditional and unary operator.
        term = T0Mif0(T0Mbtf(True), T0Mop1("-", T0Mpfst(T0Mpair(one, two))), T0Mpsnd(x))
        self.assertEqual(t0erm_size(term), 1 + 1 + (1 + 4) + 2)


class TestFreeVariables(unittest.TestCase):
    def test_assignment_example(self):
        self.assertEqual(t0erm_fvset(T0Mpfst(T0Mpair(x, y))), frozenset({"x", "y"}))

    def test_closed_terms(self):
        for term in [T0Mpair(one, two), T0Mpfst(T0Mpair(one, T0Mbtf(True))),
                     T0Mpsnd(T0Mpair(T0Mstr("a"), two))]:
            with self.subTest(term=term):
                self.assertEqual(t0erm_fvset(term), frozenset())

    def test_both_components_and_operand(self):
        self.assertEqual(t0erm_fvset(T0Mpair(x, y)), frozenset({"x", "y"}))
        self.assertEqual(t0erm_fvset(T0Mpair(x, x)), frozenset({"x"}))
        self.assertEqual(t0erm_fvset(T0Mpfst(y)), frozenset({"y"}))
        self.assertEqual(t0erm_fvset(T0Mpsnd(T0Mpair(x, T0Mpfst(z)))), frozenset({"x", "z"}))

    def test_projections_bind_nothing(self):
        # A pair under a lambda: the lambda removes its variable, the pair adds none.
        self.assertEqual(t0erm_fvset(T0Mlam("x", T0Mpair(x, y))), frozenset({"y"}))
        self.assertEqual(t0erm_fvset(T0Mlam("x", T0Mpair(x, x))), frozenset())
        # Under fix, both the function name and the parameter are bound.
        term = T0Mfix("f", "x", T0Mpair(T0Mapp(T0Mvar("f"), T0Mpfst(x)), y))
        self.assertEqual(t0erm_fvset(term), frozenset({"y"}))

    def test_nested_pairs(self):
        term = T0Mpair(T0Mpair(x, T0Mlam("y", y)), T0Mpsnd(T0Mpair(z, T0Mint(0))))
        self.assertEqual(t0erm_fvset(term), frozenset({"x", "z"}))


class TestSubstitution(unittest.TestCase):
    def test_both_components(self):
        self.assertEqual(t0erm_subst0(T0Mpair(x, x), "x", one), T0Mpair(one, one))
        self.assertEqual(t0erm_subst0(T0Mpair(x, y), "x", one), T0Mpair(one, y))
        self.assertEqual(t0erm_subst0(T0Mpair(x, y), "y", one), T0Mpair(x, one))
        # Nothing to do when the variable is absent.
        self.assertEqual(t0erm_subst0(T0Mpair(x, y), "z", one), T0Mpair(x, y))

    def test_projection_operands(self):
        self.assertEqual(t0erm_subst0(T0Mpfst(x), "x", T0Mpair(one, two)),
                         T0Mpfst(T0Mpair(one, two)))
        self.assertEqual(t0erm_subst0(T0Mpsnd(T0Mpair(x, y)), "y", two),
                         T0Mpsnd(T0Mpair(x, two)))

    def test_constructor_is_preserved(self):
        for make in (T0Mpfst, T0Mpsnd):
            with self.subTest(make=make.__name__):
                result = t0erm_subst0(make(x), "x", one)
                self.assertIsInstance(result, make)
                self.assertEqual(result, make(one))

    def test_nested(self):
        term = T0Mpair(T0Mpfst(x), T0Mpair(y, T0Mpsnd(x)))
        self.assertEqual(t0erm_subst0(term, "x", one),
                         T0Mpair(T0Mpfst(one), T0Mpair(y, T0Mpsnd(one))))

    def test_under_lambda_binder(self):
        # x is free in the pair: substituted.
        term = T0Mlam("y", T0Mpair(x, y))
        self.assertEqual(t0erm_subst0(term, "x", one), T0Mlam("y", T0Mpair(one, y)))
        # x is bound by the lambda: untouched.
        term = T0Mlam("x", T0Mpair(x, y))
        self.assertEqual(t0erm_subst0(term, "x", one), term)

    def test_under_fix_binder(self):
        body = T0Mpair(T0Mapp(T0Mvar("f"), T0Mpfst(x)), y)
        # y is free: substituted inside the pair.
        self.assertEqual(t0erm_subst0(T0Mfix("f", "x", body), "y", two),
                         T0Mfix("f", "x", T0Mpair(T0Mapp(T0Mvar("f"), T0Mpfst(x)), two)))
        # f and x are bound by the fix: untouched.
        for bound in ("f", "x"):
            with self.subTest(bound=bound):
                term = T0Mfix("f", "x", body)
                self.assertEqual(t0erm_subst0(term, bound, two), term)

    def test_pair_as_replacement(self):
        # A closed pair may itself be substituted in.
        pair = T0Mpair(one, T0Mlam("z", z))
        self.assertEqual(t0erm_subst0(T0Mop2("+", T0Mpfst(x), two), "x", pair),
                         T0Mop2("+", T0Mpfst(pair), two))


class TestEvaluation(unittest.TestCase):
    def test_assignment_example(self):
        term = T0Mpsnd(T0Mpair(one, T0Mop2("+", two, three)))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(5))

    def test_pair_of_values_is_a_value(self):
        for pair in [T0Mpair(one, two), T0Mpair(T0Mbtf(True), T0Mstr("s")),
                     T0Mpair(T0Mlam("x", x), T0Mpair(one, two))]:
            with self.subTest(pair=pair):
                self.assertEqual(t0erm_cbv_evaluate0(pair), pair)

    def test_components_are_evaluated(self):
        term = T0Mpair(T0Mop2("*", two, three), T0Mop2("<", one, two))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mpair(T0Mint(6), T0Mbtf(True)))

    def test_both_projections(self):
        pair = T0Mpair(T0Mop2("+", one, two), T0Mop2("-", one, two))
        self.assertEqual(t0erm_cbv_evaluate0(T0Mpfst(pair)), T0Mint(3))
        self.assertEqual(t0erm_cbv_evaluate0(T0Mpsnd(pair)), T0Mint(-1))

    def test_nested_pairs_and_mixed_kinds(self):
        # ((1, true), ("s", lam x. x)) -- values of every kind in one nest.
        inner_l = T0Mpair(one, T0Mbtf(True))
        inner_r = T0Mpair(T0Mstr("s"), T0Mlam("x", x))
        pair = T0Mpair(inner_l, inner_r)
        self.assertEqual(t0erm_cbv_evaluate0(pair), pair)
        self.assertEqual(t0erm_cbv_evaluate0(T0Mpsnd(T0Mpfst(pair))), T0Mbtf(True))
        self.assertEqual(t0erm_cbv_evaluate0(T0Mpfst(T0Mpsnd(pair))), T0Mstr("s"))
        # The lambda inside the pair is still usable.
        term = T0Mapp(T0Mpsnd(T0Mpsnd(pair)), T0Mint(7))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(7))

    def test_projection_of_computed_pair(self):
        # The pair comes out of a conditional, not a literal.
        term = T0Mpfst(T0Mif0(T0Mbtf(False), T0Mpair(one, two), T0Mpair(three, one)))
        self.assertEqual(t0erm_cbv_evaluate0(term), three)

    def test_function_taking_a_pair(self):
        # (lam p. fst p + snd p) (2 * 3, 1)  ==  7
        add = T0Mlam("p", T0Mop2("+", T0Mpfst(T0Mvar("p")), T0Mpsnd(T0Mvar("p"))))
        term = T0Mapp(add, T0Mpair(T0Mop2("*", two, three), one))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(7))

    def test_function_returning_a_pair(self):
        # (lam x. (x, x + 1)) 2  ==  (2, 3): the argument is substituted into both components.
        dup = T0Mlam("x", T0Mpair(x, T0Mop2("+", x, one)))
        self.assertEqual(t0erm_cbv_evaluate0(T0Mapp(dup, two)), T0Mpair(two, three))

    def test_swap(self):
        swap = T0Mlam("p", T0Mpair(T0Mpsnd(T0Mvar("p")), T0Mpfst(T0Mvar("p"))))
        term = T0Mapp(swap, T0Mpair(one, T0Mstr("b")))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mpair(T0Mstr("b"), one))

    def test_recursive_function_over_pairs(self):
        # sum (n, acc) = if n == 0 then acc else sum (n - 1, acc + n)
        p = T0Mvar("p")
        n, acc = T0Mpfst(p), T0Mpsnd(p)
        total = T0Mfix("sum", "p", T0Mif0(
            T0Mop2("==", n, T0Mint(0)),
            acc,
            T0Mapp(T0Mvar("sum"), T0Mpair(T0Mop2("-", n, one), T0Mop2("+", acc, n))),
        ))
        term = T0Mapp(total, T0Mpair(T0Mint(10), T0Mint(0)))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(55))

    def test_projection_requires_pair(self):
        for value in [one, T0Mbtf(True), T0Mstr("s"), T0Mlam("x", x), T0Mfix("f", "x", x)]:
            for make in (T0Mpfst, T0Mpsnd):
                with self.subTest(value=value, make=make.__name__):
                    with self.assertRaises(TypeError):
                        t0erm_cbv_evaluate0(make(value))

    def test_projection_operand_is_evaluated_first(self):
        # A computed non-pair still raises TypeError, after being evaluated.
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(T0Mpfst(T0Mop2("+", one, two)))
        # ...and an error while evaluating the operand wins over the type error.
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(T0Mpsnd(DIV_BY_ZERO))

    def test_left_component_evaluated_first(self):
        # Left raises ZeroDivisionError before the right's TypeError is reached.
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(T0Mpair(DIV_BY_ZERO, BAD_NEGATION))
        # Swapped, the right operand's error is never reached.
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(T0Mpair(BAD_NEGATION, DIV_BY_ZERO))

    def test_unselected_component_is_evaluated(self):
        # Assignment example: fst (1, 1/0) must raise, not return 1.
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(T0Mpfst(T0Mpair(one, DIV_BY_ZERO)))
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(T0Mpsnd(T0Mpair(DIV_BY_ZERO, one)))

    def test_other_constructs_unchanged(self):
        # A pair as an operand of an integer operator is still a TypeError.
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(T0Mop2("+", T0Mpair(one, two), one))
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(T0Mif0(T0Mpair(T0Mbtf(True), one), one, two))
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(T0Mapp(T0Mpair(one, two), one))


if __name__ == "__main__":
    unittest.main(verbosity=2)
