"""Source AST for the compiler: the supplied Assignment 5 lambda1_vp.py.

lambda1_vp.py in this directory is an unmodified, copy of the
supplied assigns/05/lambda1_vp.py (test_source_copy.py checks this). Every
other module imports the source AST through this one.
"""
from __future__ import annotations

from lambda1_vp import (
    D0ExpVisitor, D0E000, d0exp, dvar, d0exp_fvset,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)

__all__ = [
    "D0ExpVisitor", "D0E000", "d0exp", "dvar", "d0exp_fvset",
    "D0Eint", "D0Ebtf", "D0Eop1", "D0Eop2", "D0Evar", "D0Elam", "D0Efix",
    "D0Eapp", "D0Eif0", "D0Elet", "D0Epair", "D0Epfst", "D0Epsnd",
]
