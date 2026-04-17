"""
cpp_tracer.py
Traces C++ code using G++ + GDB batch stepping.
Mirrors c_tracer.py but compiles with g++ and handles C++-specific output.
Gracefully reports an error if G++/GDB is not installed.
"""
import subprocess
import os
import tempfile
import re
import json
from tracer.cpp_normalizer import normalize as cpp_normalize


_GDB_SCRIPT = """\
set pagination off
set print pretty off
set print elements 50
break main
run
python
import gdb
import json

steps = []

def step_and_record():
    for _ in range(300):
        try:
            frame = gdb.selected_frame()
            sal   = frame.find_sal()
            lineno = sal.line
            lvars = {}
            try:
                block = frame.block()
                for sym in block:
                    if sym.is_variable or sym.is_argument:
                        try:
                            val = frame.read_var(sym)
                            lvars[sym.name] = str(val)
                        except Exception:
                            pass
            except Exception:
                pass
            steps.append({
                'line':   lineno,
                'event':  'line',
                'locals': lvars,
                'stack':  [frame.name()],
                'stdout': ''
            })
            gdb.execute('next', to_string=True)
        except gdb.error:
            break

step_and_record()
import sys
sys.stdout.write(json.dumps(steps))
end
quit
"""


class CppTracer:
    def trace(self, code: str) -> list[dict]:
        # Check dependencies
        for tool, display in (("g++", "G++"), ("gdb", "GDB")):
            try:
                subprocess.run([tool, "--version"], capture_output=True, timeout=5)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return [self._err_step(
                    1,
                    f"{display} not found. Install G++ and GDB to trace C++ code. "
                    "(On Windows use MinGW-w64 or WSL.)",
                )]

        src_fd,  src_path  = tempfile.mkstemp(suffix=".cpp", prefix="trace_cpp_")
        exe_path = src_path + ".out"
        gdb_fd,  gdb_path  = tempfile.mkstemp(suffix=".gdb",  prefix="trace_gdb_")

        # Auto-prepend headers / main() for LeetCode-style snippets
        normalized_code = cpp_normalize(code)

        try:
            with os.fdopen(src_fd, "w") as f:
                f.write(normalized_code)

            # Compile with debug symbols; C++17 for modern code
            compile_result = subprocess.run(
                ["g++", "-std=c++17", "-g", "-O0", "-o", exe_path, src_path],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if compile_result.returncode != 0:
                err = compile_result.stderr.strip().split("\n")[0]
                return [self._err_step(1, err)]

            with os.fdopen(gdb_fd, "w") as f:
                f.write(_GDB_SCRIPT)

            gdb_result = subprocess.run(
                ["gdb", "--batch", "-x", gdb_path, exe_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            steps = self._parse_output(gdb_result.stdout + gdb_result.stderr, code)
            return steps

        except Exception as exc:
            return [self._err_step(1, str(exc))]
        finally:
            for path in (src_path, exe_path, gdb_path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    # ----------------------------------------------------------------- private
    def _parse_output(self, output: str, code: str) -> list[dict]:
        match = re.search(r"(\[.*\])", output, re.DOTALL)
        if match:
            try:
                steps = json.loads(match.group(1))
                if isinstance(steps, list) and steps:
                    return steps
            except Exception:
                pass

        # Fallback: one step per code line
        return [
            {
                "line":   i + 1,
                "event":  "line",
                "locals": {},
                "stack":  ["main"],
                "stdout": "",
            }
            for i in range(len(code.split("\n")))
        ]

    def _err_step(self, line: int, error: str) -> dict:
        return {
            "line":   line,
            "event":  "error",
            "error":  error,
            "locals": {},
            "stack":  [],
            "stdout": "",
        }
