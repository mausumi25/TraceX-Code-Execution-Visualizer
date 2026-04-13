"""
python_tracer.py
Uses sys.settrace to capture step-by-step execution of Python code.
"""
import sys
import io
import traceback as tb_module
from copy import deepcopy


class PythonTracer:
    def __init__(self):
        self._steps = []
        self._stdout_buf = io.StringIO()
        self._call_stack = []

    # ------------------------------------------------------------------ public
    def trace(self, code: str) -> list[dict]:
        old_stdout = sys.stdout
        sys.stdout = self._stdout_buf

        try:
            compiled = compile(code, "<trace>", "exec")
            sys.settrace(self._trace_dispatch)
            exec(compiled, {"__name__": "__main__"})  # noqa: S102
        except SyntaxError as e:
            self._steps.append(self._make_step(
                line=e.lineno or 1,
                event="error",
                locals_snap={},
                error=f"SyntaxError: {e.msg}",
            ))
        except SystemExit:
            pass
        except Exception as exc:
            raw_tb = tb_module.extract_tb(sys.exc_info()[2])
            lineno = raw_tb[-1].lineno if raw_tb else 1
            # Only add if not already captured by 'exception' event
            if not any(s.get("event") == "exception" for s in self._steps):
                self._steps.append(self._make_step(
                    line=lineno,
                    event="error",
                    locals_snap={},
                    error=f"{type(exc).__name__}: {exc}",
                ))
        finally:
            sys.settrace(None)
            sys.stdout = old_stdout

        return self._steps

    # ----------------------------------------------------------------- private
    def _trace_dispatch(self, frame, event, arg):
        func_name = frame.f_code.co_name
        if func_name == "<module>":
            func_name = "__main__"

        if event == "call":
            self._call_stack.append(func_name)
            return self._trace_dispatch

        if event == "line":
            snap = self._snap_locals(frame)
            self._steps.append(self._make_step(
                line=frame.f_lineno,
                event="line",
                locals_snap=snap,
            ))

        if event == "return":
            if self._call_stack:
                self._call_stack.pop()

        if event == "exception":
            exc_type, exc_val, _ = arg
            snap = self._snap_locals(frame)
            self._steps.append(self._make_step(
                line=frame.f_lineno,
                event="exception",
                locals_snap=snap,
                error=f"{exc_type.__name__}: {exc_val}",
            ))

        return self._trace_dispatch

    def _snap_locals(self, frame) -> dict:
        result = {}
        for k, v in frame.f_locals.items():
            if k.startswith("__"):
                continue
            try:
                r = repr(v)
                result[k] = r[:120] + ("…" if len(r) > 120 else "")
            except Exception:
                result[k] = "<unprintable>"
        return result

    def _make_step(self, line, event, locals_snap, error=None) -> dict:
        step = {
            "line": line,
            "event": event,
            "locals": locals_snap,
            "stack": list(self._call_stack),
            "stdout": self._stdout_buf.getvalue(),
        }
        if error:
            step["error"] = error
        return step
