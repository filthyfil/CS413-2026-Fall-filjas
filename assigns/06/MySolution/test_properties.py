"""Scope and purity checks over every demo program and seeded random programs.

The random generator builds well-typed source programs from a small pool of
names that deliberately collide with encoding binders (s, z, t, f, ...),
thunk parameters (u_1, v_1), and Z's binders (g, x, v), so shadowing and
name collisions occur constantly. For every program it checks:

- purity:      the output uses only Var, Lam, and App;
- scope:       FV(C[e]) = FV(e) under the source binding rules;
- determinism: compiling twice gives the same term;
- immutability: the source AST is unchanged;

and, for closed programs, that observing the compiled result yields the
same data as the shared evaluator's source path (differential testing).
The generator is seeded, so failures are reproducible. Run from assigns/06:
    python3.12 -m unittest -v MySolution/test_properties.py
"""
import copy
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compiler import compile_expr  # noqa: E402
from demo_examples import EXAMPLES  # noqa: E402
from evaluator import evaluate, source_result  # noqa: E402
from pipeline import run_compiled  # noqa: E402
from source_ast import (  # noqa: E402
    d0exp_fvset,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)
from source_visitors import d0exp_pretty  # noqa: E402
from target import free_vars, is_pure  # noqa: E402

NAMES = ["x", "y", "s", "z", "t", "f", "n", "m", "p", "g", "v", "w",
         "u_1", "v_1", "u_2", "a", "b", "c", "tail"]
CLOSED_PROGRAMS = 250
OPEN_PROGRAMS = 250
BUDGET = 500_000
SEED = 413


class Generator:
    """Random well-typed programs of type "nat" or "bool".

    env is a list of (name, type), innermost last; a later binding of the
    same name shadows an earlier one, exactly as in the source language.
    """

    def __init__(self, seed: int, free_names: bool = False):
        self.rng = random.Random(seed)
        self.free_names = free_names     # allow unbound variables (open terms)

    def name(self) -> str:
        return self.rng.choice(NAMES)

    def visible(self, env, ty):
        seen, out = set(), []
        for name, t in reversed(env):
            if name not in seen:
                seen.add(name)
                if t == ty:
                    out.append(name)
        return out

    def program(self, ty, depth=4):
        return self.expr(ty, [], depth)

    def expr(self, ty, env, depth):
        r = self.rng
        if depth == 0:
            return self.leaf(ty, env)
        choice = r.randrange(9)
        if choice == 0:
            return self.leaf(ty, env)
        if choice == 1:                                      # if
            return D0Eif0(self.expr("bool", env, depth - 1),
                          self.expr(ty, env, depth - 1), self.expr(ty, env, depth - 1))
        if choice == 2:                                      # let (shadowing)
            x, t = self.name(), r.choice(["nat", "bool"])
            init = self.expr(t, env, depth - 1)              # x not in scope here
            return D0Elet(x, init, self.expr(ty, env + [(x, t)], depth - 1))
        if choice == 3:                                      # (lam x. body) arg
            x, t = self.name(), r.choice(["nat", "bool"])
            fn = D0Elam(x, self.expr(ty, env + [(x, t)], depth - 1))
            return D0Eapp(fn, self.expr(t, env, depth - 1))
        if choice == 4:                                      # projection of a pair
            other = r.choice(["nat", "bool"])
            if r.random() < 0.5:
                return D0Epfst(D0Epair(self.expr(ty, env, depth - 1),
                                       self.expr(other, env, depth - 1)))
            return D0Epsnd(D0Epair(self.expr(other, env, depth - 1),
                                   self.expr(ty, env, depth - 1)))
        if choice == 5 and ty == "nat" and depth >= 2:       # bounded recursion
            return self.recursion(env, depth)
        if ty == "nat":
            name = r.choice(["+", "-", "*", "+", "-"])
            left = self.expr("nat", env, depth - 1)
            right = self.expr("nat", env, depth - 1) if name != "*" else self.leaf("nat", env)
            return D0Eop2(name, left, right)
        kind = r.randrange(3)
        if kind == 0:
            return D0Eop2(r.choice(["<", "<=", ">", ">=", "==", "!="]),
                          self.expr("nat", env, depth - 1), self.expr("nat", env, depth - 1))
        if kind == 1:
            return D0Eop2(r.choice(["and", "or"]),
                          self.expr("bool", env, depth - 1), self.expr("bool", env, depth - 1))
        return D0Eop1("not", self.expr("bool", env, depth - 1))

    def recursion(self, env, depth):
        """(fix f(p). if p == 0 then e0 else e1 + f (p - 1)) k, k <= 3.

        f and p are drawn from the same pool and may coincide; then the
        parameter shadows the function name and the body cannot recurse.
        """
        f, p = self.name(), self.name()
        body_env = [(n, t) for n, t in env if n != f] + [(p, "nat")]
        e0 = self.expr("nat", body_env, depth - 2)
        e1 = self.expr("nat", body_env, depth - 2)
        if f == p:
            body = D0Eif0(D0Eop2("==", D0Evar(p), D0Eint(0)), e0, e1)
        else:
            call = D0Eapp(D0Evar(f), D0Eop2("-", D0Evar(p), D0Eint(1)))
            body = D0Eif0(D0Eop2("==", D0Evar(p), D0Eint(0)), e0,
                          D0Eop2("+", e1, call))
        return D0Eapp(D0Efix(f, p, body), D0Eint(self.rng.randrange(4)))

    def leaf(self, ty, env):
        r = self.rng
        names = self.visible(env, ty)
        if self.free_names and r.random() < 0.3:
            return D0Evar(self.name())
        if names and r.random() < 0.6:
            return D0Evar(r.choice(names))
        return D0Eint(r.randrange(4)) if ty == "nat" else D0Ebtf(r.random() < 0.5)


