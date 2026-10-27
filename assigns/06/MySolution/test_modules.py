"""Module-boundary checks for the graded core.

Run from assigns/06:
    python3.12 -m unittest -v MySolution/test_modules.py
"""
import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = sorted(p for p in HERE.glob("*.py") if not p.name.startswith("test_"))
EXTENSION_MODULES = {p.stem for p in (HERE / "extensions").rglob("*.py")} | {"extensions"}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
    return names


class ModuleBoundaryTests(unittest.TestCase):
    def test_core_does_not_depend_on_extensions(self):
        for path in CORE + sorted(HERE.glob("test_*.py")):
            with self.subTest(path.name):
                self.assertFalse(imports(path) & EXTENSION_MODULES,
                                 f"{path.name} imports an extension module")

    def test_evaluator_does_not_import_compiler(self):
        self.assertNotIn("compiler", imports(HERE / "evaluator.py"))

    def test_compiler_does_not_import_evaluator(self):
        self.assertFalse(imports(HERE / "compiler.py") & {"evaluator", "observe", "pipeline"})

    def test_target_reduction_ignores_church_encodings(self):
        # The reducer must not recognize encodings, so it never sees them.
        self.assertNotIn("church", imports(HERE / "evaluator.py"))
        self.assertNotIn("church", imports(HERE / "target.py"))


if __name__ == "__main__":
    unittest.main()
