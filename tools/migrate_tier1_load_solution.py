"""
migrate_tier1_load_solution.py — Patch load_solution() in all step definition files
in validated_dataset/ to add proper error handling.

WHY THIS MATTERS FOR RL TRAINING:
  Without this fix, a SyntaxError or ImportError in LLM-generated solution.py
  causes spec.loader.exec_module(mod) to raise an unhandled exception.
  Behave then crashes the entire episode instead of returning a clean FAILED
  step — corrupting the reward signal.

WHAT THIS SCRIPT DOES:
  1. Finds every *_steps.py file under validated_dataset/
  2. Detects if load_solution() lacks error handling (safe to re-run)
  3. Replaces the bare exec_module call with a guarded version that sets
     context._solution_load_error on failure
  4. Adds a guard check at the top of every @when step body so a load
     failure produces a clean AssertionError instead of an AttributeError
  5. Writes patched files to enhanced_dataset/ (mirroring the directory
     structure) — original validated_dataset/ is NEVER modified

USAGE:
  python migrate_tier1_load_solution.py [--dry-run] [--verbose]

  --dry-run   Show what would change without writing any files
  --verbose   Print a diff-style summary for every patched file
"""

import argparse
import re
import shutil
import sys
from pathlib import Path


VALIDATED_DIR = Path("validated_dataset")
ENHANCED_DIR  = Path("enhanced_dataset")

# The exact load_solution body the LLM was instructed to use (from prompts)
# We match both whitespace-flexible variants.
_LOAD_SOL_PATTERN = re.compile(
    r"(def load_solution\(context\):.*?)"           # function def line(s)
    r"([ \t]+spec\.loader\.exec_module\(mod\)\n)"   # the bare exec_module line
    r"([ \t]+return mod)",                           # the return
    re.DOTALL,
)

# Replacement: wrap exec_module in try/except, store error on context
_LOAD_SOL_REPLACEMENT = r"""\1\2"""  # built dynamically below to preserve indent

# Pattern to find @when decorated function bodies so we can add guard calls
_WHEN_DECORATOR_PATTERN = re.compile(
    r"(@when\(.*?\)\n"          # @when decorator line
    r"def \w+\(context.*?\):\n" # def line
    r")([ \t]+)",               # leading indent of first body line
    re.DOTALL,
)

_GUARD_SNIPPET = (
    "    if getattr(context, '_solution_load_error', None):\n"
    "        raise AssertionError(\n"
    "            f\"solution.py failed to load: {context._solution_load_error}\"\n"
    "        )\n"
)


# Core patching logic
def _build_safe_exec_module(indent: str) -> str:
    """Return a try/except block that replaces the bare exec_module line."""
    i = indent  # e.g. "    " (4 spaces)
    return (
        f"{i}context._solution_load_error = None\n"
        f"{i}try:\n"
        f"{i}    spec.loader.exec_module(mod)\n"
        f"{i}except Exception as _load_exc:\n"
        f"{i}    context._solution_load_error = str(_load_exc)\n"
        f"{i}    return None\n"
    )


def _needs_patching(content: str) -> bool:
    """Return True if this file still has an unguarded exec_module call."""
    return bool(_LOAD_SOL_PATTERN.search(content)) and \
           "_solution_load_error" not in content


def patch_load_solution(content: str) -> tuple[str, bool]:
    """
    Replace the bare spec.loader.exec_module(mod) with a guarded version.
    Returns (patched_content, was_changed).
    """
    match = _LOAD_SOL_PATTERN.search(content)
    if not match or "_solution_load_error" in content:
        return content, False

    # Detect indent from the exec_module line
    exec_line = match.group(2)                  # e.g. "    spec.loader.exec_module(mod)\n"
    indent    = re.match(r"([ \t]+)", exec_line).group(1)

    safe_block = _build_safe_exec_module(indent)

    # Replace: keep the def/spec setup, swap exec_module line, keep return mod
    new_content = _LOAD_SOL_PATTERN.sub(
        lambda m: m.group(1) + safe_block + indent + "return mod",
        content,
        count=1,
    )
    return new_content, new_content != content


