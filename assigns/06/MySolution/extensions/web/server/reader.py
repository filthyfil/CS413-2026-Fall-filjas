"""Source reader: turns source text into a d0exp.

Two notations are accepted. Lines starting with "#" are comments in both.

1. A Python-style constructor expression such as
   ``D0Eop2("+", D0Eint(20), D0Eint(22))`` (the Assignment 4 format). It is
   parsed with ``ast`` and the syntax tree is walked by hand; nothing is ever
   passed to ``eval``/``exec``. Only the D0E* constructors from lambda1_vp.py
   and int/str/bool literals are accepted, and every argument is checked
   against the constructor's schema.
2. The pretty-printer notation, such as ``(2 + (3 * 4))``, read by the
   source-parser extension.

Operator names are not restricted here: the compiler and the evaluator
reject operators outside the language with their own diagnostics.

Adapted from assigns/04/MySolution/server/reader.py.
"""
import ast
import dataclasses
from typing import NoReturn

from . import _CORE  # noqa: F401  (sets up the import path)
import source_ast as L
from source_parser import ParseError, parse as parse_pretty

# 1 MB, measured in UTF-8 bytes (requirement F3). Mirrored in web/js/model.js.
MAX_SOURCE_BYTES = 1_000_000

# Argument kinds for each constructor, in field order.
#   int  - integer literal (may be negative)   bool - True/False
#   var  - nonempty string (variable name)     exp  - nested constructor
#   op1/op2 - nonempty operator name string
SCHEMA: dict[type, tuple[str, ...]] = {
    L.D0Eint: ("int",),
    L.D0Ebtf: ("bool",),
    L.D0Eop1: ("op1", "exp"),
    L.D0Eop2: ("op2", "exp", "exp"),
    L.D0Evar: ("var",),
    L.D0Elam: ("var", "exp"),
    L.D0Efix: ("var", "var", "exp"),
    L.D0Eapp: ("exp", "exp"),
    L.D0Eif0: ("exp", "exp", "exp"),
    L.D0Elet: ("var", "exp", "exp"),
    L.D0Epair: ("exp", "exp"),
    L.D0Epfst: ("exp",),
    L.D0Epsnd: ("exp",),
}
CONSTRUCTORS = {cls.__name__: cls for cls in SCHEMA}


class ReadError(Exception):
    """The source is not an acceptable constructor expression."""

    def __init__(self, message: str, line: int | None = None,
                 col: int | None = None):
        self.line = line
        self.col = col
        where = f"line {line}, column {col}: " if line is not None else ""
        super().__init__(where + message)


def check_source_text(source: str) -> None:
    """Reject empty, whitespace-only and oversized source."""
    if not isinstance(source, str):
        raise ReadError("source must be text")
    if not source.strip():
        raise ReadError("source is empty")
    size = len(source.encode("utf-8"))
    if size > MAX_SOURCE_BYTES:
        raise ReadError(f"source is {size} bytes; the limit is "
                        f"{MAX_SOURCE_BYTES} bytes")


def read_d0exp(source: str) -> L.D0E000:
    """Parse ``source`` into a d0exp, or raise ReadError."""
    check_source_text(source)
    code = "\n".join("" if line.lstrip().startswith("#") else line
                     for line in source.splitlines())
    if not code.strip():
        raise ReadError("no expression found (only comments?)")
    if not code.lstrip().startswith("D0E"):
        try:
            return parse_pretty(code)
        except ParseError as exc:
            raise ReadError(f"{exc} (expected pretty-printed source such as "
                            f"(2 + (3 * 4)) or a D0E... constructor)") from None
        except RecursionError:
            raise ReadError("expression is nested too deeply to parse") from None
    # Wrapping in parentheses allows indentation, multiple lines and
    # trailing comments. The opening line shifts line numbers by one.
    try:
        tree = ast.parse("(\n" + source + "\n)", mode="eval")
    except SyntaxError as exc:
        line = exc.lineno - 1 if exc.lineno else None
        col = exc.offset
        if line is not None and not 1 <= line <= source.count("\n") + 1:
            # Reported on the added wrapper lines: e.g. an unclosed "(".
            line, col = None, None
        raise ReadError(f"syntax error: {exc.msg}", line, col) from None
    except (RecursionError, MemoryError):
        raise ReadError("expression is nested too deeply to parse") from None
    if isinstance(tree.body, ast.Tuple) and not tree.body.elts:
        raise ReadError("no expression found (only comments?)")
    return _convert(tree.body)


def _fail(node: ast.AST, message: str) -> NoReturn:
    line = getattr(node, "lineno", 0) - 1
    if line < 1:  # node starts on the added "(" line
        raise ReadError(message)
    raise ReadError(message, line, getattr(node, "col_offset", -1) + 1)


def _convert(node: ast.AST) -> L.D0E000:
    if not isinstance(node, ast.Call):
        _fail(node, f"expected a D0E... constructor, found "
                    f"{_describe(node)}")
    if not isinstance(node.func, ast.Name) or node.func.id not in CONSTRUCTORS:
        name = node.func.id if isinstance(node.func, ast.Name) else _describe(node.func)
        _fail(node, f"unknown constructor {name!r}; allowed: "
                    + ", ".join(CONSTRUCTORS))
    cls = CONSTRUCTORS[node.func.id]
    kinds = SCHEMA[cls]
    names = [f.name for f in dataclasses.fields(cls)]
    cname = cls.__name__

    if any(isinstance(a, ast.Starred) for a in node.args) or \
            any(k.arg is None for k in node.keywords):
        _fail(node, f"{cname}: * and ** arguments are not allowed")
    if len(node.args) > len(names):
        _fail(node, f"{cname} takes {len(names)} argument(s), "
                    f"got {len(node.args)}")
    given: dict[str, ast.AST] = dict(zip(names, node.args))
    for kw in node.keywords:
        if kw.arg not in names:
            _fail(kw.value, f"{cname} has no field {kw.arg!r}; "
                            f"fields are {', '.join(names)}")
        if kw.arg in given:
            _fail(kw.value, f"{cname}: field {kw.arg!r} given twice")
        given[kw.arg] = kw.value
    missing = [n for n in names if n not in given]
    if missing:
        _fail(node, f"{cname}: missing argument(s) {', '.join(missing)}")

    values = [_convert_arg(cname, n, k, given[n]) for n, k in zip(names, kinds)]
    return cls(*values)


def _convert_arg(cname: str, field: str, kind: str, node: ast.AST):
    if kind == "exp":
        return _convert(node)
    value = _literal(node)
    if kind == "int":
        if type(value) is not int:
            _fail(node, f"{cname}.{field} must be an integer literal")
    elif kind == "bool":
        if type(value) is not bool:
            _fail(node, f"{cname}.{field} must be True or False")
    else:
        if type(value) is not str:
            _fail(node, f"{cname}.{field} must be a string literal")
        if kind == "var" and not value:
            _fail(node, f"{cname}.{field} must be a nonempty variable name")
        if kind in ("op1", "op2") and not value:
            _fail(node, f"{cname}.{field} must be a nonempty operator name")
    return value


_MISSING = object()


def _literal(node: ast.AST):
    """Value of a literal argument, or _MISSING for anything else."""
    if isinstance(node, ast.Constant):
        return node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and type(node.operand.value) is int):
        return -node.operand.value
    return _MISSING


def _describe(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return f"name {node.id!r}"
    if isinstance(node, ast.Constant):
        return f"literal {node.value!r}"
    return type(node).__name__.lower() + " expression"
