"""unittest suite for target.py: printer, free variables, substitution.

Run from assigns/06:
    python3.12 -m unittest -v MySolution/test_target.py
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from target import (  # noqa: E402
    Var, Lam, App, term_print, free_vars, all_names, is_pure,
    substitute, alpha_equiv,
)

x, y, z = Var("x"), Var("y"), Var("z")
I = Lam("x", x)


class PrintTests(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(term_print(x), "x")
        self.assertEqual(term_print(Lam("x", y)), "(lam x. y)")
        self.assertEqual(term_print(App(x, y)), "(x y)")

    def test_nested(self):
        term = Lam("s", Lam("z", App(Var("s"), App(Var("s"), z))))
        self.assertEqual(term_print(term), "(lam s. (lam z. (s (s z))))")
        self.assertEqual(term_print(App(App(I, I), App(I, I))),
                         "(((lam x. x) (lam x. x)) ((lam x. x) (lam x. x)))")


class NameTests(unittest.TestCase):
    def test_free_vars(self):
        self.assertEqual(free_vars(x), {"x"})
        self.assertEqual(free_vars(I), frozenset())
        self.assertEqual(free_vars(Lam("x", App(x, y))), {"y"})
        self.assertEqual(free_vars(App(Lam("x", x), x)), {"x"})

    def test_all_names(self):
        self.assertEqual(all_names(Lam("x", App(y, z))), {"x", "y", "z"})

    def test_is_pure(self):
        self.assertTrue(is_pure(Lam("x", App(x, y))))
        self.assertFalse(is_pure(Lam("x", 3)))
        self.assertFalse(is_pure("x"))


class SubstitutionTests(unittest.TestCase):
    def test_variable_hit_and_miss(self):
        self.assertEqual(substitute(x, "x", I), I)
        self.assertEqual(substitute(y, "x", I), y)

    def test_capture_hazard(self):
        # ACC-01: [x := y](lam y. x) must be lam fresh. y, with y still free.
        result = substitute(Lam("y", x), "x", y)
        self.assertTrue(alpha_equiv(result, Lam("w", y)))
        self.assertNotEqual(result.param, "y")
        self.assertEqual(free_vars(result), {"y"})

    def test_shadowing_binder_stops_substitution(self):
        term = Lam("x", x)
        self.assertEqual(substitute(term, "x", y), term)

    def test_inner_shadowing(self):
        # [x := z](x (lam x. x)) = z (lam x. x)
        term = App(x, Lam("x", x))
        self.assertEqual(substitute(term, "x", z), App(z, Lam("x", x)))

    def test_fresh_name_avoids_existing_names(self):
        # y_1 already occurs, so the renamed binder must skip it.
        term = Lam("y", App(x, Var("y_1")))
        result = substitute(term, "x", y)
        self.assertNotIn(result.param, {"x", "y", "y_1"})
        self.assertEqual(free_vars(result), {"y", "y_1"})
        self.assertTrue(alpha_equiv(result, Lam("w", App(y, Var("y_1")))))

    def test_deterministic(self):
        term = Lam("y", Lam("z", App(x, App(y, z))))
        r = App(y, z)
        self.assertEqual(substitute(term, "x", r), substitute(term, "x", r))

    def test_inputs_unchanged(self):
        term = Lam("y", App(x, Lam("x", x)))
        r = App(y, Lam("q", Var("q")))
        before_t, before_r = copy.deepcopy(term), copy.deepcopy(r)
        substitute(term, "x", r)
        self.assertEqual(term, before_t)
        self.assertEqual(r, before_r)

    def test_fv_property(self):
        # FV(e[x := r]) = (FV(e) - {x}) | FV(r) when x is free in e.
        cases = [
            (Lam("y", App(x, y)), "x", App(y, z)),
            (App(x, Lam("x", x)), "x", y),
            (Lam("z", Lam("y", App(App(x, y), z))), "x", App(y, z)),
        ]
        for term, v, r in cases:
            with self.subTest(term=term_print(term)):
                result = substitute(term, v, r)
                self.assertEqual(free_vars(result),
                                 (free_vars(term) - {v}) | free_vars(r))


class AlphaTests(unittest.TestCase):
    def test_equiv(self):
        self.assertTrue(alpha_equiv(Lam("x", x), Lam("y", y)))
        self.assertTrue(alpha_equiv(Lam("x", Lam("y", x)), Lam("a", Lam("b", Var("a")))))

    def test_not_equiv(self):
        self.assertFalse(alpha_equiv(Lam("x", Lam("y", x)), Lam("x", Lam("y", y))))
        self.assertFalse(alpha_equiv(Lam("x", y), Lam("x", z)))


if __name__ == "__main__":
    unittest.main()
