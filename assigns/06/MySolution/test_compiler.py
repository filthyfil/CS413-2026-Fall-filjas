"""unittest suite for compiler.py: coverage, scope, purity, divergence.

Most tests compile a source AST, execute the target term with the shared
evaluator, observe the result with its expected kind, and compare with an
explicit expected answer. Where useful they also check agreement with the
shared evaluator's source path. Run from assigns/06:
    python3.12 -m unittest -v MySolution/test_compiler.py
"""
import ast
import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluator  # noqa: E402
from compiler import compile_expr, CompileError  # noqa: E402
from church import COMBINATORS  # noqa: E402
from evaluator import evaluate, reduce_term, source_result  # noqa: E402
from observe import observe  # noqa: E402
from source_ast import (  # noqa: E402
    d0exp_fvset,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)
from target import Var, Lam, App, free_vars, is_pure, term_print  # noqa: E402

N, T, F = D0Eint, D0Ebtf(True), D0Ebtf(False)
x, y, n = D0Evar("x"), D0Evar("y"), D0Evar("n")
EXEC, OBS = 200_000, 200_000
DIVERGE_BUDGET = 3_000
EXHAUSTED = "exhausted"


def op(name, a, b):
    return D0Eop2(name, a, b)


def var(name):
    return D0Evar(name)


LOOP = D0Eapp(D0Efix("loop", "x", D0Eapp(var("loop"), x)), N(0))
FACT = D0Efix("fact", "n",
              D0Eif0(op("==", n, N(0)), N(1),
                     op("*", n, D0Eapp(var("fact"), op("-", n, N(1))))))
FIB = D0Efix("fib", "n",
             D0Eif0(op("<", n, N(2)), n,
                    op("+", D0Eapp(var("fib"), op("-", n, N(1))),
                       D0Eapp(var("fib"), op("-", n, N(2))))))


def run(dexp, kind, budget=EXEC):
    """Compile, execute, and observe; return the decoded value or EXHAUSTED."""
    result = reduce_term(compile_expr(dexp), budget)
    if not result.completed:
        return EXHAUSTED
    obs = observe(result.term, kind, OBS)
    assert obs.decoded, f"observation {obs.status}: {obs.detail}"
    return obs.value


def source(dexp, budget=None):
    result = evaluate(dexp, budget)
    return source_result(result.term) if result.completed else EXHAUSTED


class DemoTests(unittest.TestCase):
    CASES = [
        ("2 + 3 * 4", op("+", N(2), op("*", N(3), N(4))), "nat", 14),
        ("2 - 5", op("-", N(2), N(5)), "nat", 0),
        ("if 2 <= 3 then 7 else 9", D0Eif0(op("<=", N(2), N(3)), N(7), N(9)), "nat", 7),
        ("let x = 3 in (lam y. x + y) 4",
         D0Elet("x", N(3), D0Eapp(D0Elam("y", op("+", x, y)), N(4))), "nat", 7),
        ("fst (pair 2 true)", D0Epfst(D0Epair(N(2), T)), "nat", 2),
        ("snd (pair 2 true)", D0Epsnd(D0Epair(N(2), T)), "bool", True),
        ("(lam f. f 3) (lam x. x + 1)",
         D0Eapp(D0Elam("f", D0Eapp(var("f"), N(3))), D0Elam("x", op("+", x, N(1)))),
         "nat", 4),
        ("true and false", op("and", T, F), "bool", False),
        ("false or true", op("or", F, T), "bool", True),
        ("if true then 1 else LOOP", D0Eif0(T, N(1), LOOP), "nat", 1),
        ("fact 4", D0Eapp(FACT, N(4)), "nat", 24),
        ("fib 5", D0Eapp(FIB, N(5)), "nat", 5),
    ]
    DIVERGING = [
        ("(lam x. 0) LOOP", D0Eapp(D0Elam("x", N(0)), LOOP)),
        ("LOOP", LOOP),
    ]

    def test_terminating_demos(self):
        for label, dexp, kind, expected in self.CASES:
            with self.subTest(label):
                self.assertEqual(run(dexp, kind), expected)
                self.assertEqual(source(dexp), expected)

    def test_diverging_demos(self):
        for label, dexp in self.DIVERGING:
            with self.subTest(label):
                result = reduce_term(compile_expr(dexp), DIVERGE_BUDGET)
                self.assertEqual((result.status, result.steps),
                                 (EXHAUSTED, DIVERGE_BUDGET))


