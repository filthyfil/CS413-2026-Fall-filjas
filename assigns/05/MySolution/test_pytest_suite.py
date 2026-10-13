"""pytest suite for lambda1_visitors.py (plain functions and assert).

Run from the assignment directory:
    python3.12 -m pytest -v MySolution/test_pytest_suite.py
"""
import copy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import lambda1_vp as m  # noqa: E402
import lambda1_visitors as lv  # noqa: E402
import shared_cases as c  # noqa: E402


def ids(cases):
    return [case[0] for case in cases]


def strip_name(cases):
    return [case[1:] for case in cases]


########################################################################
# Pretty printing
########################################################################

@pytest.mark.parametrize("expr, expected", strip_name(c.PRETTY_CASES),
                         ids=ids(c.PRETTY_CASES))
def test_pretty(expr, expected):
    out = lv.d0exp_pretty(expr)
    assert out == expected
    assert "\n" not in out and out == out.strip()


def test_pretty_covers_every_constructor():
    assert len({type(expr) for _, expr, _ in c.PRETTY_CASES}) == 13


def test_pretty_visitor_used_directly():
    visitor = lv.PrettyPrintVisitor()
    assert isinstance(visitor, m.D0ExpVisitor)
    assert m.D0Ebtf(False).accept(visitor) == "false"


def test_pretty_unsupported_expression():
    with pytest.raises(TypeError):
        lv.d0exp_pretty(m.D0E000())


########################################################################
# Substitution: exact results under the documented fresh-name policy
########################################################################

@pytest.mark.parametrize("e, x, r, expected", strip_name(c.SUBST_CASES),
                         ids=ids(c.SUBST_CASES))
def test_substitute_exact(e, x, r, expected):
    result = lv.d0exp_substitute(e, x, r)
    assert lv.d0exp_pretty(result) == lv.d0exp_pretty(expected)
    assert result == expected


@pytest.mark.parametrize("e, x, r, expected", strip_name(c.ALPHA_CASES),
                         ids=ids(c.ALPHA_CASES))
def test_substitute_up_to_alpha(e, x, r, expected):
    assert lv.d0exp_alpha_equiv(lv.d0exp_substitute(e, x, r), expected)


def test_capture_would_be_wrong():
    e = c.lam("y", c.add(c.V("x"), c.V("y")))
    captured = c.lam("y", c.add(c.V("y"), c.V("y")))
    assert not lv.d0exp_alpha_equiv(lv.d0exp_substitute(e, "x", c.V("y")), captured)


def test_substitute_covers_every_constructor():
    assert len({type(e) for _, e, _, _, _ in c.CONSTRUCTOR_CASES}) == 13


@pytest.mark.parametrize("e, x, r, expected",
                         strip_name(c.SUBST_CASES + c.ALPHA_CASES),
                         ids=ids(c.SUBST_CASES + c.ALPHA_CASES))
def test_free_variable_property(e, x, r, expected):
    result = lv.d0exp_substitute(e, x, r)
    fv_e = m.d0exp_fvset(e)
    if x in fv_e:
        assert m.d0exp_fvset(result) == (fv_e - {x}) | m.d0exp_fvset(r)
    else:
        assert m.d0exp_fvset(result) == fv_e
        assert lv.d0exp_alpha_equiv(result, e)


@pytest.mark.parametrize("e, x, r, expected", strip_name(c.SUBST_CASES),
                         ids=ids(c.SUBST_CASES))
def test_inputs_preserved_and_deterministic(e, x, r, expected):
    e_before, r_before = copy.deepcopy(e), copy.deepcopy(r)
    first = lv.d0exp_substitute(e, x, r)
    second = lv.d0exp_substitute(e, x, r)
    assert e == e_before and r == r_before
    assert first == second


def test_substitute_unsupported_expression():
    with pytest.raises(TypeError):
        lv.d0exp_substitute(m.D0E000(), "x", c.I(1))


########################################################################
# No evaluation
########################################################################

@pytest.fixture
def forbid_evaluation(monkeypatch):
    def fail(*args):
        raise AssertionError("expression was evaluated")
    for attr in dir(m.EvaluateVisitor):
        if attr.startswith("visit_"):
            monkeypatch.setattr(m.EvaluateVisitor, attr, fail)


@pytest.mark.parametrize("e", c.UNEVALUABLE)
def test_no_evaluation(forbid_evaluation, e):
    result = lv.d0exp_substitute(e, "x", c.op2("/", c.I(1), c.I(0)))
    assert isinstance(result, type(e))
    lv.d0exp_pretty(result)


def test_evaluation_hook_works(forbid_evaluation):
    with pytest.raises(AssertionError):
        m.d0exp_evaluate(c.I(1))


########################################################################
# Alpha-equivalence checker
########################################################################

@pytest.mark.parametrize("a, b, equivalent", strip_name(c.ALPHA_EQUIV_CASES),
                         ids=ids(c.ALPHA_EQUIV_CASES))
def test_alpha_equiv(a, b, equivalent):
    assert lv.d0exp_alpha_equiv(a, b) == equivalent


def test_debruijn_form():
    term = c.lam("x", c.lam("y", c.app(c.V("x"), c.V("z"))))
    assert lv.d0exp_debruijn(term) == (
        "lam", ("lam", ("app", ("bound", 1), ("free", "z"))))
