"""
js_tracer.py
Instruments JavaScript code (via Python-side AST-free line injection)
and runs it with Node.js to capture step-by-step execution traces.
"""
import subprocess
import json
import os
import tempfile


# ---------------------------------------------------------------------------
# JavaScript preamble injected before every user script
# ---------------------------------------------------------------------------
_JS_PREAMBLE = r"""
var __trace_steps = [];
var __trace_stdout = '';

function __t(line) {
    __trace_steps.push({
        line: line,
        event: 'line',
        locals: {},
        stack: ['<script>'],
        stdout: __trace_stdout
    });
}

// Override console so we capture output
var __orig_console = console;
var console = {
    log: function() {
        var msg = Array.prototype.slice.call(arguments).map(function(a) {
            try { return typeof a === 'object' ? JSON.stringify(a) : String(a); }
            catch(e) { return String(a); }
        }).join(' ');
        __trace_stdout += msg + '\n';
        if (__trace_steps.length > 0) {
            __trace_steps[__trace_steps.length - 1].stdout = __trace_stdout;
        }
    },
    error: function() {
        __trace_stdout += '[error] ' + Array.prototype.slice.call(arguments).join(' ') + '\n';
    },
    warn: function() {
        __trace_stdout += '[warn] ' + Array.prototype.slice.call(arguments).join(' ') + '\n';
    },
    info: function() {
        console.log.apply(console, arguments);
    }
};
"""

_JS_EPILOGUE = "\nprocess.stdout.write(JSON.stringify(__trace_steps));\n"

# Lines that are not worth stepping into (pure structure tokens)
_SKIP_LINES = {"", "{", "}", "};", "});", ")", "};", "//", "/*", "*", "*/"}


class JSTracer:
    def trace(self, code: str) -> list[dict]:
        instrumented = self._instrument(code)

        fd, tmpfile = tempfile.mkstemp(suffix=".js", prefix="trace_js_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(instrumented)

            result = subprocess.run(
                ["node", tmpfile],
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
            )
        except FileNotFoundError:
            return [self._err_step(1, "Node.js is not installed. Please install Node.js to trace JavaScript code.")]
        except subprocess.TimeoutExpired:
            return [self._err_step(1, "JavaScript execution timed out (15 s).")]
        finally:
            try:
                os.unlink(tmpfile)
            except OSError:
                pass

        # Parse JSON output from the instrumented script
        stdout = result.stdout.strip()
        if stdout:
            try:
                steps = json.loads(stdout)
                if isinstance(steps, list) and steps:
                    return steps
            except json.JSONDecodeError:
                pass

        # If stderr has content, surface it as an error step
        stderr = result.stderr.strip()
        if stderr:
            line = self._extract_node_lineno(stderr)
            return [self._err_step(line, stderr.split("\n")[0])]

        return [self._err_step(1, "No execution steps captured.")]

    # ----------------------------------------------------------------- private
    def _instrument(self, code: str) -> str:
        lines = code.split("\n")
        instrumented_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            lineno = i + 1

            # Inject __t(N) before meaningful lines
            if stripped and not stripped.startswith("//") and stripped not in _SKIP_LINES:
                instrumented_lines.append(f"try {{ __t({lineno}); }} catch(_te) {{}}")

            instrumented_lines.append(line)

        return _JS_PREAMBLE + "\n".join(instrumented_lines) + _JS_EPILOGUE

    def _err_step(self, line: int, error: str) -> dict:
        return {
            "line": line,
            "event": "error",
            "error": error,
            "locals": {},
            "stack": ["<script>"],
            "stdout": "",
        }

    def _extract_node_lineno(self, stderr: str) -> int:
        import re
        m = re.search(r":(\d+)$", stderr.split("\n")[0])
        if m:
            return int(m.group(1))
        return 1
