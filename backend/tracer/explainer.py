"""
explainer.py
------------
Generates beginner-friendly, one-line explanations for each execution step.
Called by runner.py before sending the step list to the frontend.
"""
import re

# Variables that hold "result" type values (max, min, found, etc.)
_RESULT_VARS = {
    "max","min","result","ans","maximum","minimum","largest","smallest",
    "max_val","min_val","res","found","flag","count","total","sum",
    "product","output","target","key","val","value",
}

_LOOP_KW  = ("for ", "while ")
_COND_KW  = ("if ", "elif ")


def _strip(code_line: str) -> str:
    return code_line.strip() if code_line else ""


def _arr_diff(old_str: str, new_str: str):
    """Return human description of what changed between two list reprs, or None."""
    import ast
    try:
        o = ast.literal_eval(old_str)
        n = ast.literal_eval(new_str)
        if not (isinstance(o, list) and isinstance(n, list)): return None
        if len(o) != len(n): return None
        diff = [i for i in range(len(o)) if o[i] != n[i]]
        if len(diff) == 2 and o[diff[0]] == n[diff[1]] and o[diff[1]] == n[diff[0]]:
            a, b = diff
            return f"positions [{a}] and [{b}] were SWAPPED  ({o[a]} ↔ {o[b]})"
        if diff:
            return f"position[s] {diff} updated"
    except Exception:
        pass
    return None


def generate(step: dict, prev_step: dict | None, code_lines: list[str]) -> str:
    """Return a one-sentence beginner explanation for *step*."""
    line      = step.get("line", 0)
    event     = step.get("event", "line")
    error     = step.get("error") or ""
    locs      = step.get("locals", {}) or {}
    prev_locs = (prev_step.get("locals", {}) or {}) if prev_step else {}
    stack     = step.get("stack", []) or []
    stdout    = (step.get("stdout") or "").strip()
    prev_out  = ((prev_step.get("stdout", "") or "") if prev_step else "").strip()
    code_ln   = code_lines[line - 1] if 0 < line <= len(code_lines) else ""
    cl        = _strip(code_ln)

    # ── Error / exception ────────────────────────────────────────────────────
    if error:
        etype = error.split(":")[0] if ":" in error else "Error"
        emsg  = error.split(":", 1)[1].strip() if ":" in error else error
        return f"🔴 {etype} — {emsg}. Execution stopped here."

    if event == "exception":
        return f"⚠️ An exception occurred at line {line}. The program raised an error."

    # ── Function call / return ───────────────────────────────────────────────
    if event == "call":
        fn   = stack[-1] if stack else "the function"
        args = ", ".join(
            f"{k} = {v}" for k, v in locs.items()
            if not k.startswith("__")
        )
        if args:
            return f"📞 Calling  {fn}()  with arguments: {args}."
        return f"📞 Entering function  {fn}()."

    if event == "return":
        fn = stack[-1] if stack else "this function"
        return f"↩️ Returning from  {fn}()  — going back to the place it was called."

    # ── New output printed ───────────────────────────────────────────────────
    if stdout and stdout != prev_out:
        new_out = stdout[len(prev_out):].strip()
        return f"🖨️ Output printed: \"{new_out}\"."

    # ── Variable changes ─────────────────────────────────────────────────────
    changed = {}
    for k, v in locs.items():
        if k.startswith("__"): continue
        pv = prev_locs.get(k)
        if pv is None or str(pv) != str(v):
            changed[k] = (pv, v)

    if changed:
        # Prioritise result variables
        for k, (old, new) in changed.items():
            if k in _RESULT_VARS:
                old_s = str(old) if old is not None else "—"
                new_s = str(new)
                return (
                    f"✅ Variable  \"{k}\"  updated from {old_s} → {new_s}.  "
                    f"This is the new best value found so far."
                )

        # Detect array swap
        for k, (old, new) in changed.items():
            old_s = str(old) if old else ""
            new_s = str(new)
            diff = _arr_diff(old_s, new_s)
            if diff:
                return f"🔄 Array  \"{k}\"  changed — {diff}."

        # Generic variable change
        items = list(changed.items())[:2]
        parts = []
        for k, (old, new) in items:
            old_s = str(old) if old is not None else "not yet set"
            parts.append(f"\"{k}\" is now {new}  (was {old_s})")
        return "📝 " + ";   ".join(parts) + "."

    # ── Code-line based explanation ───────────────────────────────────────────
    if any(cl.startswith(kw) for kw in _COND_KW):
        cond = re.sub(r'^(if|elif)\s+', '', cl).rstrip(':')
        return f"🔍 Checking condition:  {cond}  — is this True or False?"

    if cl.startswith("else"):
        return "↪️ The condition above was False, so we take the else branch."

    if any(cl.startswith(kw) for kw in _LOOP_KW):
        return f"🔄 Loop step:  {cl}  — iterating to the next value."

    if cl.startswith("return "):
        val = cl.removeprefix("return").strip()
        return f"↩️ Returning the value:  {val}."

    if "print(" in cl or "cout" in cl or "printf" in cl or "console.log" in cl:
        return "🖨️ This line prints output to the console."

    if "=" in cl and "==" not in cl and "!=" not in cl and "<=" not in cl and ">=" not in cl:
        return f"📌 Assignment:  {cl}  — storing a value into a variable."

    return f"▶️ Executing line {line}: {cl or '...'}"