class ConstructorTests(unittest.TestCase):
    def test_literals(self):
        self.assertEqual(run(N(0), "nat"), 0)
        self.assertEqual(run(N(9), "nat"), 9)
        self.assertIs(run(T, "bool"), True)
        self.assertIs(run(F, "bool"), False)

    def test_arithmetic(self):
        cases = [("+", 0, 0, 0), ("+", 2, 3, 5), ("-", 5, 2, 3), ("-", 3, 3, 0),
                 ("-", 2, 5, 0), ("-", 0, 1, 0), ("*", 3, 4, 12), ("*", 0, 5, 0)]
        for name, a, b, expected in cases:
            with self.subTest(f"{a} {name} {b}"):
                self.assertEqual(run(op(name, N(a), N(b)), "nat"), expected)

    def test_predecessor_of_zero(self):
        self.assertEqual(run(op("-", N(0), N(1)), "nat"), 0)

    def test_comparisons_both_outcomes(self):
        cases = {"<": [(2, 3, True), (3, 2, False), (3, 3, False)],
                 "<=": [(3, 3, True), (2, 3, True), (4, 3, False)],
                 ">": [(3, 2, True), (2, 3, False), (3, 3, False)],
                 ">=": [(3, 3, True), (4, 3, True), (3, 4, False)],
                 "==": [(4, 4, True), (4, 5, False), (0, 0, True)],
                 "!=": [(4, 5, True), (4, 4, False), (0, 1, True)]}
        for name, rows in cases.items():
            for a, b, expected in rows:
                with self.subTest(f"{a} {name} {b}"):
                    self.assertIs(run(op(name, N(a), N(b)), "bool"), expected)

    def test_boolean_truth_tables(self):
        for a in (True, False):
            self.assertIs(run(D0Eop1("not", D0Ebtf(a)), "bool"), not a)
            for b in (True, False):
                with self.subTest(a=a, b=b):
                    self.assertIs(run(op("and", D0Ebtf(a), D0Ebtf(b)), "bool"), a and b)
                    self.assertIs(run(op("or", D0Ebtf(a), D0Ebtf(b)), "bool"), a or b)

    def test_if_both_branches(self):
        self.assertEqual(run(D0Eif0(T, N(1), N(2)), "nat"), 1)
        self.assertEqual(run(D0Eif0(F, N(1), N(2)), "nat"), 2)

    def test_pairs(self):
        self.assertEqual(run(D0Epair(N(2), T), ("nat", "bool")), (2, True))
        nested = D0Epair(D0Epair(N(2), T), N(3))
        self.assertEqual(run(nested, (("nat", "bool"), "nat")), ((2, True), 3))
        self.assertEqual(run(D0Epsnd(D0Epfst(nested)), "bool"), True)

    def test_lam_and_app(self):
        self.assertEqual(run(D0Eapp(D0Elam("x", op("*", x, x)), N(3)), "nat"), 9)

    def test_function_valued_result_compiles_to_lambda(self):
        result = reduce_term(compile_expr(D0Elam("x", x)), 0)
        self.assertTrue(result.completed)
        self.assertEqual(result.steps, 0)


