"""unittest suite for lambda1_visitors.py.

Run from the assignment directory:
    python3.12 -m unittest -v MySolution/test_unittest_suite.py
"""
import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import lambda1_vp as m  # noqa: E402
import lambda1_visitors as lv  # noqa: E402
import shared_cases as c  # noqa: E402


def fv_property_holds(e, x, r, result):
    """FV(e[x := r]) = (FV(e) - {x}) | FV(r) when x is free in e."""
    fv_e = m.d0exp_fvset(e)
    if x in fv_e:
        return m.d0exp_fvset(result) == (fv_e - {x}) | m.d0exp_fvset(r)
    return m.d0exp_fvset(result) == fv_e


class PrettyPrintTests(unittest.TestCase):
    def test_cases(self):
        for name, expr, expected in c.PRETTY_CASES:
            with self.subTest(name):
                self.assertEqual(lv.d0exp_pretty(expr), expected)

    def test_every_constructor_covered(self):
        covered = {type(expr) for _, expr, _ in c.PRETTY_CASES}
        expected = {m.D0Eint, m.D0Ebtf, m.D0Eop1, m.D0Eop2, m.D0Evar,
                    m.D0Elam, m.D0Efix, m.D0Eapp, m.D0Eif0, m.D0Elet,
                    m.D0Epair, m.D0Epfst, m.D0Epsnd}
        self.assertEqual(covered, expected)

    def test_single_line_without_surrounding_whitespace(self):
        for name, expr, _ in c.PRETTY_CASES:
            with self.subTest(name):
                out = lv.d0exp_pretty(expr)
                self.assertNotIn("\n", out)
                self.assertEqual(out, out.strip())

    def test_visitor_used_directly(self):
        visitor = lv.PrettyPrintVisitor()
        self.assertIsInstance(visitor, m.D0ExpVisitor)
        self.assertEqual(m.D0Evar("x").accept(visitor), "x")

    def test_unsupported_expression(self):
        with self.assertRaises(TypeError):
            lv.d0exp_pretty(m.D0E000())


class SubstitutionTests(unittest.TestCase):
    def check(self, cases):
        for name, e, x, r, expected in cases:
            with self.subTest(name):
                result = lv.d0exp_substitute(e, x, r)
                self.assertEqual(lv.d0exp_pretty(result), lv.d0exp_pretty(expected))
                self.assertEqual(result, expected)

    def test_constructors(self):
        self.check(c.CONSTRUCTOR_CASES)

    def test_shadowing(self):
        self.check(c.SHADOWING_CASES)

    def test_capture_avoidance(self):
        self.check(c.CAPTURE_CASES)

    def test_renaming_and_fresh_names(self):
        self.check(c.RENAMING_CASES)

    def test_let_initializer_vs_body(self):
        self.check(c.LET_CASES)

    def test_results_up_to_alpha_equivalence(self):
        for name, e, x, r, expected in c.ALPHA_CASES:
            with self.subTest(name):
                result = lv.d0exp_substitute(e, x, r)
                self.assertTrue(lv.d0exp_alpha_equiv(result, expected))

    def test_capture_would_be_wrong(self):
        e = c.lam("y", c.add(c.V("x"), c.V("y")))
        captured = c.lam("y", c.add(c.V("y"), c.V("y")))
        result = lv.d0exp_substitute(e, "x", c.V("y"))
        self.assertFalse(lv.d0exp_alpha_equiv(result, captured))

    def test_every_constructor_covered(self):
        covered = {type(e) for _, e, _, _, _ in c.CONSTRUCTOR_CASES}
        self.assertEqual(len(covered), 13)

    def test_free_variable_property(self):
        for name, e, x, r, _ in c.SUBST_CASES + c.ALPHA_CASES:
            with self.subTest(name):
                result = lv.d0exp_substitute(e, x, r)
                self.assertTrue(fv_property_holds(e, x, r, result))

    def test_target_not_free_gives_alpha_equivalent_result(self):
        for name, e, x, r, _ in c.SUBST_CASES:
            if x in m.d0exp_fvset(e):
                continue
            with self.subTest(name):
                result = lv.d0exp_substitute(e, x, r)
                self.assertTrue(lv.d0exp_alpha_equiv(result, e))

    def test_inputs_not_mutated(self):
        for name, e, x, r, _ in c.SUBST_CASES:
            with self.subTest(name):
                e_before, r_before = copy.deepcopy(e), copy.deepcopy(r)
                lv.d0exp_substitute(e, x, r)
                self.assertEqual(e, e_before)
                self.assertEqual(r, r_before)

    def test_deterministic(self):
        for name, e, x, r, _ in c.SUBST_CASES:
            with self.subTest(name):
                self.assertEqual(lv.d0exp_substitute(e, x, r),
                                 lv.d0exp_substitute(e, x, r))

    def test_unsupported_expression(self):
        with self.assertRaises(TypeError):
            lv.d0exp_substitute(m.D0E000(), "x", c.I(1))


class NoEvaluationTests(unittest.TestCase):
    def setUp(self):
        # Make any accidental evaluation fail loudly.
        self.saved = {}
        for attr in dir(m.EvaluateVisitor):
            if attr.startswith("visit_"):
                self.saved[attr] = getattr(m.EvaluateVisitor, attr)
                setattr(m.EvaluateVisitor, attr, self.fail_on_evaluate)

    def tearDown(self):
        for attr, method in self.saved.items():
            setattr(m.EvaluateVisitor, attr, method)

    @staticmethod
    def fail_on_evaluate(*args):
        raise AssertionError("expression was evaluated")

    def test_printing_and_substitution_do_not_evaluate(self):
        for e in c.UNEVALUABLE:
            with self.subTest(lv.d0exp_pretty(e)):
                result = lv.d0exp_substitute(e, "x", c.op2("/", c.I(1), c.I(0)))
                self.assertIsInstance(result, type(e))
                lv.d0exp_pretty(result)

    def test_evaluation_hook_works(self):
        with self.assertRaises(AssertionError):
            m.d0exp_evaluate(c.I(1))


class AlphaEquivalenceTests(unittest.TestCase):
    def test_cases(self):
        for name, a, b, equivalent in c.ALPHA_EQUIV_CASES:
            with self.subTest(name):
                self.assertEqual(lv.d0exp_alpha_equiv(a, b), equivalent)

    def test_debruijn_form(self):
        term = c.lam("x", c.lam("y", c.app(c.V("x"), c.V("z"))))
        self.assertEqual(lv.d0exp_debruijn(term),
                         ("lam", ("lam", ("app", ("bound", 1), ("free", "z")))))


if __name__ == "__main__":
    unittest.main()
