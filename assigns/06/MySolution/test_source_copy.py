"""Check that MySolution/lambda1_vp.py is an exact copy of the supplied file.

Run from assigns/06:
    python3.12 -m unittest -v MySolution/test_source_copy.py
"""
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
COPY = HERE / "lambda1_vp.py"
SUPPLIED = HERE.parents[1] / "05" / "lambda1_vp.py"


class SourceCopyTests(unittest.TestCase):
    @unittest.skipUnless(SUPPLIED.exists(), "assigns/05/lambda1_vp.py not present")
    def test_copy_is_unmodified(self):
        self.assertEqual(COPY.read_bytes(), SUPPLIED.read_bytes(),
                         "MySolution/lambda1_vp.py differs from assigns/05/lambda1_vp.py")


if __name__ == "__main__":
    unittest.main()
