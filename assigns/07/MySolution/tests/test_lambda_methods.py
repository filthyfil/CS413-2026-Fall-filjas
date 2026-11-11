"""Successful and language-error behavior of the four RPC methods.

No test doubles here: every call goes through Flask, the dispatcher, the
service layer, and the real LAMBDA3 parser/type checker/interpreter/compilers.
"""

import ast
import unittest

from _support import FACTORIAL, RpcTestCase


class HealthTests(RpcTestCase):
    def test_health_returns_status_version_and_preserves_string_id(self):
        self.assertEqual(self.ok("service.health", {}, "health-1"), {"status": "ok", "version": "1.0"})

    def test_health_preserves_numeric_and_null_ids(self):
        for request_id in (0, 7, -3, 2.5, None):
            with self.subTest(id=request_id):
                self.ok("service.health", {}, request_id)

    def test_health_accepts_omitted_params(self):
        self.assertEqual(self.ok("service.health", None, 1)["status"], "ok")


class TypecheckTests(RpcTestCase):
    CASES = [
        ("1 + 2", "sint"),
        ("true", "bool"),
        ("(1, true)", "(sint, bool)"),
        ("((1, 2), (true, false))", "((sint, sint), (bool, bool))"),
        ("lam (x: sint) => x", "sint -> sint"),
        ("list_cons(1, list_cons(2, list_nil()))", "List[sint]"),
        ("optn_cons(5)", "Optn[sint]"),
        (FACTORIAL, "sint"),
    ]

    def test_valid_programs_return_formatted_type(self):
        for source, expected in self.CASES:
            with self.subTest(source=source):
                self.assertEqual(self.ok("lambda.typecheck", {"source": source}), {"type": expected})

    def test_typecheck_does_not_evaluate(self):
        # Would fail at run time / take far too long if it were evaluated.
        self.assertEqual(self.ok("lambda.typecheck", {"source": "list_head(list_tail(list_cons(1, list_nil())))"}), {"type": "sint"})
        self.assertEqual(self.ok("lambda.typecheck", {"source": "1 / 0"}), {"type": "sint"})

    def test_typecheck_with_library(self):
        result = self.ok("lambda.typecheck", {"source": "list_range(1, 4)", "libraries": ["list"]})
        self.assertEqual(result, {"type": "List[sint]"})


class InterpretTests(RpcTestCase):
    def assert_interprets(self, source, type_, value, libraries=None):
        params = {"source": source}
        if libraries is not None:
            params["libraries"] = libraries
        self.assertEqual(self.ok("lambda.interpret", params), {"type": type_, "value": value})

    def test_arithmetic(self):
        self.assert_interprets("20 + 22", "sint", "42")
        self.assert_interprets("(7 - 2) * 3", "sint", "15")
        self.assert_interprets("if 1 < 2 then 10 else 20", "sint", "10")

    def test_factorial(self):
        self.assert_interprets(FACTORIAL, "sint", "720")
        self.assert_interprets(FACTORIAL.replace("fact(6)", "fact(10)"), "sint", "3628800")

    def test_tuple(self):
        self.assert_interprets("(1, true)", "(sint, bool)", "(1, true)")
        self.assert_interprets("let p = (3, 4) in p.0 + p.1 end", "sint", "7")

    def test_collections(self):
        self.assert_interprets("list_cons(1, list_cons(2, list_nil()))", "List[sint]", "[1, 2]")
        self.assert_interprets("list_cons(true, list_nil())", "List[bool]", "[true]")
        self.assert_interprets("optn_cons(5)", "Optn[sint]", "optn_cons(5)")

    def test_collection_from_library(self):
        self.assert_interprets("list_map(list_range(1, 4), lam (x) => x * x)", "List[sint]", "[1, 4, 9]",
                               libraries=["list"])

    def test_all_libraries_load_together(self):
        self.assert_interprets("1", "sint", "1", libraries=["list", "optn", "a1sz", "strm"])

    def test_print_output_is_not_part_of_result(self):
        self.assert_interprets("print(5)", "unit", "()")


class FunctionValueTests(RpcTestCase):
    """Requirement 7: function values are formatted, closures never leak."""

    CASES = [
        ("let f : sint -> sint = lam (x: sint) => x in f end", "sint -> sint", "<lam>"),
        ("lam (x: sint) => x", "sint -> sint", "<lam>"),
        ("fix f(n: sint): sint => n", "sint -> sint", "<fix>"),
        ("(1, lam (x: sint) => x)", "(sint, sint -> sint)", "(1, <lam>)"),
    ]

    def test_function_values_use_d0val_format(self):
        for source, type_, value in self.CASES:
            with self.subTest(source=source):
                result = self.ok("lambda.interpret", {"source": source})
                self.assertEqual(result, {"type": type_, "value": value})
                self.assertIsInstance(result["value"], str)
                for leak in ("env", "D0V", "closure", "object at"):
                    self.assertNotIn(leak, result["value"])


