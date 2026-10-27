"""unittest suite for the source-parser extension: round trips with d0exp_pretty.

Run from assigns/06:
    python3.12 -m unittest discover -s MySolution/extensions -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_ast import (  # noqa: E402
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)
from source_visitors import d0exp_pretty  # noqa: E402
from source_parser import parse, ParseError  # noqa: E402

x, y, n = D0Evar("x"), D0Evar("y"), D0Evar("n")
LOOP = D0Eapp(D0Efix("loop", "x", D0Eapp(D0Evar("loop"), x)), D0Eint(0))
FACT = D0Efix("fact", "n",
              D0Eif0(D0Eop2("==", n, D0Eint(0)),
                     D0Eint(1),
                     D0Eop2("*", n, D0Eapp(D0Evar("fact"),
                                           D0Eop2("-", n, D0Eint(1))))))

ROUND_TRIP = {
    "int": D0Eint(0),
    "big int": D0Eint(1234567890123),
    "negative int": D0Eint(-3),
    "true": D0Ebtf(True),
    "false": D0Ebtf(False),
    "var": D0Evar("x_1"),
    "underscore var": D0Evar("_tmp"),
    "lam": D0Elam("x", x),
    "fix": FACT,
    "coincident fix": D0Efix("f", "f", D0Evar("f")),
    "app": D0Eapp(x, y),
    "app of negative": D0Eapp(x, D0Eint(-1)),
    "nested app": D0Eapp(D0Eapp(x, y), D0Eapp(y, x)),
    "if": D0Eif0(D0Ebtf(True), D0Eint(1), LOOP),
    "let": D0Elet("x", D0Eint(3),
                  D0Eapp(D0Elam("y", D0Eop2("+", x, y)), D0Eint(4))),
    "let x = x": D0Elet("x", x, x),
    "pair": D0Epair(D0Epair(D0Eint(2), D0Ebtf(True)), D0Eint(3)),
    "fst": D0Epfst(D0Epair(D0Eint(2), D0Ebtf(True))),
    "snd": D0Epsnd(D0Epair(D0Eint(2), D0Ebtf(True))),
    "not": D0Eop1("not", D0Ebtf(False)),
    "op1 +1": D0Eop1("+1", x),
    "op1 -1": D0Eop1("-1", x),
    "op1 symbolic": D0Eop1("~", x),
    "and": D0Eop2("and", D0Ebtf(True), D0Ebtf(False)),
    "or": D0Eop2("or", D0Ebtf(False), D0Ebtf(True)),
    "negative left operand": D0Eop2("+", D0Eint(-1), D0Eint(2)),
    "unsupported op2 symbol": D0Eop2("/", D0Eint(6), D0Eint(2)),
    "unsupported op2 name": D0Eop2("div", D0Eint(6), D0Eint(2)),
    "loop": LOOP,
    "fact 4": D0Eapp(FACT, D0Eint(4)),
    "names like encodings": D0Elam("s", D0Elam("z", D0Eapp(D0Evar("s"), D0Evar("z")))),
}
for op in ("+", "-", "*", "<", "<=", ">", ">=", "==", "!="):
    ROUND_TRIP[f"op2 {op}"] = D0Eop2(op, D0Eint(2), D0Eint(5))


class RoundTripTests(unittest.TestCase):
    def test_parse_inverts_print(self):
        for label, dexp in ROUND_TRIP.items():
            with self.subTest(label):
                self.assertEqual(parse(d0exp_pretty(dexp)), dexp)

    def test_print_inverts_parse(self):
        for label, dexp in ROUND_TRIP.items():
            text = d0exp_pretty(dexp)
            with self.subTest(label):
                self.assertEqual(d0exp_pretty(parse(text)), text)


class TextTests(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(parse("(2 + (3 * 4))"),
                         D0Eop2("+", D0Eint(2), D0Eop2("*", D0Eint(3), D0Eint(4))))
        self.assertEqual(parse("(2 - 5)"), D0Eop2("-", D0Eint(2), D0Eint(5)))
        self.assertEqual(parse("(x -5)"), D0Eapp(x, D0Eint(-5)))
        self.assertEqual(parse("(fix f(x). (f x))"),
                         D0Efix("f", "x", D0Eapp(D0Evar("f"), x)))

    def test_whitespace_is_free(self):
        self.assertEqual(parse("  ( lam x .\n  ( x\ty ) )  "), D0Elam("x", D0Eapp(x, y)))

    def test_errors(self):
        bad = [
            "", "(", ")", "(x)", "(x y z w)", "(lam x x)", "(lam fst. x)",
            "(let x 3 in x)", "(if x then y)", "x y", "(pair x)", "fst",
            "(+ x y)", "(x +)", "x $ y", "(fix f x. x)",
        ]
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ParseError):
                    parse(text)


if __name__ == "__main__":
    unittest.main()
