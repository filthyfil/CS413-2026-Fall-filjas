"""Restricted constructor reader."""
import pytest

from server.lambda1 import D0Eapp, D0Ebtf, D0Eint, D0Elam, D0Eop2, D0Evar
from server.reader import MAX_SOURCE_BYTES, ReadError, read_d0exp


def test_simple_expression():
    assert read_d0exp('D0Eop2("+", D0Eint(20), D0Eint(22))') == \
        D0Eop2("+", D0Eint(20), D0Eint(22))


def test_keywords_negative_numbers_and_booleans():
    assert read_d0exp("D0Eint(arg1=-5)") == D0Eint(-5)
    assert read_d0exp("D0Ebtf(False)") == D0Ebtf(False)
    assert read_d0exp('D0Elam(arg2=D0Evar("x"), arg1="x")') == \
        D0Elam("x", D0Evar("x"))


def test_comments_multiline_and_indentation():
    src = '''
        # a comment
        D0Eapp(          # trailing comment
            D0Elam("x", D0Evar("x")),
            D0Eint(1))
    '''
    assert read_d0exp(src) == D0Eapp(D0Elam("x", D0Evar("x")), D0Eint(1))


def test_all_samples_that_should_parse(sample):
    for name in ("factorial", "fibonacci", "open_var", "closed_let",
                 "div_zero", "type_error", "let_scope", "html_like",
                 "infinite_loop"):
        read_d0exp(sample(name))


@pytest.mark.parametrize("src, fragment", [
    ("", "empty"),
    ("   \n\t  ", "empty"),
    ("# only a comment", "no expression"),
    ("D0Eint(", "syntax error"),
    ("D0Eint(1) D0Eint(2)", "syntax error"),
    ("42", "expected a D0E"),
    ("D0Eint(1), D0Eint(2)", "expected a D0E"),
    ("D0Vint(1)", "unknown constructor"),
    ("print(1)", "unknown constructor"),
    ('__import__("os").system("echo hi")', "unknown constructor"),
    ("D0Eint(1).__class__", "expected a D0E"),
    ('D0Eint("five")', "integer literal"),
    ("D0Eint(True)", "integer literal"),
    ("D0Eint(1.5)", "integer literal"),
    ("D0Ebtf(1)", "True or False"),
    ("D0Evar(x)", "string literal"),
    ('D0Evar("")', "nonempty"),
    ("D0Eint()", "missing argument"),
    ("D0Eint(1, 2)", "takes 1 argument"),
    ("D0Eint(arg2=1)", "no field"),
    ("D0Eint(1, arg1=1)", "given twice"),
    ("D0Eint(*[1])", "not allowed"),
    ('D0Eop2("%", D0Eint(1), D0Eint(2))', "unknown binary operator"),
    ('D0Eop1("neg", D0Eint(1))', "unknown unary operator"),
    ('D0Eop2("+", D0Eint(1), 2)', "expected a D0E"),
])
def test_rejected_input(src, fragment):
    with pytest.raises(ReadError) as info:
        read_d0exp(src)
    assert fragment in str(info.value)


def test_error_reports_user_line_numbers():
    with pytest.raises(ReadError) as info:
        read_d0exp('D0Eop2("+",\n  D0Eint(1),\n  D0Eint("x"))')
    assert info.value.line == 3


def test_size_limit():
    filler = "#" * MAX_SOURCE_BYTES + "\n"
    with pytest.raises(ReadError, match="limit"):
        read_d0exp(filler + "D0Eint(1)")
    # exactly at the limit is fine
    src = "D0Eint(1)"
    ok = "#" * (MAX_SOURCE_BYTES - len(src) - 1) + "\n" + src
    assert read_d0exp(ok) == D0Eint(1)


def test_size_limit_counts_utf8_bytes():
    # 'é' is 2 bytes in UTF-8
    src = "#" + "é" * (MAX_SOURCE_BYTES // 2) + "\nD0Eint(1)"
    with pytest.raises(ReadError, match="limit"):
        read_d0exp(src)