class CompileTests(RpcTestCase):
    def compile(self, source, target, **extra):
        result = self.ok("lambda.compile", {"source": source, "target": target, **extra}, target)
        self.assertEqual(set(result), {"target", "code"})
        self.assertEqual(result["target"], target)
        self.assertIsInstance(result["code"], str)
        self.assertTrue(result["code"].strip())
        return result["code"]

    def test_python_target_returns_parseable_python(self):
        code = self.compile("1 + 2", "python")
        self.assertIn("def _lambda_main():", code)
        self.assertIn("_lambda_result = _lambda_main()", code)
        ast.parse(code)  # syntax check only; the code is never executed

    def test_javascript_target_returns_javascript(self):
        code = self.compile("1 + 2", "javascript")
        self.assertIn("function _lambda_main()", code)
        self.assertIn("const _lambda_result = _lambda_main();", code)
        self.assertNotIn("def _lambda_main", code)

    def test_factorial_compiles_for_both_targets(self):
        python, javascript = self.compile(FACTORIAL, "python"), self.compile(FACTORIAL, "javascript")
        ast.parse(python)
        self.assertNotEqual(python, javascript)

    def test_generated_code_matches_lambda3_unchanged(self):
        from lambda_rpc import frontend
        expression, _ = frontend.L.d0exp_parse_and_typecheck(FACTORIAL)
        self.assertEqual(self.compile(FACTORIAL, "python"), frontend.L.d0exp_compile(expression))
        self.assertEqual(self.compile(FACTORIAL, "javascript"), frontend.L.d0exp_compile_js(expression))

    def test_compile_does_not_run_the_program(self):
        # Fails at run time, but compiling it must succeed.
        self.compile("list_head(list_nil())", "python")

    def test_compile_with_library(self):
        ast.parse(self.compile("list_range(1, 4)", "python", libraries=["list"]))


class LanguageErrorTests(RpcTestCase):
    """Requirements 5 and 9: syntax and type errors are distinct application errors."""

    def test_syntax_error_has_position_details(self):
        error = self.fails("lambda.typecheck", {"source": "if then"}, -32010)
        self.assertEqual(error["message"], "LAMBDA syntax error")
        self.assertEqual(error["data"], {"detail": "Expected an expression", "line": 1, "column": 4, "text": "if then"})

    def test_syntax_error_on_later_line(self):
        error = self.fails("lambda.interpret", {"source": "let x = 1 in\n  x $ 2\nend"}, -32010)
        self.assertEqual((error["data"]["line"], error["data"]["column"]), (2, 5))
        self.assertIn("'$'", error["data"]["detail"])

    def test_type_error(self):
        error = self.fails("lambda.typecheck", {"source": "1 + true"}, -32011)
        self.assertEqual(error["message"], "LAMBDA type error")
        self.assertEqual(error["data"], {"detail": "+: expected bool, got sint"})

    def test_syntax_and_type_codes_differ(self):
        syntax = self.fails("lambda.typecheck", {"source": "1 +"}, -32010)
        type_ = self.fails("lambda.typecheck", {"source": "if 1 then 2 else 3"}, -32011)
        self.assertNotEqual(syntax["code"], type_["code"])

    def test_unbound_variable_rejected_by_type_checker(self):
        for method in ("lambda.typecheck", "lambda.interpret"):
            with self.subTest(method=method):
                error = self.fails(method, {"source": "x + 1"}, -32011)
                self.assertEqual(error["data"]["detail"], "unbound variable 'x'")

    def test_every_source_method_checks_before_running(self):
        for method, extra in (("lambda.interpret", {}), ("lambda.compile", {"target": "python"}),
                              ("lambda.compile", {"target": "javascript"})):
            with self.subTest(method=method, **extra):
                self.fails(method, {"source": "if then", **extra}, -32010)
                self.fails(method, {"source": "1 + true", **extra}, -32011)
                self.fails(method, {"source": "y", **extra}, -32011)

    def test_lambda_syntax_error_is_not_a_json_parse_error(self):
        self.fails("lambda.interpret", {"source": "{\"jsonrpc\":"}, -32010)


if __name__ == "__main__":
    unittest.main()
