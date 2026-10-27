"""unittest suite for the source path of the shared evaluator.

Run from assigns/06:
    python3.12 -m unittest -v MySolution/test_source_eval.py
"""
import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evaluator  # noqa: E402
from evaluator import (  # noqa: E402
    evaluate, evaluate_source, reduce_term, source_result,
    Reduction, OpenTermError, SourceError, VALUE, EXHAUSTED,
)
from source_ast import (  # noqa: E402
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)
from target import Var, Lam, App  # noqa: E402

N, T, F = D0Eint, D0Ebtf(True), D0Ebtf(False)
x, y, n = D0Evar("x"), D0Evar("y"), D0Evar("n")


def op(name, a, b):
    return D0Eop2(name, a, b)


LOOP = D0Eapp(D0Efix("loop", "x", D0Eapp(D0Evar("loop"), x)), N(0))
FACT = D0Efix("fact", "n",
              D0Eif0(op("==", n, N(0)), N(1),
                     op("*", n, D0Eapp(D0Evar("fact"), op("-", n, N(1))))))
FIB = D0Efix("fib", "n",
             D0Eif0(op("<", n, N(2)), n,
                    op("+", D0Eapp(D0Evar("fib"), op("-", n, N(1))),
                       D0Eapp(D0Evar("fib"), op("-", n, N(2))))))
BUDGET = 1000


def run(dexp, budget=None):
    result = evaluate_source(dexp, budget)
    return source_result(result.term) if result.completed else EXHAUSTED


class DemoTests(unittest.TestCase):
    """The required demonstrations, source side."""

    CASES = [
        ("2 + 3 * 4", op("+", N(2), op("*", N(3), N(4))), 14),
        ("2 - 5", op("-", N(2), N(5)), 0),
        ("if 2 <= 3 then 7 else 9", D0Eif0(op("<=", N(2), N(3)), N(7), N(9)), 7),
        ("let x = 3 in (lam y. x + y) 4",
         D0Elet("x", N(3), D0Eapp(D0Elam("y", op("+", x, y)), N(4))), 7),
        ("fst (pair 2 true)", D0Epfst(D0Epair(N(2), T)), 2),
        ("snd (pair 2 true)", D0Epsnd(D0Epair(N(2), T)), True),
        ("(lam f. f 3) (lam x. x + 1)",
         D0Eapp(D0Elam("f", D0Eapp(D0Evar("f"), N(3))), D0Elam("x", op("+", x, N(1)))), 4),
        ("true and false", op("and", T, F), False),
        ("false or true", op("or", F, T), True),
        ("if true then 1 else LOOP", D0Eif0(T, N(1), LOOP), 1),
        ("(lam x. 0) LOOP", D0Eapp(D0Elam("x", N(0)), LOOP), EXHAUSTED),
        ("fact 4", D0Eapp(FACT, N(4)), 24),
        ("fib 5", D0Eapp(FIB, N(5)), 5),
        ("LOOP", LOOP, EXHAUSTED),
    ]

    def test_demos(self):
        for label, dexp, expected in self.CASES:
            with self.subTest(label):
                self.assertEqual(run(dexp, BUDGET), expected)


class OperatorTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(run(op("+", N(0), N(0))), 0)
        self.assertEqual(run(op("-", N(5), N(2))), 3)
        self.assertEqual(run(op("-", N(0), N(1))), 0)   # truncated
        self.assertEqual(run(op("-", N(3), N(3))), 0)
        self.assertEqual(run(op("*", N(6), N(0))), 0)
        self.assertEqual(run(op("*", N(6), N(7))), 42)

    def test_comparisons_both_outcomes(self):
        cases = {"<": (2, 3, 3, 2), "<=": (3, 3, 4, 3), ">": (3, 2, 2, 3),
                 ">=": (3, 3, 3, 4), "==": (4, 4, 4, 5), "!=": (4, 5, 4, 4)}
        for name, (a, b, c, d) in cases.items():
            with self.subTest(name):
                self.assertIs(run(op(name, N(a), N(b))), True)
                self.assertIs(run(op(name, N(c), N(d))), False)

    def test_boolean_truth_tables(self):
        for a in (True, False):
            self.assertIs(run(D0Eop1("not", D0Ebtf(a))), not a)
            for b in (True, False):
                with self.subTest(a=a, b=b):
                    self.assertIs(run(op("and", D0Ebtf(a), D0Ebtf(b))), a and b)
                    self.assertIs(run(op("or", D0Ebtf(a), D0Ebtf(b))), a or b)

    def test_literals(self):
        self.assertEqual(run(N(0)), 0)
        self.assertIs(run(T), True)
        self.assertIs(run(F), False)