class ScopeTests(unittest.TestCase):
    def test_nested_lets(self):
        # let x = 1 in let y = x + 1 in let x = y * 10 in x + y  ==>  22
        dexp = D0Elet("x", N(1), D0Elet("y", op("+", x, N(1)),
                      D0Elet("x", op("*", y, N(10)), op("+", x, y))))
        self.assertEqual(run(dexp, "nat"), 22)

    def test_let_initializer_scope(self):
        # let x = 1 in let x = x + 1 in x  ==>  2 (inner initializer sees outer x)
        dexp = D0Elet("x", N(1), D0Elet("x", op("+", x, N(1)), x))
        self.assertEqual(run(dexp, "nat"), 2)

    def test_let_x_equals_x_is_open(self):
        dexp = D0Elet("x", x, x)
        self.assertEqual(free_vars(compile_expr(dexp)), {"x"})
        closed = D0Elet("x", N(4), D0Elet("x", x, x))
        self.assertEqual(run(closed, "nat"), 4)

    def test_nested_lambda_shadowing(self):
        # (lam x. (lam x. x + 1) (x * 2)) 5  ==>  11
        dexp = D0Eapp(D0Elam("x", D0Eapp(D0Elam("x", op("+", x, N(1))),
                                         op("*", x, N(2)))), N(5))
        self.assertEqual(run(dexp, "nat"), 11)

    def test_closure_uses_definition_scope(self):
        dexp = D0Elet("x", N(1), D0Elet("f", D0Elam("y", op("+", x, y)),
                      D0Elet("x", N(10), D0Eapp(var("f"), N(1)))))
        self.assertEqual(run(dexp, "nat"), 2)

    def test_fix_both_binders(self):
        # (fix f(x). if x == 0 then 7 else f (x - 1)) 3  ==>  7
        dexp = D0Eapp(D0Efix("f", "x", D0Eif0(op("==", x, N(0)), N(7),
                      D0Eapp(var("f"), op("-", x, N(1))))), N(3))
        self.assertEqual(run(dexp, "nat"), 7)

    def test_coincident_fix_binders(self):
        # ACC-07: (fix f(f). f) 3  ==>  3; the parameter shadows the name.
        dexp = D0Eapp(D0Efix("f", "f", var("f")), N(3))
        self.assertEqual(run(dexp, "nat"), 3)
        self.assertEqual(source(dexp), 3)

    def test_coincident_fix_body_uses_parameter(self):
        # (fix f(f). f + 1) 4  ==>  5
        dexp = D0Eapp(D0Efix("f", "f", op("+", var("f"), N(1))), N(4))
        self.assertEqual(run(dexp, "nat"), 5)


class NameCollisionTests(unittest.TestCase):
    """Source names that coincide with encoding and compiler names."""

    ENCODING_NAMES = ["s", "z", "t", "f", "x", "a", "b", "p", "m", "n", "g",
                      "v", "w", "q", "u", "u_1", "v_1", "tail", "c"]

    def test_lets_named_like_encodings(self):
        for name in self.ENCODING_NAMES:
            with self.subTest(name):
                # let name = 3 in (lam w. name + w) 4  ==>  7
                dexp = D0Elet(name, N(3),
                              D0Eapp(D0Elam("w" if name != "w" else "k",
                                            op("+", var(name), var("w" if name != "w" else "k"))),
                                     N(4)))
                self.assertEqual(run(dexp, "nat"), 7)

    def test_branches_mentioning_thunk_names(self):
        # let u_1 = 5 in let v_1 = 7 in if c then u_1 else v_1
        for cond, expected in ((T, 5), (F, 7)):
            dexp = D0Elet("u_1", N(5), D0Elet("v_1", N(7),
                          D0Eif0(cond, var("u_1"), var("v_1"))))
            with self.subTest(cond=cond):
                self.assertEqual(run(dexp, "nat"), expected)

    def test_thunk_parameter_avoids_branch_names(self):
        term = compile_expr(D0Eif0(var("c"), var("u_1"), var("u_2")))
        self.assertEqual(free_vars(term), {"c", "u_1", "u_2"})
        # term = ((c (lam p. u_1)) (lam q. u_2)) I
        then_thunk = term.fn.fn.arg
        self.assertNotIn(then_thunk.param, {"u_1", "c"})

    def test_short_circuit_with_free_names(self):
        for dexp in (op("and", var("s"), var("u_1")), op("or", var("t"), var("v_1"))):
            with self.subTest(dexp=dexp.name):
                self.assertEqual(free_vars(compile_expr(dexp)), d0exp_fvset(dexp))

    def test_fix_binders_named_like_z(self):
        # Z's own binders are g, x, v; recursion named with them must still work.
        for fname, param in (("g", "v"), ("x", "g"), ("v", "x")):
            with self.subTest(fname=fname, param=param):
                p, f = var(param), var(fname)
                dexp = D0Eapp(D0Efix(fname, param,
                              D0Eif0(op("==", p, N(0)), N(1),
                                     op("*", N(2), D0Eapp(f, op("-", p, N(1)))))), N(3))
                self.assertEqual(run(dexp, "nat"), 8)

    def test_open_free_names_like_encodings(self):
        # ACC-06: free s, z, t, f, x survive compilation unchanged.
        dexp = op("+", var("s"), D0Eif0(var("t"), var("z"), op("*", var("f"), x)))
        self.assertEqual(free_vars(compile_expr(dexp)), {"s", "z", "t", "f", "x"})


