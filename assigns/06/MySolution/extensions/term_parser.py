"""Extension: parser for printed target terms (the inverse of term_print).

Not part of the graded core. The web front-end (extensions/web) sends the
compiled artifact to the browser as printed text and back to the server for
Execute; this module turns that text back into a target term.

    term ::= x | (lam x. term) | (term term)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from target import Var, Lam, App, Term  # noqa: E402

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TERM_TOKEN = re.compile(r"\s*(?:([().])|([A-Za-z_][A-Za-z0-9_]*)|(\S))")


class TermParseError(ValueError):
    """Raised for text that is not in term_print's notation."""


def term_parse(text: str) -> Term:
    """Inverse of term_print: parse x, (lam x. body), and (fn arg)."""
    tokens: list[tuple[str, int]] = []
    for m in _TERM_TOKEN.finditer(text):
        if m.group(3):
            raise TermParseError(f"unexpected character {m.group(3)!r} at {m.start(3)}")
        if m.group(1) or m.group(2):
            tokens.append((m.group(1) or m.group(2), m.start(1) if m.group(1) else m.start(2)))
    pos = 0

    def take() -> tuple[str, int]:
        nonlocal pos
        if pos == len(tokens):
            raise TermParseError("unexpected end of input")
        pos += 1
        return tokens[pos - 1]

    def expect(want: str) -> None:
        tok, at = take()
        if tok != want:
            raise TermParseError(f"expected {want!r} at {at}, got {tok!r}")

    def ident() -> str:
        tok, at = take()
        if not _IDENT.fullmatch(tok) or tok == "lam":
            raise TermParseError(f"expected a variable name at {at}, got {tok!r}")
        return tok

    def term() -> Term:
        tok, at = take()
        if tok != "(":
            if not _IDENT.fullmatch(tok) or tok == "lam":
                raise TermParseError(f"expected a term at {at}, got {tok!r}")
            return Var(tok)
        if pos < len(tokens) and tokens[pos][0] == "lam":
            take()
            x = ident()
            expect(".")
            body = term()
            expect(")")
            return Lam(x, body)
        fn = term()
        arg = term()
        expect(")")
        return App(fn, arg)

    result = term()
    if pos != len(tokens):
        raise TermParseError(f"unexpected {tokens[pos][0]!r} at {tokens[pos][1]}")
    return result
