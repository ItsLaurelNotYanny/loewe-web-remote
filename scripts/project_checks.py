"""Read-only project checks and nonempty test runners using the Python standard library."""

import ast
import io
import os
import re
import subprocess
import sys
import tabnanny
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fast_checks():
    sources = [ROOT / "loewe_remote.py", *ROOT.glob("test_*.py"), *ROOT.joinpath("scripts").glob("*.py")]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        ast.parse(text, filename=str(source))
        tabnanny.process_tokens(tokenize.generate_tokens(io.StringIO(text).readline))
    module = ast.parse((ROOT / "loewe_remote.py").read_text(encoding="utf-8"))
    embedded = next(
        ast.literal_eval(item.value)
        for item in module.body
        if isinstance(item, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "HTML_CONTENT" for target in item.targets)
    )
    page = (ROOT / "static/index.html").read_bytes()
    if embedded.encode("utf-8") != page:
        raise ValueError("Python HTML_CONTENT must match static/index.html byte for byte")
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script\s*>", page.decode("utf-8"), re.I | re.S)
    if not scripts:
        raise ValueError("No inline frontend JavaScript was found")
    for index, script in enumerate(scripts, 1):
        result = subprocess.run(["node", "--check"], input=script, text=True, capture_output=True)
        if result.returncode:
            raise ValueError(f"Frontend script {index}:\n{result.stderr.strip()}")


def python_tests():
    suite = unittest.defaultTestLoader.discover(str(ROOT), pattern="test_*.py", top_level_dir=str(ROOT))
    count = suite.countTestCases()
    if count == 0:
        raise ValueError("Python test discovery found zero tests")
    print(f"Discovered {count} Python tests")
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


def rust_tests():
    environment = {**os.environ, "CARGO_TARGET_DIR": str(ROOT / "target/project-gate")}
    command = ["cargo", "test", "--workspace", "--all-targets", "--locked", "--offline"]
    listing = subprocess.run([*command, "--", "--list"], cwd=ROOT, env=environment, text=True, capture_output=True)
    if listing.returncode:
        print(listing.stdout + listing.stderr, file=sys.stderr)
        return 1
    count = len(re.findall(r": test$", listing.stdout, re.M))
    if count == 0:
        raise ValueError("Rust test discovery found zero tests")
    print(f"Discovered {count} Rust target tests")
    # Run cargo's full default test selection, including any documentation tests.
    return subprocess.run(["cargo", "test", "--workspace", "--locked", "--offline"], cwd=ROOT, env=environment).returncode


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"fast", "python-tests", "rust-tests"}:
        print("Usage: project_checks.py {fast|python-tests|rust-tests}", file=sys.stderr)
        return 2
    try:
        if sys.argv[1] == "fast":
            fast_checks()
            return 0
        return python_tests() if sys.argv[1] == "python-tests" else rust_tests()
    except (OSError, SyntaxError, ValueError, StopIteration, tabnanny.NannyNag) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
