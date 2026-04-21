"""
c_tracer.py
Traces C code using GCC + GDB batch stepping.
Gracefully reports an error if GCC or GDB is not installed.
"""
import subprocess
import os
import tempfile
import re


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
    for _ in range(200):
        try:
            frame = gdb.selected_frame()
            sal = frame.find_sal()
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
            steps.append({'line': lineno, 'event': 'line', 'locals': lvars,
                          'stack': [frame.name()], 'stdout': ''})
            gdb.execute('next', to_string=True)
        except gdb.error:
            break
step_and_record()
import sys
sys.stdout.write(json.dumps(steps))
end
quit
"""


class CTracer:
    def trace(self, code: str) -> list[dict]:
        # Check dependencies
        for tool in ("gcc", "gdb"):
            try:
                subprocess.run([tool, "--version"], capture_output=True, timeout=5)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return [self._err_step(
                    1,
                    f"{tool.upper()} not found. Install GCC and GDB to trace C code. "
                    "(On Windows use MinGW or WSL.)",
                )]

        src_fd, src_path = tempfile.mkstemp(suffix=".c", prefix="trace_c_")
        exe_path = src_path + ".out"
        gdb_fd, gdb_path = tempfile.mkstemp(suffix=".gdb", prefix="trace_gdb_")

        try:
            with os.fdopen(src_fd, "w") as f:
                f.write(code)

            # Compile with debug symbols
            compile_result = subprocess.run(
                ["gcc", "-g", "-O0", "-o", exe_path, src_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if compile_result.returncode != 0:
                err_lines = compile_result.stderr.strip().split("\n")
                real_err = next(
                    (
                        l for l in err_lines
                        if l.strip()
                        and "libmingw32" not in l
                        and "WinMain" not in l
                        and "collect2" not in l
                        and "ld.exe" not in l
                    ),
                    err_lines[0] if err_lines else "Compilation failed.",
                )
                return [self._err_step(1, f"[COMPILE ERROR]  {real_err}")]

            # Write GDB script
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
        """Try to parse JSON from GDB Python output; fall back to line-based."""
        # GDB Python script writes JSON to stdout
        match = re.search(r"(\[.*\])", output, re.DOTALL)
        if match:
            try:
                steps = __import__("json").loads(match.group(1))
                if isinstance(steps, list) and steps:
                    return steps
            except Exception:
                pass

        # Fallback: one step per code line (no variable info)
        code_lines = code.split("\n")
        return [
            {
                "line": i + 1,
                "event": "line",
                "locals": {},
                "stack": ["main"],
                "stdout": "",
            }
            for i in range(len(code_lines))
        ]

    def _err_step(self, line: int, error: str) -> dict:
        return {
            "line": line,
            "event": "error",
            "error": error,
            "locals": {},
            "stack": [],
            "stdout": "",
        }
