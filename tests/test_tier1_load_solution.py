"""
test_tier1_load_solution.py — Unit tests for tier1_fix_load_solution.py

Tests cover:
  - Detection of files that need patching vs. already patched
  - Correct injection of try/except around exec_module
  - Guard injection into @when step bodies
  - Idempotency (running twice produces the same output)
  - Edge cases: different indentation, multiple @when steps, no load_solution

USAGE:
  python -m pytest tests/test_tier1_load_solution.py -v
  python test_tier1_load_solution.py          # runs without pytest
"""

import sys
import textwrap
import unittest

# Import the module under test
from tools.migrate_tier1_load_solution import (
    _needs_patching,
    patch_load_solution,
    patch_when_guards,
    patch_file,
)


# Helpers
def dedent(s: str) -> str:
    return textwrap.dedent(s).lstrip("\n")


# Sample step file content
STEPS_UNPATCHED = dedent("""\
    import ast, importlib.util, os
    from behave import given, when, then

    def load_solution(context):
        path = context.config.userdata.get(
            "solution_path",
            os.path.join(os.path.dirname(__file__), "../../solution.py")
        )
        spec = importlib.util.spec_from_file_location("solution", path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @given("a list of numbers {numbers}")
    def step_given(context, numbers):
        context.numbers = ast.literal_eval(numbers)

    @when("I check for close elements with threshold {threshold}")
    def step_when(context, threshold):
        context.result = load_solution(context).has_close_elements(
            context.numbers, float(threshold)
        )

    @then("the result should be {expected}")
    def step_then(context, expected):
        assert context.result == ast.literal_eval(expected)
""")


STEPS_ALREADY_PATCHED = dedent("""\
    import ast, importlib.util, os
    from behave import given, when, then

    def load_solution(context):
        path = context.config.userdata.get(
            "solution_path",
            os.path.join(os.path.dirname(__file__), "../../solution.py")
        )
        spec = importlib.util.spec_from_file_location("solution", path)
        mod  = importlib.util.module_from_spec(spec)
        context._solution_load_error = None
        try:
            spec.loader.exec_module(mod)
        except Exception as _load_exc:
            context._solution_load_error = str(_load_exc)
            return None
        return mod

    @when("I check for close elements with threshold {threshold}")
    def step_when(context, threshold):
        if getattr(context, '_solution_load_error', None):
            raise AssertionError(
                f"solution.py failed to load: {context._solution_load_error}"
            )
        context.result = load_solution(context).has_close_elements(
            context.numbers, float(threshold)
        )
""")

STEPS_NO_LOAD_SOLUTION = dedent("""\
    from behave import given, when, then

    @given("something")
    def step_given(context):
        context.value = 1

    @when("I do something")
    def step_when(context):
        context.result = context.value + 1

    @then("the result should be {expected}")
    def step_then(context, expected):
        assert context.result == int(expected)
""")

STEPS_TWO_WHEN = dedent("""\
    import importlib.util, os
    from behave import given, when, then

    def load_solution(context):
        path = context.config.userdata.get("solution_path", "solution.py")
        spec = importlib.util.spec_from_file_location("solution", path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @given("input {x}")
    def step_given(context, x):
        context.x = int(x)

    @when("I call foo")
    def step_when_foo(context):
        context.result = load_solution(context).foo(context.x)

    @when("I call bar")
    def step_when_bar(context):
        context.result = load_solution(context).bar(context.x)

    @then("result is {expected}")
    def step_then(context, expected):
        assert context.result == int(expected)
""")


# Test cases
class TestNeedsPatching(unittest.TestCase):

    def test_unpatched_needs_patching(self):
        self.assertTrue(_needs_patching(STEPS_UNPATCHED))

    def test_already_patched_does_not_need_patching(self):
        self.assertFalse(_needs_patching(STEPS_ALREADY_PATCHED))

    def test_no_load_solution_does_not_need_patching(self):
        self.assertFalse(_needs_patching(STEPS_NO_LOAD_SOLUTION))