class DivergenceTests(unittest.TestCase):
    def exhausts(self, dexp):
        result = reduce_term(compile_expr(dexp), DIVERGE_BUDGET)
        self.assertEqual(result.status, EXHAUSTED)

    def test_unselected_divergence_skipped(self):
        self.assertEqual(run(D0Eif0(T, N(1), LOOP), "nat"), 1)
        self.assertEqual(run(D0Eif0(F, LOOP, N(2)), "nat"), 2)
        self.assertIs(run(op("and", F, LOOP), "bool"), False)
        self.assertIs(run(op("or", T, LOOP), "bool"), True)

    def test_selected_divergence_exhausts(self):
        self.exhausts(D0Eif0(T, LOOP, N(1)))
        self.exhausts(D0Eif0(F, N(1), LOOP))
        self.exhausts(D0Eif0(LOOP, N(1), N(2)))
        self.exhausts(op("and", T, LOOP))
        self.exhausts(op("or", F, LOOP))
        self.exhausts(op("and", LOOP, F))

    def test_strict_positions_exhaust(self):
        # ACC-08 and item 5: unused values are still computed.
        for label, dexp in [
            ("function argument", D0Eapp(D0Elam("x", N(0)), LOOP)),
            ("let initializer", D0Elet("x", LOOP, N(2))),
            ("pair right", D0Epfst(D0Epair(N(2), LOOP))),
            ("pair left", D0Epsnd(D0Epair(LOOP, T))),
            ("operator left", op("*", LOOP, N(0))),
            ("operator right", op("*", N(0), LOOP)),
            ("not", D0Eop1("not", LOOP)),
        ]:
            with self.subTest(label):
                self.exhausts(dexp)


class RejectionTests(unittest.TestCase):
    def test_rejected_inputs(self):
        for label, dexp, pattern in [
            ("negative literal", N(-3), "negative literal -3"),
            ("division", op("/", N(6), N(2)), "'/'"),
            ("modulo", op("%", N(6), N(2)), "'%'"),
            ("named binary", op("div", N(6), N(2)), "'div'"),
            ("unsupported unary", D0Eop1("-1", N(2)), "'-1'"),
            ("unsupported unary name", D0Eop1("neg", N(2)), "'neg'"),
            ("unselected branch", D0Eif0(T, N(1), op("/", N(1), N(0))), "'/'"),
            ("unselected negative", D0Eif0(F, N(-1), N(0)), "negative literal -1"),
            ("unapplied lambda", D0Elam("x", op("/", x, N(2))), "'/'"),
            ("fix body", D0Efix("f", "x", D0Eop1("+1", x)), "'\\+1'"),
            ("short-circuited operand", op("and", F, op("/", N(1), N(0))), "'/'"),
            ("deep inside a pair", D0Epair(N(1), D0Elet("y", N(-2), y)), "-2"),
            ("bad identifier", D0Elam("1x", N(0)), "invalid identifier"),
        ]:
            with self.subTest(label):
                with self.assertRaisesRegex(CompileError, pattern):
                    compile_expr(dexp)


