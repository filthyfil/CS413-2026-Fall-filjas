from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture
def sample():
    """sample("factorial") -> text of samples/factorial.txt"""
    return lambda name: (SAMPLES / f"{name}.txt").read_text(encoding="utf-8")