class TestPatchLoadSolution(unittest.TestCase):

    def test_bare_exec_module_is_replaced(self):
        patched, changed = patch_load_solution(STEPS_UNPATCHED)
        self.assertTrue(changed)
        self.assertIn("_solution_load_error", patched)
        self.assertIn("try:", patched)
        self.assertIn("except Exception as _load_exc:", patched)
        self.assertIn("return None", patched)

    def test_bare_exec_module_is_removed(self):
        """The raw unguarded exec_module line must no longer appear."""
        patched, _ = patch_load_solution(STEPS_UNPATCHED)
        # After patching, exec_module should only appear inside try block
        lines = patched.splitlines()
        exec_lines = [l for l in lines if "spec.loader.exec_module(mod)" in l]
        self.assertEqual(len(exec_lines), 1, "exec_module should appear exactly once")
        # It must be inside a try block — preceded by "try:" somewhere above
        idx = next(i for i, l in enumerate(lines) if "spec.loader.exec_module(mod)" in l)
        above = "\n".join(lines[max(0, idx-5):idx])
        self.assertIn("try:", above)

    def test_already_patched_is_idempotent(self):
        patched, changed = patch_load_solution(STEPS_ALREADY_PATCHED)
        self.assertFalse(changed)
        self.assertEqual(patched, STEPS_ALREADY_PATCHED)

    def test_return_mod_preserved(self):
        patched, _ = patch_load_solution(STEPS_UNPATCHED)
        self.assertIn("return mod", patched)

    def test_no_load_solution_unchanged(self):
        patched, changed = patch_load_solution(STEPS_NO_LOAD_SOLUTION)
        self.assertFalse(changed)
        self.assertEqual(patched, STEPS_NO_LOAD_SOLUTION)

    def test_indentation_preserved_4_spaces(self):
        patched, changed = patch_load_solution(STEPS_UNPATCHED)
        self.assertTrue(changed)
        # try: block should be indented at 4 spaces (matching original)
        self.assertIn("    try:", patched)
        self.assertIn("    except Exception as _load_exc:", patched)

    def test_indentation_preserved_2_spaces(self):
        content_2sp = STEPS_UNPATCHED.replace("    spec.loader", "  spec.loader")
        # Rewrite fully with 2-space indent for load_solution body
        content_2sp = dedent("""\
            import importlib.util, os
            from behave import given, when, then

            def load_solution(context):
              path = "solution.py"
              spec = importlib.util.spec_from_file_location("solution", path)
              mod  = importlib.util.module_from_spec(spec)
              spec.loader.exec_module(mod)
              return mod
        """)
        patched, changed = patch_load_solution(content_2sp)
        self.assertTrue(changed)
        self.assertIn("  try:", patched)
        self.assertIn("  except Exception as _load_exc:", patched)


class TestPatchWhenGuards(unittest.TestCase):

    def _patched_with_load_fix(self, content: str) -> str:
        """Apply load_solution fix first (guard injection depends on it)."""
        content, _ = patch_load_solution(content)
        return content

    def test_guard_injected_into_when_step(self):
        content = self._patched_with_load_fix(STEPS_UNPATCHED)
        patched, changed = patch_when_guards(content)
        self.assertTrue(changed)
        self.assertIn("_solution_load_error", patched)
        # Guard must appear inside the @when function body
        lines = patched.splitlines()
        when_idx = next(i for i, l in enumerate(lines) if "@when(" in l)
        body_lines = lines[when_idx:]
        guard_found = any("_solution_load_error" in l for l in body_lines[:10])
        self.assertTrue(guard_found)

    def test_guard_injected_into_both_when_steps(self):
        content = self._patched_with_load_fix(STEPS_TWO_WHEN)
        patched, changed = patch_when_guards(content)
        self.assertTrue(changed)
        # Count guard occurrences — should be 2 (one per @when)
        guard_count = patched.count("_solution_load_error")
        # At least 2 guard checks (one per @when body), plus the load_solution definition
        self.assertGreaterEqual(guard_count, 3)  # 1 in load_solution + 2 in @when bodies

    def test_guard_not_injected_without_load_fix(self):
        """Guards should not be added if load_solution was not patched."""
        patched, changed = patch_when_guards(STEPS_NO_LOAD_SOLUTION)
        self.assertFalse(changed)

    def test_idempotent_guard_injection(self):
        """Running patch_when_guards twice should not duplicate guards."""
        content = self._patched_with_load_fix(STEPS_UNPATCHED)
        patched1, _ = patch_when_guards(content)
        patched2, changed2 = patch_when_guards(patched1)
        # Second pass should make no changes
        self.assertFalse(changed2, "Guard injection should be idempotent")
        self.assertEqual(patched1, patched2)


class TestPatchFileFull(unittest.TestCase):

    def test_full_patch_produces_both_fixes(self):
        patched, changes = patch_file(STEPS_UNPATCHED)
        self.assertEqual(len(changes), 2)
        self.assertTrue(any("exec_module" in c for c in changes))
        self.assertTrue(any("@when" in c for c in changes))

    def test_full_patch_idempotent(self):
        patched1, changes1 = patch_file(STEPS_UNPATCHED)
        patched2, changes2 = patch_file(patched1)
        self.assertEqual(len(changes2), 0, "Second pass should make no changes")
        self.assertEqual(patched1, patched2)

    def test_no_load_solution_no_changes(self):
        patched, changes = patch_file(STEPS_NO_LOAD_SOLUTION)
        self.assertEqual(len(changes), 0)
        self.assertEqual(patched, STEPS_NO_LOAD_SOLUTION)

    def test_already_patched_no_changes(self):
        patched, changes = patch_file(STEPS_ALREADY_PATCHED)
        self.assertEqual(len(changes), 0)

    def test_patched_content_is_valid_python(self):
        """The patched file must compile without SyntaxError."""
        patched, _ = patch_file(STEPS_UNPATCHED)
        try:
            compile(patched, "<patched>", "exec")
        except SyntaxError as e:
            self.fail(f"Patched content has SyntaxError: {e}")

    def test_two_when_full_patch_is_valid_python(self):
        patched, _ = patch_file(STEPS_TWO_WHEN)
        try:
            compile(patched, "<patched_two_when>", "exec")
        except SyntaxError as e:
            self.fail(f"Patched content has SyntaxError: {e}")


# Standalone runner
if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suite   = loader.loadTestsFromModule(sys.modules[__name__])
    runner  = unittest.TextTestRunner(verbosity=2)
    result  = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