ALL_FORMS = [
    N(0), N(3), T, F, x, D0Elam("x", op("+", x, y)), D0Eapp(var("f"), x),
    D0Eop1("not", var("b")), op("and", x, y), op("or", x, y),
    *[op(o, x, y) for o in ("+", "-", "*", "<", "<=", ">", ">=", "==", "!=")],
    D0Eif0(var("c"), x, y), D0Elet("x", x, op("+", x, y)),
    D0Epair(x, y), D0Epfst(var("p")), D0Epsnd(var("p")),
    FACT, FIB, LOOP, D0Efix("f", "f", var("f")), D0Efix("f", "x", D0Eapp(var("g"), var("f"))),
    D0Elet("s", var("z"), D0Elam("z", op("+", var("s"), var("z")))),
]


class StructuralTests(unittest.TestCase):
    def test_output_is_pure(self):
        for dexp in ALL_FORMS:
            with self.subTest(dexp=type(dexp).__name__):
                self.assertTrue(is_pure(compile_expr(dexp)))

    def test_free_variables_preserved(self):
        for dexp in ALL_FORMS:
            with self.subTest(dexp=type(dexp).__name__):
                self.assertEqual(free_vars(compile_expr(dexp)), d0exp_fvset(dexp))

    def test_combinators_closed(self):
        for name, term in COMBINATORS.items():
            with self.subTest(name):
                self.assertEqual(free_vars(term), frozenset())

    def test_input_unchanged(self):
        for dexp in ALL_FORMS:
            snapshot = copy.deepcopy(dexp)
            compile_expr(dexp)
            self.assertEqual(dexp, snapshot)

    def test_deterministic(self):
        for dexp in ALL_FORMS:
            self.assertEqual(compile_expr(dexp), compile_expr(dexp))

    def test_compositional_rules(self):
        # Spot-check the given rules: C[x] = x, C[lam x. e] = lam x. C[e],
        # C[e1 e2] = C[e1] C[e2], C[let x = e1 in e2] = (lam x. C[e2]) C[e1].
        self.assertEqual(compile_expr(x), Var("x"))
        self.assertEqual(compile_expr(D0Elam("x", y)), Lam("x", Var("y")))
        self.assertEqual(compile_expr(D0Eapp(x, y)), App(Var("x"), Var("y")))
        self.assertEqual(compile_expr(D0Elet("x", y, x)),
                         App(Lam("x", Var("x")), Var("y")))

    def test_compilation_never_evaluates(self):
        # ACC-10: replace every evaluator entry point with a failing double.
        fail = mock.Mock(side_effect=AssertionError("evaluator called"))
        with mock.patch.object(evaluator, "evaluate", fail), \
             mock.patch.object(evaluator, "reduce_term", fail), \
             mock.patch.object(evaluator, "_run", fail):
            for dexp in (op("+", N(2), op("*", N(3), N(4))), LOOP,
                         D0Eapp(FACT, N(4)), D0Eapp(D0Elam("x", N(0)), LOOP)):
                self.assertTrue(is_pure(compile_expr(dexp)))
        fail.assert_not_called()

    def test_compiler_does_not_import_evaluator(self):
        tree = ast.parse((HERE / "compiler.py").read_text())
        imported = {node.module for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom)}
        imported |= {alias.name for node in ast.walk(tree)
                     if isinstance(node, ast.Import) for alias in node.names}
        self.assertNotIn("evaluator", imported)
        self.assertNotIn("observe", imported)

    def test_printed_output_uses_target_notation(self):
        self.assertEqual(term_print(compile_expr(D0Eint(2))),
                         "(lam s. (lam z. (s (s z))))")


if __name__ == "__main__":
    unittest.main()
