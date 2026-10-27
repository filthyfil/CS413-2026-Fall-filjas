"""Extension: parser for the source language, the inverse of d0exp_pretty.

Not part of the graded core (the assignment requires no parser). It lets the
web front-end accept readable source text such as (2 + (3 * 4)).

parse(d0exp_pretty(e)) == e for every expression e whose names avoid the
keywords below, and d0exp_pretty(parse(s)) == s for every printer output s.
The accepted grammar is exactly the printer's (whitespace between tokens is
free):

    e ::= INT | -INT | true | false | IDENT
        | (lam IDENT. e)            | (fix IDENT(IDENT). e)
        | (if e then e else e)      | (let IDENT = e in e)
        | (pair e e) | (fst e) | (snd e)
        | (OP1 e)                   | (e OP2 e)        | (e e)

The printer fully parenthesizes, so inside "( ... )" the number of items
decides the form: an application always has two items and a binary operation
three. OP2 is any symbolic operator, an identifier, or and/or, which lets
unsupported spellings such as "/" or "div" reach the compiler and be
rejected there. OP1 is "not" or a symbolic operator such as "~" or "+1".

Limitations, both unavoidable given the printer's output:
- Keywords (lam fix if then else let in pair fst snd true false not and or)
  cannot be variable names, since e.g. D0Eapp(D0Evar("fst"), e) and
  D0Epfst(e) print identically.
- "(-1 e)" is read as the unary operator -1, the form the supplied
  interpreter uses, not as a negative literal applied to e; and a unary
  operator with an identifier name, such as "(neg e)", reads as an
  application. Neither alternative is meaningful in the project's language.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from source_ast import (  # noqa: E402
    d0exp,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)

KEYWORDS = frozenset({
    "lam", "fix", "if", "then", "else", "let", "in", "pair", "fst", "snd",
    "true", "false", "not", "and", "or",
})
_NAMED_OP2 = frozenset({"and", "or"})

_TOKEN = re.compile(r"""
    (?P<space>\s+)
  | (?P<punct>[().])
  | (?P<int>\d+)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<sym>[+\-*/%<>=!&|^~]+\d*)
""", re.VERBOSE)
_NEG_INT = re.compile(r"-\d+")


class ParseError(ValueError):
    """Raised for text that is not in the printer's grammar."""


@dataclass(frozen=True)
class _Tok:
    kind: str       # "punct", "int", "ident", "sym", or "eof"
    text: str
    pos: int


def _tokenize(text: str) -> list[_Tok]:
    tokens, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            raise ParseError(f"unexpected character {text[pos]!r} at {pos}")
        kind = m.lastgroup
        assert kind is not None     # every alternative is a named group
        if kind != "space":
            tokens.append(_Tok(kind, m.group(), pos))
        pos = m.end()
    tokens.append(_Tok("eof", "", pos))
    return tokens


@dataclass(frozen=True)
class _OpName:
    """A paren item that can only be an operator name, never an expression."""
    name: str