class StrategyTests(unittest.TestCase):
    def test_short_circuit_skips_divergence(self):
        self.assertIs(run(op("and", F, LOOP), BUDGET), False)
        self.assertIs(run(op("or", T, LOOP), BUDGET), True)

    def test_selected_operand_diverges(self):
        self.assertEqual(run(op("and", T, LOOP), BUDGET), EXHAUSTED)
        self.assertEqual(run(op("or", F, LOOP), BUDGET), EXHAUSTED)

    def test_unselected_branch_skipped_selected_runs(self):
        self.assertEqual(run(D0Eif0(F, LOOP, N(2)), BUDGET), 2)
        self.assertEqual(run(D0Eif0(T, LOOP, N(2)), BUDGET), EXHAUSTED)

    def test_call_by_value_divergence(self):
        # ACC-08: unused values are still computed.
        for label, dexp in [
            ("let x = LOOP in 2", D0Elet("x", LOOP, N(2))),
            ("fst (pair 2 LOOP)", D0Epfst(D0Epair(N(2), LOOP))),
            ("snd (pair LOOP true)", D0Epsnd(D0Epair(LOOP, T))),
            ("(lam x. 0) LOOP", D0Eapp(D0Elam("x", N(0)), LOOP)),
            ("LOOP + 1", op("+", LOOP, N(1))),
            ("1 + LOOP", op("+", N(1), LOOP)),
        ]:
            with self.subTest(label):
                result = evaluate_source(dexp, BUDGET)
                self.assertEqual((result.status, result.steps), (EXHAUSTED, BUDGET))

    def test_left_to_right_operands(self):
        # Both operands fail; the left's error is reported, so it ran first.
        with self.assertRaisesRegex(SourceError, "^fst"):
            evaluate_source(op("+", D0Epfst(N(1)), D0Epsnd(N(1))))
        # The left operand diverges, so the right's error is never reached.
        self.assertEqual(run(op("+", LOOP, D0Epsnd(N(1))), BUDGET), EXHAUSTED)
        # Operands are evaluated before the operator checks their types.
        self.assertEqual(run(op("+", T, LOOP), BUDGET), EXHAUSTED)

    def test_value_zero_steps(self):
        lam = D0Elam("x", D0Eapp(D0Elam("y", y), x))
        self.assertEqual(evaluate_source(lam, 0), Reduction(VALUE, lam, 0))
        self.assertEqual(evaluate_source(op("+", N(1), N(2)), 0).steps, 0)

    def test_budget_counts_applications(self):
        app = D0Eapp(D0Elam("x", x), N(1))
        self.assertEqual(evaluate_source(app, 0).status, EXHAUSTED)
        self.assertEqual(evaluate_source(app, 1), Reduction(VALUE, N(1), 1))

    def test_unbounded_by_default(self):
        self.assertEqual(run(D0Eapp(FACT, N(6))), 720)

    def test_exhausted_residual(self):
        result = evaluate_source(op("+", N(1), D0Eapp(D0Elam("x", x), N(2))), 0)
        self.assertEqual(result.term, op("+", N(1), D0Eapp(D0Elam("x", x), N(2))))