def patch_when_guards(content: str) -> tuple[str, bool]:
    """
    Add a _solution_load_error guard as the first line of every @when step body.
    This ensures a load failure produces a clean AssertionError, not AttributeError.
    """
    if "_solution_load_error" not in content:
        # No point adding guards if load_solution wasn't patched
        return content, False

    lines    = content.splitlines(keepends=True)
    out      = []
    changed  = False
    i        = 0

    while i < len(lines):
        line = lines[i]
        # Detect @when decorator
        if re.match(r"[ \t]*@when\(", line):
            out.append(line)
            i += 1
            # Collect def line
            if i < len(lines) and re.match(r"[ \t]*def ", lines[i]):
                out.append(lines[i])
                i += 1
                # Detect indent of first body line
                if i < len(lines):
                    body_indent_match = re.match(r"([ \t]+)", lines[i])
                    if body_indent_match:
                        body_indent = body_indent_match.group(1)
                        guard = (
                            f"{body_indent}if getattr(context, '_solution_load_error', None):\n"
                            f"{body_indent}    raise AssertionError(\n"
                            f"{body_indent}        f\"solution.py failed to load: "
                            f"{{context._solution_load_error}}\"\n"
                            f"{body_indent}    )\n"
                        )
                        # Only inject if guard is not already there
                        if "_solution_load_error" not in lines[i]:
                            out.append(guard)
                            changed = True
        else:
            out.append(line)
            i += 1
            continue

    return "".join(out), changed


def patch_file(content: str) -> tuple[str, list[str]]:
    """
    Apply all Tier-1 patches to a steps file content.
    Returns (patched_content, list_of_changes_applied).
    """
    changes = []

    content, changed = patch_load_solution(content)
    if changed:
        changes.append("load_solution: added error handling around exec_module")

    content, changed = patch_when_guards(content)
    if changed:
        changes.append("@when steps: added _solution_load_error guard")

    return content, changes


# File discovery
def find_steps_files(root: Path) -> list[Path]:
    """Find all *_steps.py files under root."""
    return sorted(root.rglob("*_steps.py"))


# Main pipeline
def run(dry_run: bool = False, verbose: bool = False) -> dict:
    """
    Process all step files: patch and write to enhanced_dataset/.
    Returns a summary dict.
    """
    if not VALIDATED_DIR.exists():
        print(f"ERROR: {VALIDATED_DIR} not found. Run from project root.")
        sys.exit(1)

    steps_files = find_steps_files(VALIDATED_DIR)
    if not steps_files:
        print(f"No *_steps.py files found under {VALIDATED_DIR}")
        sys.exit(1)

    stats = {
        "total":       len(steps_files),
        "patched":     0,
        "skipped":     0,   # already had error handling
        "no_match":    0,   # no load_solution found (unusual)
        "errors":      0,
    }

    print(f"Found {len(steps_files)} step files under {VALIDATED_DIR}/")
    print(f"Output dir: {ENHANCED_DIR}/")
    if dry_run:
        print("DRY-RUN mode — no files will be written.\n")

    for steps_path in steps_files:
        # Mirror path under enhanced_dataset/
        rel       = steps_path.relative_to(VALIDATED_DIR)
        out_path  = ENHANCED_DIR / rel

        try:
            content = steps_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ERROR reading {steps_path}: {e}")
            stats["errors"] += 1
            continue

        if "load_solution" not in content:
            if verbose:
                print(f"  SKIP (no load_solution): {rel}")
            stats["no_match"] += 1
            # Still copy the file so enhanced_dataset/ is complete
            if not dry_run:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(content, encoding="utf-8")
            continue

        if not _needs_patching(content):
            if verbose:
                print(f"  SKIP (already patched): {rel}")
            stats["skipped"] += 1
            if not dry_run:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(content, encoding="utf-8")
            continue

        patched, changes = patch_file(content)

        if not changes:
            if verbose:
                print(f"  SKIP (no changes produced): {rel}")
            stats["skipped"] += 1
            if not dry_run:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(content, encoding="utf-8")
            continue

        stats["patched"] += 1
        if verbose or dry_run:
            print(f"  PATCH: {rel}")
            for c in changes:
                print(f"         → {c}")

        if not dry_run:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(patched, encoding="utf-8")

    # Copy all non-steps files (feature files, solution.py) unchanged
    if not dry_run:
        _copy_non_steps_files()

    print("\nSummary ─────────────────────────────────────────────")
    print(f"  Total step files : {stats['total']}")
    print(f"  Patched          : {stats['patched']}")
    print(f"  Already patched  : {stats['skipped']}")
    print(f"  No load_solution : {stats['no_match']}")
    print(f"  Errors           : {stats['errors']}")
    if not dry_run:
        print(f"\n  Enhanced dataset written to: {ENHANCED_DIR}/")

    return stats

def _copy_non_steps_files():
    """Copy .feature files and solution.py to enhanced_dataset/ unchanged."""
    for src in VALIDATED_DIR.rglob("*"):
        if src.is_file() and not src.name.endswith("_steps.py"):
            rel      = src.relative_to(VALIDATED_DIR)
            dst      = ENHANCED_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


# CLI
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tier-1 fix: add load_solution() error handling to all step files."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be patched without writing files.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print details for every processed file.",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, verbose=args.verbose)