class _Parser:
    def __init__(self, text: str) -> None:
        self.tokens = _tokenize(text)
        self.i = 0

    # -- token helpers ---------------------------------------------------

    def peek(self) -> _Tok:
        return self.tokens[self.i]

    def next(self) -> _Tok:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, text: str) -> None:
        tok = self.next()
        if tok.text != text:
            raise ParseError(f"expected {text!r} at {tok.pos}, got {tok.text or 'end of input'!r}")

    def ident(self) -> str:
        tok = self.next()
        if tok.kind != "ident" or tok.text in KEYWORDS:
            raise ParseError(f"expected a variable name at {tok.pos}, got {tok.text or 'end of input'!r}")
        return tok.text

    # -- grammar -----------------------------------------------------------

    def parse(self) -> d0exp:
        dexp = self.expr()
        tok = self.peek()
        if tok.kind != "eof":
            raise ParseError(f"unexpected {tok.text!r} at {tok.pos} after a complete expression")
        return dexp

    def expr(self) -> d0exp:
        tok = self.next()
        match tok.kind:
            case "int":
                return D0Eint(int(tok.text))
            case "sym" if _NEG_INT.fullmatch(tok.text):
                return D0Eint(int(tok.text))
            case "ident" if tok.text == "true":
                return D0Ebtf(True)
            case "ident" if tok.text == "false":
                return D0Ebtf(False)
            case "ident" if tok.text not in KEYWORDS:
                return D0Evar(tok.text)
            case "punct" if tok.text == "(":
                return self.paren()
        raise ParseError(f"expected an expression at {tok.pos}, got {tok.text or 'end of input'!r}")

    def paren(self) -> d0exp:
        """Parse the inside of "( ... )"; the "(" is already consumed."""
        match self.peek().text:
            case "lam":
                self.next()
                x = self.ident()
                self.expect(".")
                body = self.expr()
                self.expect(")")
                return D0Elam(x, body)
            case "fix":
                self.next()
                f = self.ident()
                self.expect("(")
                x = self.ident()
                self.expect(")")
                self.expect(".")
                body = self.expr()
                self.expect(")")
                return D0Efix(f, x, body)
            case "if":
                self.next()
                cond = self.expr()
                self.expect("then")
                then = self.expr()
                self.expect("else")
                other = self.expr()
                self.expect(")")
                return D0Eif0(cond, then, other)
            case "let":
                self.next()
                x = self.ident()
                self.expect("=")
                init = self.expr()
                self.expect("in")
                body = self.expr()
                self.expect(")")
                return D0Elet(x, init, body)
            case "pair":
                self.next()
                first = self.expr()
                second = self.expr()
                self.expect(")")
                return D0Epair(first, second)
            case "fst" | "snd" as which:
                self.next()
                arg = self.expr()
                self.expect(")")
                return D0Epfst(arg) if which == "fst" else D0Epsnd(arg)
        return self.operation_or_app()

    def operation_or_app(self) -> d0exp:
        """Parse (OP1 e), (e OP2 e), or (e e) by counting the items."""
        start = self.peek().pos
        items: list[d0exp | _OpName] = []
        while self.peek().text != ")":
            if self.peek().kind == "eof":
                raise ParseError(f"unclosed '(' at {start - 1}")
            items.append(self.item(first=not items))
        self.next()
        match items:
            case [_OpName(name), arg] if not isinstance(arg, _OpName):
                return D0Eop1(name, arg)
            case [left, _OpName(name) | D0Evar(name), right] \
                    if not isinstance(left, _OpName) and not isinstance(right, _OpName):
                return D0Eop2(name, left, right)
            case [fn, arg] if not isinstance(fn, _OpName) and not isinstance(arg, _OpName):
                return D0Eapp(fn, arg)
        raise ParseError(f"malformed parenthesized form at {start - 1}: "
                         f"expected (op e), (e op e), or (e e)")

    def item(self, first: bool) -> d0exp | _OpName:
        tok = self.peek()
        if tok.kind == "sym":
            # "-1" is a negative literal, except as the first item with no
            # binary operator after it: (-1 e) is the unary operator -1.
            if _NEG_INT.fullmatch(tok.text) and (not first or self._op2_follows()):
                return self.expr()
            self.next()
            return _OpName(tok.text)
        if tok.kind == "ident" and (tok.text in _NAMED_OP2 or (first and tok.text == "not")):
            self.next()
            return _OpName(tok.text)
        return self.expr()

    def _op2_follows(self) -> bool:
        after = self.tokens[self.i + 1]
        return ((after.kind == "sym" and not _NEG_INT.fullmatch(after.text))
                or after.text in _NAMED_OP2)


def parse(text: str) -> d0exp:
    """Parse printer-format source text into a source AST."""
    return _Parser(text).parse()