class ScopeTests(unittest.TestCase):
    def test_let_initializer_scope(self):
        # let x = 1 in let x = x + 1 in x  ==>  2
        self.assertEqual(run(D0Elet("x", N(1), D0Elet("x", op("+", x, N(1)), x))), 2)

    def test_shadowing(self):
        # (lam x. (lam x. x) 5) 3  ==>  5
        self.assertEqual(run(D0Eapp(D0Elam("x", D0Eapp(D0Elam("x", x), N(5))), N(3))), 5)

    def test_closure_captures_definition_scope(self):
        # let x = 1 in let f = lam y. x + y in let x = 10 in f 1  ==>  2
        dexp = D0Elet("x", N(1), D0Elet("f", D0Elam("y", op("+", x, y)),
                      D0Elet("x", N(10), D0Eapp(D0Evar("f"), N(1)))))
        self.assertEqual(run(dexp), 2)

    def test_coincident_fix_binders(self):
        # ACC-07: (fix f(f). f) 3  ==>  3
        self.assertEqual(run(D0Eapp(D0Efix("f", "f", D0Evar("f")), N(3))), 3)

    def test_fix_uses_both_binders(self):
        # (fix f(x). if x == 0 then 0 else f (x - 1)) 3  ==>  0
        dexp = D0Eapp(D0Efix("f", "x", D0Eif0(op("==", x, N(0)), N(0),
                      D0Eapp(D0Evar("f"), op("-", x, N(1))))), N(3))
        self.assertEqual(run(dexp, BUDGET), 0)

    def test_function_result(self):
        result = evaluate_source(D0Eapp(D0Elam("x", D0Elam("y", x)), N(1)))
        self.assertEqual(result.term, D0Elam("y", N(1)))

    def test_nested_pair(self):
        dexp = D0Epair(D0Epair(N(2), T), op("+", N(1), N(2)))
        self.assertEqual(run(dexp), ((2, True), 3))


class ErrorTests(unittest.TestCase):
    def test_open_program_rejected(self):
        with self.assertRaises(OpenTermError):
            evaluate_source(op("+", x, N(1)))

    def test_runtime_errors(self):
        for label, dexp in [
            ("negative literal", N(-1)),
            ("division", op("/", N(6), N(2))),
            ("unsupported unary", D0Eop1("-1", N(2))),
            ("if on a number", D0Eif0(N(0), N(1), N(2))),
            ("add a boolean", op("+", N(1), T)),
            ("not a number", D0Eop1("not", N(1))),
            ("apply a number", D0Eapp(N(1), N(2))),
            ("project a number", D0Epfst(N(1))),
            ("and with a number", op("and", T, N(1))),
        ]:
            with self.subTest(label):
                with self.assertRaises(SourceError):
                    evaluate_source(dexp)

    def test_unselected_error_not_reached(self):
        # The evaluator is lazy about errors in unselected branches; rejecting
        # them statically is the compiler's job.
        self.assertEqual(run(D0Eif0(T, N(1), op("/", N(1), N(0)))), 1)

    def test_bad_inputs(self):
        with self.assertRaises(TypeError):
            evaluate("2 + 3")
        with self.assertRaises(TypeError):
            evaluate(App(Lam("x", Var("x")), N(1)))        # mixed syntax
        with self.assertRaises(TypeError):
            reduce_term(N(1), 10)
        with self.assertRaises(ValueError):
            reduce_term(Lam("x", Var("x")), None)


class SharedEvaluatorTests(unittest.TestCase):
    def test_input_unchanged_and_deterministic(self):
        dexp = D0Eapp(FACT, N(4))
        snapshot = copy.deepcopy(dexp)
        self.assertEqual(evaluate(dexp, BUDGET), evaluate(dexp, BUDGET))
        self.assertEqual(dexp, snapshot)

    def test_target_path_uses_no_source_operations(self):
        # Running a target term must never touch source substitution or ops.
        fail = mock.Mock(side_effect=AssertionError("source operation used"))
        I = Lam("x", Var("x"))
        with mock.patch.object(evaluator, "d0exp_substitute", fail), \
             mock.patch.object(evaluator, "_op1", fail), \
             mock.patch.object(evaluator, "_op2", fail):
            self.assertEqual(evaluate(App(App(I, I), App(I, I)), 10),
                             Reduction(VALUE, I, 3))


if __name__ == "__main__":
    unittest.main()