def check_structure(test, dexp, label):
    snapshot = copy.deepcopy(dexp)
    term = compile_expr(dexp)
    test.assertTrue(is_pure(term), f"impure output: {label}")
    test.assertEqual(free_vars(term), d0exp_fvset(dexp), f"FV changed: {label}")
    test.assertEqual(compile_expr(dexp), term, f"nondeterministic: {label}")
    test.assertEqual(dexp, snapshot, f"input mutated: {label}")
    return term


class DemoStructureTests(unittest.TestCase):
    def test_every_demo_program(self):
        for ex in EXAMPLES:
            with self.subTest(ex.label):
                term = check_structure(self, ex.source, ex.label)
                self.assertEqual(free_vars(term), frozenset())


class RandomProgramTests(unittest.TestCase):
    def test_closed_programs_agree_with_source(self):
        gen = Generator(SEED)
        for i in range(CLOSED_PROGRAMS):
            ty = gen.rng.choice(["nat", "bool"])
            dexp = gen.program(ty)
            label = f"#{i} {d0exp_pretty(dexp)}"
            with self.subTest(i=i):
                term = check_structure(self, dexp, label)
                expected = source_result(evaluate(dexp).term)
                result = run_compiled(term, ty, BUDGET, BUDGET)
                self.assertTrue(result.decoded, f"not decoded: {label}")
                self.assertEqual(result.value, expected, label)

    def test_open_programs_preserve_scope(self):
        gen = Generator(SEED + 1, free_names=True)
        opened = 0
        for i in range(OPEN_PROGRAMS):
            dexp = gen.program(gen.rng.choice(["nat", "bool"]))
            with self.subTest(i=i):
                check_structure(self, dexp, f"#{i} {d0exp_pretty(dexp)}")
            opened += bool(d0exp_fvset(dexp))
        self.assertGreater(opened, OPEN_PROGRAMS // 3, "generator made too few open terms")

    def test_generator_exercises_hazards(self):
        # Guard against a generator that silently stops producing the cases
        # this suite exists for.
        gen = Generator(SEED)
        programs = [gen.program(gen.rng.choice(["nat", "bool"]))
                    for _ in range(CLOSED_PROGRAMS)]
        text = " ".join(d0exp_pretty(p) for p in programs)
        for needle in ("(fix ", "(let s = ", "(lam u_1. ", "(if ", " and ", " or "):
            self.assertIn(needle, text)
        self.assertTrue(any(_has_coincident_fix(p) for p in programs))


def _has_coincident_fix(dexp) -> bool:
    if isinstance(dexp, D0Efix) and dexp.arg1 == dexp.arg2:
        return True
    return any(_has_coincident_fix(c) for c in vars(dexp).values()
               if isinstance(c, (D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam,
                                 D0Efix, D0Eapp, D0Eif0, D0Elet, D0Epair,
                                 D0Epfst, D0Epsnd)))


if __name__ == "__main__":
    unittest.main()
