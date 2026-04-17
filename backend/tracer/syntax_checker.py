"""
syntax_checker.py
Validates code syntax for Python, JavaScript, C, and C++ before tracing.
"""
import ast
import subprocess
import tempfile
import os
from tracer.cpp_normalizer import normalize as cpp_normalize


class SyntaxChecker:
    def check(self, code: str, language: str) -> dict:
        lang = language.lower()
        if lang == "python":
            return self._check_python(code)
        elif lang == "javascript":
            return self._check_javascript(code)
        elif lang == "c":
            return self._check_c(code)
        elif lang == "cpp":
            return self._check_cpp(code)
        return {"valid": True, "error": None, "line": None}

    # ------------------------------------------------------------------ Python
    def _check_python(self, code: str) -> dict:
        try:
            ast.parse(code)
            return {"valid": True, "error": None, "line": None}
        except SyntaxError as e:
            return {
                "valid": False,
                "error": f"SyntaxError: {e.msg}",
                "line": e.lineno,
            }

    # --------------------------------------------------------------- JavaScript
    def _check_javascript(self, code: str) -> dict:
        try:
            result = subprocess.run(
                ["node", "--check"],
                input=code,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip().split("\n")[0]
                line = self._extract_line_from_node_error(result.stderr)
                return {"valid": False, "error": error_msg, "line": line}
            return {"valid": True, "error": None, "line": None}
        except FileNotFoundError:
            # Node.js not installed — skip JS syntax check
            return {"valid": True, "error": None, "line": None}
        except subprocess.TimeoutExpired:
            return {"valid": True, "error": None, "line": None}

    def _extract_line_from_node_error(self, stderr: str) -> int | None:
        for part in stderr.split(":"):
            part = part.strip()
            if part.isdigit():
                return int(part)
        return None

    # ------------------------------------------------------------------ C
    def _check_c(self, code: str) -> dict:
        try:
            fd, tmpfile = tempfile.mkstemp(suffix=".c")
            with os.fdopen(fd, "w") as f:
                f.write(code)

            result = subprocess.run(
                ["gcc", "-fsyntax-only", tmpfile],
                capture_output=True,
                text=True,
                timeout=10,
            )
            os.unlink(tmpfile)

            if result.returncode != 0:
                raw = result.stderr.strip().split("\n")[0]
                line = None
                parts = raw.split(":")
                if len(parts) >= 2:
                    try:
                        line = int(parts[1])
                    except ValueError:
                        pass
                return {"valid": False, "error": raw, "line": line}
            return {"valid": True, "error": None, "line": None}
        except FileNotFoundError:
            return {"valid": True, "error": None, "line": None}
        except Exception:
            return {"valid": True, "error": None, "line": None}

    # ------------------------------------------------------------------ C++
    def _check_cpp(self, code: str) -> dict:
        try:
            # Auto-prepend headers / main() for LeetCode-style snippets
            normalized = cpp_normalize(code)

            fd, tmpfile = tempfile.mkstemp(suffix=".cpp")
            with os.fdopen(fd, "w") as f:
                f.write(normalized)

            result = subprocess.run(
                ["g++", "-std=c++17", "-fsyntax-only", tmpfile],
                capture_output=True,
                text=True,
                timeout=10,
            )
            os.unlink(tmpfile)

            if result.returncode != 0:
                raw = result.stderr.strip().split("\n")[0]
                line = None
                parts = raw.split(":")
                if len(parts) >= 2:
                    try:
                        line = int(parts[1])
                    except ValueError:
                        pass
                return {"valid": False, "error": raw, "line": line}
            return {"valid": True, "error": None, "line": None}
        except FileNotFoundError:
            return {"valid": True, "error": None, "line": None}
        except Exception:
            return {"valid": True, "error": None, "line": None}
