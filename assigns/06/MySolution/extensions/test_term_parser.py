"""unittest suite for the term-parser extension.

Run from assigns/06:
    python3.12 -m unittest discover -s MySolution/extensions -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from target import Var, Lam, App, term_print  # noqa: E402
from term_parser import term_parse, TermParseError  # noqa: E402

x, y, z = Var("x"), Var("y"), Var("z")
I = Lam("x", x)


class ParseTests(unittest.TestCase):
    def test_round_trip(self):
        terms = [x, I, App(x, y), Lam("s", Lam("z", App(Var("s"), App(Var("s"), z)))),
                 App(App(I, I), App(I, I)), Lam("u_1", App(Var("lambda"), Var("_q")))]
        for term in terms:
            with self.subTest(term=term_print(term)):
                self.assertEqual(term_parse(term_print(term)), term)

    def test_whitespace(self):
        self.assertEqual(term_parse(" ( lam x .\n( x  y ) ) "), Lam("x", App(x, y)))

    def test_errors(self):
        for bad in ["", "(", "(x)", "(x y z)", "(lam x x)", "(lam lam. x)", "x y",
                    "(lam x. x))", "3", "(x + y)", "lam"]:
            with self.subTest(text=bad):
                with self.assertRaises(TermParseError):
                    term_parse(bad)


if __name__ == "__main__":
    unittest.main()
