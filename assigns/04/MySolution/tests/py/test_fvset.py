"""Free-variable analysis (d0exp_fvset) for every expression constructor."""
from server.lambda1 import (D0Eapp, D0Ebtf, D0Efix, D0Eif0, D0Eint, D0Elam,
                            D0Elet, D0Eop1, D0Eop2, D0Epair, D0Epfst,
                            D0Epsnd, D0Evar)
from server.tools import free_variables as fv

x, y, z, f = D0Evar("x"), D0Evar("y"), D0Evar("z"), D0Evar("f")


def test_returns_frozenset():
    assert type(fv(D0Eint(1))) is frozenset
    assert type(fv(x)) is frozenset
    assert type(fv(D0Elam("x", x))) is frozenset


def test_literals_are_closed():
    assert fv(D0Eint(7)) == frozenset()
    assert fv(D0Ebtf(True)) == frozenset()


def test_var():
    assert fv(x) == {"x"}


def test_operators():
    assert fv(D0Eop1("+1", x)) == {"x"}
    assert fv(D0Eop2("+", x, y)) == {"x", "y"}


def test_duplicate_occurrences_counted_once():
    result = fv(D0Eop2("*", x, D0Eop2("+", x, x)))
    assert result == {"x"}
    assert len(result) == 1


def test_lambda_binds_its_parameter():
    assert fv(D0Elam("x", x)) == frozenset()
    assert fv(D0Elam("x", D0Eop2("+", x, y))) == {"y"}


def test_fix_binds_name_and_parameter_in_body():
    body = D0Eapp(f, D0Eop2("-", x, y))
    assert fv(D0Efix("f", "x", body)) == {"y"}


def test_app():
    assert fv(D0Eapp(f, x)) == {"f", "x"}


def test_if0_traverses_all_three_parts():
    assert fv(D0Eif0(x, y, z)) == {"x", "y", "z"}
    assert fv(D0Eif0(D0Ebtf(True), D0Eint(1), z)) == {"z"}  # else branch


def test_let_binds_name_in_body_only():
    assert fv(D0Elet("x", D0Eint(1), x)) == frozenset()
    # the initializer is outside the scope of x
    assert fv(D0Elet("x", x, x)) == {"x"}
    assert fv(D0Elet("x", y, D0Eop2("+", x, z))) == {"y", "z"}


def test_pairs_and_projections():
    assert fv(D0Epair(x, y)) == {"x", "y"}
    assert fv(D0Epfst(x)) == {"x"}
    assert fv(D0Epsnd(y)) == {"y"}


def test_nested_bindings_and_shadowing():
    # lam x. lam y. x + y + z
    e = D0Elam("x", D0Elam("y", D0Eop2("+", x, D0Eop2("+", y, z))))
    assert fv(e) == {"z"}
    # (lam x. x) applied to x: the argument x is free
    assert fv(D0Eapp(D0Elam("x", x), x)) == {"x"}
    # inner lambda shadows outer let
    e = D0Elet("x", D0Eint(1), D0Elam("x", D0Eop2("+", x, y)))
    assert fv(e) == {"y"}


def test_unused_binding_is_not_an_error():
    assert fv(D0Elam("unused", D0Eint(1))) == frozenset()
    assert fv(D0Elet("unused", D0Eint(1), D0Eint(2))) == frozenset()


def test_recursive_samples_are_closed(sample):
    from server.reader import read_d0exp
    assert fv(read_d0exp(sample("factorial"))) == frozenset()
    assert fv(read_d0exp(sample("fibonacci"))) == frozenset()
