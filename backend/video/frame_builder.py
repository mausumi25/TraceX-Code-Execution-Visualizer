"""
frame_builder.py  —  Whiteboard Dry-Run Visualizer
====================================================
Generates educational algorithm walkthrough videos — NOT screen recordings.

Each frame looks like a teacher's whiteboard explanation:
  • Large array boxes in the centre
  • Compared elements shown face-to-face with a VS badge
  • Swap shown with swapped positions in orange + arrows
  • Result/assignment shown with big text
  • NO code panel in the main view — pure visual storytelling

Layout (1280 × 720)
-------------------
┌──────────────────────────────────────────────────────────────┐
│  HEADER  ⟨trace⟩  [lang]  Algorithm Name   Step N/T  [event] │  60 px
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ARRAY  (large boxes, coloured by state)                    │  280 px
│   indices above  |  pointer arrows below                     │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  OPERATION PANEL  — face-to-face comparison / swap / result  │  230 px
│  Large readable text: "Is 34 > 25? YES! → SWAP"             │
├──────────────────────────────────────────────────────────────┤
│  VARIABLES STRIP  —  key vars (max=8, i=3 …)   compact       │  150 px
└──────────────────────────────────────────────────────────────┘
"""
import os
import re
import ast
import tempfile
from enum import Enum
from PIL import Image, ImageDraw, ImageFont


# ── Dimensions ────────────────────────────────────────────────────────────────
FRAME_W  = 1280
FRAME_H  = 720
HEADER_H = 60
ARRAY_H  = 280      # array visualization zone
OP_H     = 230      # operation panel
VAR_H    = FRAME_H - HEADER_H - ARRAY_H - OP_H   # ≈ 150 px

# ── Colour palette ─────────────────────────────────────────────────────────────
BG          = (12,  16,  24)
HEADER_BG   = (16,  20,  32)
ARRAY_BG    = (14,  18,  28)
OP_BG       = (18,  22,  34)
VAR_BG      = (16,  20,  30)
BORDER      = (36,  46,  60)
PANEL_LINE  = (30,  40,  55)

TEXT        = (218, 228, 242)
TEXT2       = (140, 155, 175)
TEXT_DIM    = (65,  78,  95)
TEXT_WHITE  = (255, 255, 255)

# Box states (fill, border)
BOX_DEFAULT = ((25,  50,  95),   (52,  98, 182))   # blue — untouched
BOX_CURRENT = ((36,  72, 130),   (78, 138, 228))   # brighter blue — pointer on it
BOX_COMPARE = ((160, 128,  14),  (238, 192,  26))  # yellow — being compared
BOX_SWAP    = ((162,  70,  10),  (238, 118,  28))  # orange — being swapped
BOX_SORTED  = (( 16, 104,  52),  ( 36, 180,  96))  # green — sorted / found / result
BOX_FOUND   = ((  8, 130,  60),  ( 28, 215, 110))  # bright green — FOUND!
BOX_ELIM    = (( 20,  28,  40),  ( 35,  45,  58))  # dim — eliminated / checked
BOX_ERROR   = ((138,  16,  16),  (236,  52,  52))  # red — error

# Pointer arrow colours
PTR_COLORS = {
    "i": (255, 210, 40), "j": (255, 140, 40), "k": (200, 100, 240),
    "l": (60, 150, 255),  "r": (248, 80, 80),
    "low": (56, 145, 255), "high": (248, 81, 73), "mid": (188, 140, 228),
    "left": (56, 145, 255), "right": (248, 81, 73),
    "start": (56, 145, 255), "end": (248, 81, 73),
    "pivot": (200, 60, 220),
    "slow": (63, 185, 80), "fast": (79, 197, 232),
    "p": (255, 210, 40), "q": (255, 140, 40),
    "curr": (63, 185, 80), "prev": (60, 150, 255),
    "ans": (63, 185, 80), "pos": (255, 210, 40), "idx": (255, 210, 40),
    "min_idx": (63, 185, 80), "max_idx": (248, 81, 73),
}

# Result / accumulator variable names
_RESULT_VARS = {
    "max", "min", "result", "ans", "maximum", "minimum",
    "largest", "smallest", "max_val", "min_val", "res",
    "found", "flag", "count", "total", "sum", "product",
    "target", "output",
}

# Accent colours
AC_CYAN   = (79,  197, 232)
AC_BLUE   = (56,  139, 253)
AC_GREEN  = (63,  185,  80)
AC_RED    = (248,  81,  73)
AC_ORANGE = (210, 153,  34)
AC_PURPLE = (188, 140, 228)
AC_YELLOW = (255, 215,  50)

LANG_COLORS = {
    "PYTHON": (55, 118, 171), "JAVASCRIPT": (200, 160, 0),
    "C": (85, 170, 211),      "CPP": (0, 150, 136), "JAVA": (248, 152, 32),
}
BADGE_OK  = (35,  134,  54)
BADGE_EXC = (187, 128,   9)
BADGE_ERR = (218,  54,  51)

KEYWORDS = {
    "def","class","return","if","else","elif","for","while","import","from",
    "in","not","and","or","True","False","None","try","except","finally",
    "with","as","pass","break","continue","lambda","print","int","float",
    "double","char","void","printf","cout","cin","endl","using","namespace",
    "std","include","vector","string","map","set","queue","stack",
    "var","let","const","function","new","this",
}


# ── Font helpers ──────────────────────────────────────────────────────────────
def _load_font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        paths = [
            "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf",
            "/System/Library/Fonts/Monaco.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]
    else:
        paths = [
            "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


def _tw(draw, text, font) -> int:
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[2] - b[0]
    except AttributeError:
        w, _ = draw.textsize(text, font=font)
        return w


def _th(draw, text, font) -> int:
    try:
        b = draw.textbbox((0, 0), text, font=font)
        return b[3] - b[1]
    except AttributeError:
        _, h = draw.textsize(text, font=font)
        return h


def _rrect(draw, box, radius=8, **kw):
    try:
        draw.rounded_rectangle(box, radius=radius, **kw)
    except AttributeError:
        draw.rectangle(box, **kw)


def _parse_num_list(v_str: str):
    s = re.sub(r'[…\.]{2,}', '', str(v_str)).strip()
    if not (s.startswith('[') and s.endswith(']')):
        return None
    try:
        r = ast.literal_eval(s)
        if isinstance(r, list) and all(isinstance(x, (int, float)) for x in r):
            return r
    except Exception:
        pass
    return None


def _safe_int(v_str: str):
    try:
        return int(ast.literal_eval(str(v_str).strip()))
    except Exception:
        return None


# ── Algorithm name detection ──────────────────────────────────────────────────
def _detect_algorithm(code_lines):
    code = "\n".join(code_lines).lower()
    if "bubble"   in code:                              return "Bubble Sort"
    if "selection"in code and "sort" in code:           return "Selection Sort"
    if "insertion"in code and "sort" in code:           return "Insertion Sort"
    if "merge"    in code and "sort" in code:           return "Merge Sort"
    if "quick"    in code and ("sort" in code or "partition" in code): return "Quick Sort"
    if "heap"     in code and "sort" in code:           return "Heap Sort"
    if re.search(r'\bsort\b', code):                    return "Sorting Algorithm"
    if "binary"   in code and "search" in code:         return "Binary Search"
    if "linear"   in code and "search" in code:         return "Linear Search"
    if re.search(r'\bsearch\b', code):                  return "Search Algorithm"
    if "two" in code and "pointer" in code:             return "Two Pointer"
    if "sliding"  in code and "window" in code:         return "Sliding Window"
    if "largest"  in code or "maximum" in code or "max" in code: return "Find Maximum"
    if "smallest" in code or "minimum" in code or "min" in code: return "Find Minimum"
    if "fibonacci"in code or re.search(r'\bfib\b', code): return "Fibonacci"
    if "palindrome"in code:                             return "Palindrome Check"
    if "bfs"      in code:                              return "BFS"
    if "dfs"      in code:                              return "DFS"
    if re.search(r'\bdp\b', code) or "dynamic" in code: return "Dynamic Programming"
    return "Algorithm Execution"


# ── Operation types ───────────────────────────────────────────────────────────
class OpType(Enum):
    INIT      = "init"
    COMPARE   = "compare"
    SWAP      = "swap"
    UPDATE    = "update"
    VISIT     = "visit"
    FOUND     = "found"
    ERROR     = "error"
    OTHER     = "other"


# ── Main class ────────────────────────────────────────────────────────────────
class FrameBuilder:
    def __init__(self, code_lines: list, language: str = "python"):
        self.code_lines  = code_lines
        self.language    = language.upper()
        self.algo_name   = _detect_algorithm(code_lines)

        # Fonts  (loaded once)
        self.f_hdr   = _load_font(15)           # header
        self.f_algo  = _load_font(18)           # algorithm name
        self.f_lbl   = _load_font(11)           # small label
        self.f_idx   = _load_font(12)           # index numbers above boxes
        self.f_ptr   = _load_font(11)           # pointer labels below arrows
        self.f_op    = _load_font(22)           # operation main text
        self.f_op_sm = _load_font(16)           # operation secondary text
        self.f_vs    = _load_font(28)           # "VS" badge
        self.f_var   = _load_font(13)           # variable strip
        self.f_var_k = _load_font(13, mono=True)# variable key (monospace)
        self.f_box   = {                        # value text inside boxes
            "xl": _load_font(26, mono=True),
            "lg": _load_font(20, mono=True),
            "md": _load_font(15, mono=True),
            "sm": _load_font(11, mono=True),
        }

        self.temp_dir  = tempfile.mkdtemp(prefix="trace_frames_")
        self._prev     = None          # previous step dict
        self._sorted   : set = set()  # confirmed-sorted indices

    # ── Public API ────────────────────────────────────────────────────────────
    def build_frames(self, steps: list, has_runtime_error: bool = False,
                     runtime_error_msg: str = None) -> list:
        self._prev   = None
        self._sorted = set()
        paths = []
        for i, s in enumerate(steps):
            paths.append(self._frame(s, i + 1, len(steps)))
            self._prev = s
        if has_runtime_error and runtime_error_msg:
            paths.append(self._error_frame(runtime_error_msg, len(steps) + 1))
        return paths

    # ── Build one frame ───────────────────────────────────────────────────────
    def _frame(self, step: dict, num: int, total: int) -> str:
        img  = Image.new("RGB", (FRAME_W, FRAME_H), BG)
        draw = ImageDraw.Draw(img)

        self._draw_header(draw, step, num, total)

        locs = step.get("locals", {}) or {}

        # Find main numeric array
        arr_name, arr = self._find_main_array(locs)

        if arr is not None:
            # Find pointer variables
            pointers = self._find_pointers(locs, arr_name, len(arr))
            # Determine operation
            op = self._infer_op(step, arr_name, arr, pointers)
            # Draw zones
            self._draw_array_zone(draw, arr_name, arr, pointers, op)
            self._draw_op_panel(draw, arr, pointers, op, step)
        else:
            # Fallback: code walk view
            op = {"type": OpType.OTHER, "desc": f"Line {step.get('line','?')}",
                  "hi": set(), "swap": set()}
            self._draw_code_fallback(draw, step)
            self._draw_op_panel_simple(draw,
                f"Executing line {step.get('line','?')} …", step)

        self._draw_var_strip(draw, step, arr_name)

        # Zone dividers
        y1 = HEADER_H + ARRAY_H
        y2 = y1 + OP_H
        draw.rectangle([0, y1, FRAME_W, y1 + 1], fill=PANEL_LINE)
        draw.rectangle([0, y2, FRAME_W, y2 + 1], fill=PANEL_LINE)

        path = os.path.join(self.temp_dir, f"frame_{num:04d}.png")
        img.save(path, "PNG", optimize=False)
        return path

    # ── Header ────────────────────────────────────────────────────────────────
    def _draw_header(self, draw, step, num, total):
        draw.rectangle([0, 0, FRAME_W, HEADER_H], fill=HEADER_BG)
        draw.rectangle([0, HEADER_H-1, FRAME_W, HEADER_H], fill=BORDER)
        # Logo
        draw.text((18, 16), "\u27e8trace\u27e9", fill=AC_CYAN, font=self.f_hdr)
        # Lang badge
        lc = LANG_COLORS.get(self.language, AC_BLUE)
        lw = _tw(draw, self.language, self.f_lbl) + 16
        _rrect(draw, [108, 17, 108+lw, HEADER_H-17], radius=4, fill=lc)
        draw.text((116, 19), self.language, fill=(255,255,255), font=self.f_lbl)
        # Algo name
        draw.text((108+lw+14, 17), self.algo_name, fill=AC_PURPLE, font=self.f_hdr)
        # Step counter (centre)
        sc  = f"Step  {num} / {total}"
        scw = _tw(draw, sc, self.f_hdr)
        draw.text(((FRAME_W-scw)//2, 17), sc, fill=TEXT, font=self.f_hdr)
        # Event badge (right)
        event   = step.get("event", "line")
        has_err = bool(step.get("error"))
        bc, bt  = ((BADGE_ERR, "ERROR") if (event == "error" or has_err)
                   else (BADGE_EXC, "EXCEPTION") if event == "exception"
                   else (BADGE_OK,  "EXECUTING"))
        bw = _tw(draw, bt, self.f_lbl) + 20
        bx = FRAME_W - bw - 16
        _rrect(draw, [bx, 17, bx+bw, HEADER_H-17], radius=4, fill=bc)
        draw.text((bx+10, 19), bt, fill=(255,255,255), font=self.f_lbl)

    # ── Find main array ───────────────────────────────────────────────────────
    def _find_main_array(self, locs):
        best_name, best = None, None
        for k, v in locs.items():
            parsed = _parse_num_list(str(v))
            if parsed is not None and len(parsed) >= 2:
                if best is None or len(parsed) > len(best):
                    best_name, best = k, parsed
        return best_name, best

    # ── Find pointer variables ────────────────────────────────────────────────
    def _find_pointers(self, locs, arr_name, arr_len):
        ptrs = {}
        for var, color in PTR_COLORS.items():
            if var in locs and var != arr_name:
                iv = _safe_int(str(locs[var]))
                if iv is not None and 0 <= iv < arr_len:
                    ptrs[var] = (iv, color)
        return ptrs

    # ── Infer semantic operation ──────────────────────────────────────────────
    def _infer_op(self, step, arr_name, arr, pointers):
        locs      = step.get("locals", {}) or {}
        prev_locs = (self._prev.get("locals", {}) or {}) if self._prev else {}
        n         = len(arr)
        has_err   = bool(step.get("error"))

        if has_err:
            return {"type": OpType.ERROR, "desc": step.get("error",""),
                    "hi": set(), "swap": set(), "compare": None}

        # --- SWAP detection -------------------------------------------------
        if arr_name in prev_locs:
            prev_arr = _parse_num_list(str(prev_locs[arr_name]))
            if prev_arr and len(prev_arr) == n:
                diff = [i for i in range(n) if arr[i] != prev_arr[i]]
                if len(diff) == 2:
                    a, b = diff[0], diff[1]
                    if arr[a] == prev_arr[b] and arr[b] == prev_arr[a]:
                        desc = (f"\U0001f504  SWAP!  "
                                f"arr[{a}] = {_fmt(arr[a])}  \u21c4  arr[{b}] = {_fmt(arr[b])}")
                        return {"type": OpType.SWAP,
                                "desc": desc,
                                "hi": set(diff), "swap": set(diff), "compare": None}

        # --- RESULT variable UPDATE detection --------------------------------
        for var in _RESULT_VARS:
            if var in locs and var in prev_locs:
                prev_v = str(prev_locs[var]).strip()
                curr_v = str(locs[var]).strip()
                if prev_v != curr_v:
                    # Find index of new value in array (for highlighting)
                    try:
                        new_val  = ast.literal_eval(curr_v)
                        hi_idx   = {i for i, x in enumerate(arr) if x == new_val}
                    except Exception:
                        hi_idx   = set()
                    desc = (f"\u2705  Update:  {var}  =  {curr_v}  "
                            f"\u2190  was {prev_v}")
                    return {"type": OpType.UPDATE,
                            "desc": desc,
                            "hi": hi_idx, "swap": set(), "compare": None}

        # --- COMPARISON detection (2+ pointers at different positions) -------
        ptr_positions = {idx for idx, _ in pointers.values()}
        if len(ptr_positions) >= 2:
            idxs = sorted(ptr_positions)
            a, b = idxs[0], idxs[1]
            if 0 <= a < n and 0 <= b < n:
                va, vb = arr[a], arr[b]
                cmp_str = (f"arr[{a}] = {_fmt(va)}   vs   arr[{b}] = {_fmt(vb)}")
                return {"type": OpType.COMPARE,
                        "desc": cmp_str,
                        "hi": {a, b}, "swap": set(),
                        "compare": (a, va, b, vb)}

        # --- SINGLE pointer VISIT -------------------------------------------
        if pointers:
            a = min(idx for idx, _ in pointers.values())
            desc = f"Visiting  arr[{a}] = {_fmt(arr[a])}"
            return {"type": OpType.VISIT,
                    "desc": desc,
                    "hi": {a}, "swap": set(), "compare": None}

        # --- INIT -----------------------------------------------------------
        desc = f"Array loaded:  {len(arr)} elements"
        return {"type": OpType.INIT, "desc": desc,
                "hi": set(), "swap": set(), "compare": None}

    # ── Array zone ────────────────────────────────────────────────────────────
    def _draw_array_zone(self, draw, arr_name, arr, pointers, op):
        n   = len(arr)
        y0  = HEADER_H
        y1  = HEADER_H + ARRAY_H
        draw.rectangle([0, y0, FRAME_W, y1], fill=ARRAY_BG)

        # Title
        title = self.algo_name
        tw = _tw(draw, title, self.f_algo)
        draw.text(((FRAME_W-tw)//2, y0+10), title, fill=AC_CYAN, font=self.f_algo)

        # Array label
        lbl = f"{ arr_name }  [ length = {n} ]"
        lw  = _tw(draw, lbl, self.f_lbl)
        draw.text(((FRAME_W-lw)//2, y0+38), lbl, fill=TEXT2, font=self.f_lbl)

        # Box geometry
        MAX_W   = FRAME_W - 120
        GAP     = 8
        raw_bw  = (MAX_W - (n-1)*GAP) // n
        box_w   = max(38, min(100, raw_bw))
        box_h   = max(60, min(100, int(box_w * 0.95)))
        total_w = n*box_w + (n-1)*GAP
        sx      = (FRAME_W - total_w) // 2
        sy      = y0 + 60                       # top of boxes

        hi_set   = op.get("hi",   set())
        swap_set = op.get("swap", set())
        ptr_idx  = {idx for idx, _ in pointers.values()}

        # Pick value font
        if box_w >= 80:  vf = self.f_box["xl"]
        elif box_w >= 60: vf = self.f_box["lg"]
        elif box_w >= 46: vf = self.f_box["md"]
        else:             vf = self.f_box["sm"]

        # Index numbers ABOVE boxes
        for idx in range(n):
            bx = sx + idx*(box_w+GAP)
            s  = str(idx)
            sw = _tw(draw, s, self.f_idx)
            draw.text((bx+(box_w-sw)//2, sy-18), s, fill=TEXT_DIM, font=self.f_idx)

        # Boxes
        for idx in range(n):
            bx = sx + idx*(box_w+GAP)
            by = sy

            # Choose colour
            if op["type"] == OpType.ERROR and idx in ptr_idx:
                fill, bdr = BOX_ERROR
            elif idx in swap_set:
                fill, bdr = BOX_SWAP
            elif idx in self._sorted:
                fill, bdr = BOX_SORTED
            elif idx in hi_set and len(hi_set) >= 2:
                fill, bdr = BOX_COMPARE
            elif idx in hi_set:
                fill, bdr = BOX_CURRENT
            else:
                fill, bdr = BOX_DEFAULT

            _rrect(draw, [bx, by, bx+box_w, by+box_h], radius=8, fill=fill)
            _rrect(draw, [bx, by, bx+box_w, by+box_h], radius=8, outline=bdr, width=2)

            v  = arr[idx]
            vs = str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
            if len(vs) > 5: vs = vs[:4]+"\u2026"
            vw = _tw(draw, vs, vf)
            vh = _th(draw, vs, vf)
            draw.text((bx+(box_w-vw)//2, by+(box_h-vh)//2),
                      vs, fill=TEXT_WHITE, font=vf)

        # Pointer arrows BELOW boxes
        arrow_y = sy + box_h + 8
        layers  = {}
        for var, (idx, color) in pointers.items():
            layers.setdefault(idx, []).append((var, color))

        for idx, entries in layers.items():
            bx    = sx + idx*(box_w+GAP)
            mid_x = bx + box_w//2
            for li, (var, color) in enumerate(entries):
                ay = arrow_y + li*28
                # Triangle up
                draw.polygon([(mid_x, ay), (mid_x-7, ay+14), (mid_x+7, ay+14)],
                             fill=color)
                draw.rectangle([mid_x-1, ay+14, mid_x+1, ay+20], fill=color)
                lw2 = _tw(draw, var, self.f_ptr)
                draw.text((mid_x-lw2//2, ay+22), var, fill=color, font=self.f_ptr)

        # Colour legend (small, bottom of array zone)
        legend = [
            (BOX_DEFAULT[0], "Default"),
            (BOX_COMPARE[0], "Comparing"),
            (BOX_SWAP[0],    "Swapped"),
            (BOX_SORTED[0],  "Sorted"),
            (BOX_FOUND[0],   "Found"),
        ]
        lx = 60
        ly2 = y1 - 24
        for fc, lt in legend:
            _rrect(draw, [lx, ly2+1, lx+13, ly2+13], radius=3, fill=fc)
            draw.text((lx+17, ly2), lt, fill=TEXT_DIM, font=self.f_lbl)
            lx += _tw(draw, lt, self.f_lbl) + 36

    # ── Operation panel ───────────────────────────────────────────────────────
    def _draw_op_panel(self, draw, arr, pointers, op, step):
        y0 = HEADER_H + ARRAY_H
        y1 = y0 + OP_H
        draw.rectangle([0, y0, FRAME_W, y1], fill=OP_BG)

        ot  = op["type"]
        cmp = op.get("compare")   # (a, va, b, vb) or None

        if ot == OpType.COMPARE and cmp:
            self._draw_comparison(draw, y0, y1, cmp, arr, step)
        elif ot == OpType.SWAP:
            self._draw_swap_panel(draw, y0, y1, op, arr)
        elif ot == OpType.UPDATE:
            self._draw_update_panel(draw, y0, y1, op)
        elif ot == OpType.FOUND:
            self._draw_found_panel(draw, y0, y1, op)
        elif ot == OpType.ERROR:
            self._draw_error_panel_inline(draw, y0, y1, op)
        else:
            # INIT / VISIT / OTHER — show description centred
            desc = op.get("desc", "")
            dw   = _tw(draw, desc, self.f_op)
            dy   = y0 + (OP_H - _th(draw, desc, self.f_op))//2
            draw.text(((FRAME_W-dw)//2, dy), desc, fill=AC_CYAN, font=self.f_op)

    def _draw_comparison(self, draw, y0, y1, cmp, arr, step):
        """Draw face-to-face comparison: big box A  vs  big box B  with result."""
        a_idx, a_val, b_idx, b_val = cmp
        cx = FRAME_W // 2
        box_size = 90
        gap      = 160    # gap between the two boxes

        ax = cx - gap//2 - box_size
        bx = cx + gap//2
        by = y0 + 22

        # Draw box A (yellow)
        _rrect(draw, [ax, by, ax+box_size, by+box_size], radius=10,
               fill=BOX_COMPARE[0])
        _rrect(draw, [ax, by, ax+box_size, by+box_size], radius=10,
               outline=BOX_COMPARE[1], width=3)
        av = str(int(a_val)) if isinstance(a_val, float) and a_val.is_integer() else str(a_val)
        aw = _tw(draw, av, self.f_box["xl"])
        ah = _th(draw, av, self.f_box["xl"])
        draw.text((ax+(box_size-aw)//2, by+(box_size-ah)//2),
                  av, fill=TEXT_WHITE, font=self.f_box["xl"])
        # sub-label
        al = f"arr[{a_idx}]"
        alw = _tw(draw, al, self.f_lbl)
        draw.text((ax+(box_size-alw)//2, by+box_size+4), al, fill=AC_YELLOW, font=self.f_lbl)

        # VS badge
        vs = "VS"
        vsw = _tw(draw, vs, self.f_vs)
        draw.text((cx-vsw//2, by+(box_size-_th(draw,vs,self.f_vs))//2),
                  vs, fill=TEXT_DIM, font=self.f_vs)

        # Draw box B (yellow)
        _rrect(draw, [bx, by, bx+box_size, by+box_size], radius=10,
               fill=BOX_COMPARE[0])
        _rrect(draw, [bx, by, bx+box_size, by+box_size], radius=10,
               outline=BOX_COMPARE[1], width=3)
        bv = str(int(b_val)) if isinstance(b_val, float) and b_val.is_integer() else str(b_val)
        bvw = _tw(draw, bv, self.f_box["xl"])
        bvh = _th(draw, bv, self.f_box["xl"])
        draw.text((bx+(box_size-bvw)//2, by+(box_size-bvh)//2),
                  bv, fill=TEXT_WHITE, font=self.f_box["xl"])
        bl = f"arr[{b_idx}]"
        blw = _tw(draw, bl, self.f_lbl)
        draw.text((bx+(box_size-blw)//2, by+box_size+4), bl, fill=AC_YELLOW, font=self.f_lbl)

        # Comparison question
        q  = f"Is  {_fmt(a_val)}  >  {_fmt(b_val)} ?"
        qw = _tw(draw, q, self.f_op)
        draw.text(((FRAME_W-qw)//2, by+box_size+28), q, fill=TEXT, font=self.f_op)

        # Code line hint (what happens on true/false)
        line_code = ""
        cur_line  = step.get("line", 1)
        if 0 < cur_line <= len(self.code_lines):
            line_code = self.code_lines[cur_line-1].strip()
        if line_code:
            lc_text = f"\u25b6  {line_code}"
            lcw     = _tw(draw, lc_text, self.f_op_sm)
            draw.text(((FRAME_W-lcw)//2, by+box_size+64),
                      lc_text, fill=TEXT2, font=self.f_op_sm)

    def _draw_swap_panel(self, draw, y0, y1, op, arr):
        """Show before→after swap with arrows."""
        cx  = FRAME_W // 2
        bsz = 80
        gap = 140
        by  = y0 + 18

        # Icon + title row
        title = "\U0001f504  SWAP!"
        tw    = _tw(draw, title, self.f_op)
        draw.text(((FRAME_W-tw)//2, by), title, fill=AC_ORANGE, font=self.f_op)
        by += 50

        # Extract swapped indices from desc
        desc = op.get("desc", "")
        idxs = re.findall(r'arr\[(\d+)\]', desc)
        if len(idxs) >= 2:
            a_idx, b_idx = int(idxs[0]), int(idxs[1])
            ax = cx - gap//2 - bsz
            bx = cx + gap//2

            for (ix, xbx) in ((a_idx, ax), (b_idx, bx)):
                v  = arr[ix]
                vs = str(int(v)) if isinstance(v,float) and v.is_integer() else str(v)
                _rrect(draw, [xbx, by, xbx+bsz, by+bsz], radius=8,
                       fill=BOX_SWAP[0])
                _rrect(draw, [xbx, by, xbx+bsz, by+bsz], radius=8,
                       outline=BOX_SWAP[1], width=3)
                vw = _tw(draw, vs, self.f_box["xl"])
                vh = _th(draw, vs, self.f_box["xl"])
                draw.text((xbx+(bsz-vw)//2, by+(bsz-vh)//2),
                          vs, fill=TEXT_WHITE, font=self.f_box["xl"])

            # Double arrow ↔
            mid_y = by + bsz//2
            for mx in range(ax+bsz+8, bx-8, 4):
                draw.point((mx, mid_y), fill=AC_ORANGE)
            arrow = "\u21c4"
            arw   = _tw(draw, arrow, self.f_vs)
            draw.text((cx-arw//2, mid_y-14), arrow, fill=AC_ORANGE, font=self.f_vs)

        # Description
        dw = _tw(draw, desc, self.f_op_sm)
        draw.text(((FRAME_W-dw)//2, by+bsz+12), desc, fill=AC_ORANGE, font=self.f_op_sm)

    def _draw_update_panel(self, draw, y0, y1, op):
        cx  = FRAME_W // 2
        by  = y0 + 30
        ic  = "\u2705"
        iw  = _tw(draw, ic, self.f_op)
        draw.text((cx-iw//2, by), ic, fill=AC_GREEN, font=self.f_op)
        by += 48

        desc = op.get("desc", "")
        # Split on arrow for two-line display
        parts = desc.replace("\u2705","").strip().split("\u2190")
        main_txt = parts[0].strip()
        sub_txt  = ("\u2190 " + parts[1].strip()) if len(parts) > 1 else ""

        mw = _tw(draw, main_txt, self.f_op)
        draw.text(((FRAME_W-mw)//2, by), main_txt, fill=AC_GREEN, font=self.f_op)

        if sub_txt:
            sw = _tw(draw, sub_txt, self.f_op_sm)
            draw.text(((FRAME_W-sw)//2, by+38), sub_txt, fill=TEXT2, font=self.f_op_sm)

    def _draw_found_panel(self, draw, y0, y1, op):
        cx = FRAME_W // 2
        t  = "\U0001f3af  FOUND!"
        tw = _tw(draw, t, self.f_op)
        draw.text(((FRAME_W-tw)//2, y0+40), t, fill=AC_GREEN, font=self.f_op)
        desc = op.get("desc","")
        dw   = _tw(draw, desc, self.f_op_sm)
        draw.text(((FRAME_W-dw)//2, y0+90), desc, fill=TEXT, font=self.f_op_sm)

    def _draw_error_panel_inline(self, draw, y0, y1, op):
        t   = "\u26a0  Runtime Error"
        tw  = _tw(draw, t, self.f_op)
        draw.text(((FRAME_W-tw)//2, y0+28), t, fill=AC_RED, font=self.f_op)
        err = op.get("desc","")
        ew  = _tw(draw, err[:80], self.f_op_sm)
        draw.text(((FRAME_W-ew)//2, y0+74), err[:80], fill=AC_ORANGE, font=self.f_op_sm)

    # ── Simple op panel for fallback view ─────────────────────────────────────
    def _draw_op_panel_simple(self, draw, msg, step):
        y0 = HEADER_H + ARRAY_H
        draw.rectangle([0, y0, FRAME_W, y0+OP_H], fill=OP_BG)
        mw = _tw(draw, msg, self.f_op)
        draw.text(((FRAME_W-mw)//2, y0+(OP_H-_th(draw,msg,self.f_op))//2),
                  msg, fill=AC_CYAN, font=self.f_op)

    # ── Code fallback (no array found) ────────────────────────────────────────
    def _draw_code_fallback(self, draw, step):
        y0  = HEADER_H
        y1  = HEADER_H + ARRAY_H
        draw.rectangle([0, y0, FRAME_W, y1], fill=(16, 20, 30))

        # Title
        tw = _tw(draw, self.algo_name, self.f_algo)
        draw.text(((FRAME_W-tw)//2, y0+10), self.algo_name, fill=AC_CYAN, font=self.f_algo)

        cur     = step.get("line", 0)
        has_err = bool(step.get("error"))
        f_code  = _load_font(14, mono=True)
        f_lbl2  = _load_font(11, mono=True)
        cw      = max(1, _tw(draw, "W", f_code))
        lh      = 22
        gw      = 52
        cx0     = 60
        cy0     = y0 + 46

        avail_h = (y1-10) - cy0
        max_vis = avail_h // lh
        half    = max_vis // 2
        start_l = max(0, cur-1-half)
        end_l   = min(len(self.code_lines), start_l+max_vis)

        draw.rectangle([cx0, cy0, cx0+gw, y1-10], fill=(18,22,30))

        for rel, li in enumerate(range(start_l, end_l)):
            lineno = li+1
            raw    = self.code_lines[li] if li < len(self.code_lines) else ""
            ly     = cy0 + rel*lh
            if lineno == cur:
                hl = (58,24,24) if has_err else (24,54,36)
                draw.rectangle([cx0, ly-1, FRAME_W-60, ly+lh-2], fill=hl)
                ac = AC_RED if has_err else AC_GREEN
                draw.rectangle([cx0, ly-1, cx0+4, ly+lh-2], fill=ac)
            ln_s = str(lineno)
            lnw  = _tw(draw, ln_s, f_lbl2)
            draw.text((cx0+gw-lnw-6, ly), ln_s,
                      fill=AC_BLUE if lineno==cur else TEXT_DIM, font=f_lbl2)
            if lineno == cur:
                draw.text((cx0+gw+4, ly), "\u25b6",
                          fill=AC_RED if has_err else AC_GREEN, font=f_code)
            tx      = cx0+gw+22
            max_c   = max(1, (FRAME_W-120-tx)//cw)
            display = raw.expandtabs(4)[:max_c]
            self._syn(draw, tx, ly, display, f_code)

    # ── Variables strip ───────────────────────────────────────────────────────
    def _draw_var_strip(self, draw, step, arr_name):
        y0  = HEADER_H + ARRAY_H + OP_H
        y1  = FRAME_H
        draw.rectangle([0, y0, FRAME_W, y1], fill=VAR_BG)

        lbl = "Variables"
        draw.text((20, y0+8), lbl, fill=TEXT_DIM, font=self.f_lbl)
        draw.rectangle([0, y0+24, FRAME_W, y0+25], fill=PANEL_LINE)

        locs   = step.get("locals", {}) or {}
        stdout = (step.get("stdout") or "").strip()
        x      = 20
        vy     = y0+32

        for k, v in locs.items():
            if k == arr_name: continue     # skip main array (shown above)
            kstr = str(k);  vstr = str(v)
            if len(vstr) > 25: vstr = vstr[:24]+"\u2026"
            item = f"{kstr} = {vstr}"
            iw   = _tw(draw, item, self.f_var)
            if x + iw + 20 > FRAME_W - 20:
                break
            draw.text((x, vy), kstr,  fill=AC_PURPLE, font=self.f_var_k)
            eq_x = x + _tw(draw, kstr, self.f_var_k)
            draw.text((eq_x, vy), f" = ", fill=TEXT2, font=self.f_var)
            draw.text((eq_x+_tw(draw," = ",self.f_var), vy),
                      vstr, fill=AC_ORANGE, font=self.f_var)
            x += iw + 28

        if stdout:
            out_lbl = f"\u25b6  Output: {stdout.split(chr(10))[-1][:60]}"
            ow      = _tw(draw, out_lbl, self.f_var)
            ox      = FRAME_W - ow - 20
            if ox > x + 20:
                draw.text((ox, vy), out_lbl, fill=AC_GREEN, font=self.f_var)

    # ── Syntax highlighting helper ────────────────────────────────────────────
    def _syn(self, draw, x, y, text, font):
        i = 0
        while i < len(text):
            c = text[i]
            if c == '#' or text[i:i+2] in ('//', '/*'):
                draw.text((x, y), text[i:], fill=(88,166,255), font=font)
                break
            if c in ('"', "'"):
                j = i+1
                while j < len(text) and text[j] != c: j+=1
                tok = text[i:j+1]
                draw.text((x, y), tok, fill=(115,192,90), font=font)
                try: x = draw.textbbox((x,y), tok, font=font)[2]
                except: x += _tw(draw, tok, font)
                i = j+1; continue
            if c.isdigit():
                j = i
                while j < len(text) and (text[j].isdigit() or text[j]=='.'): j+=1
                tok = text[i:j]
                draw.text((x, y), tok, fill=(210,153,34), font=font)
                try: x = draw.textbbox((x,y), tok, font=font)[2]
                except: x += _tw(draw, tok, font)
                i = j; continue
            if c.isalpha() or c == '_':
                j = i
                while j < len(text) and (text[j].isalnum() or text[j]=='_'): j+=1
                tok  = text[i:j]
                col  = (255,123,114) if tok in KEYWORDS else TEXT
                draw.text((x, y), tok, fill=col, font=font)
                try: x = draw.textbbox((x,y), tok, font=font)[2]
                except: x += _tw(draw, tok, font)
                i = j; continue
            draw.text((x, y), c, fill=TEXT, font=font)
            try: x = draw.textbbox((x,y), c, font=font)[2]
            except: x += _tw(draw, c, font)
            i += 1

    # ── Final error summary frame ─────────────────────────────────────────────
    def _error_frame(self, msg: str, num: int) -> str:
        img  = Image.new("RGB", (FRAME_W, FRAME_H), (18, 10, 10))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0,0,FRAME_W,8], fill=AC_RED)
        draw.text((20,20), "\u27e8trace\u27e9", fill=AC_CYAN, font=self.f_hdr)
        t  = "RUNTIME ERROR"
        tw = _tw(draw, t, self.f_hdr)
        draw.text(((FRAME_W-tw)//2, 20), t, fill=AC_RED, font=self.f_hdr)
        draw.rectangle([0,56,FRAME_W,58], fill=(70,18,18))
        ic  = "\u26a0"
        icf = _load_font(72)
        icw = _tw(draw, ic, icf)
        draw.text(((FRAME_W-icw)//2, 90), ic, fill=AC_RED, font=icf)
        tf  = _load_font(22)
        tit = "Execution stopped with a Runtime Error"
        tiw = _tw(draw, tit, tf)
        draw.text(((FRAME_W-tiw)//2, 210), tit, fill=TEXT, font=tf)
        bx0,by0 = 80,265; bx1,by1 = FRAME_W-80, by0+190
        _rrect(draw,[bx0,by0,bx1,by1],radius=10,fill=(38,14,14),outline=AC_RED,width=2)
        f_err = _load_font(13, mono=True)
        ey = by0+14
        for line in msg.replace('\r','').split('\n')[:8]:
            if ey+16 > by1-8: break
            cw = max(1, _tw(draw, "W", f_err))
            mc = max(1,(bx1-bx0-30)//cw)
            draw.text((bx0+15, ey), line[:mc], fill=(238,138,98), font=f_err)
            ey += 20
        nf  = _load_font(12)
        nt  = "The video above shows all steps executed before this error."
        nw  = _tw(draw, nt, nf)
        draw.text(((FRAME_W-nw)//2, by1+28), nt, fill=TEXT2, font=nf)
        draw.rectangle([0,FRAME_H-8,FRAME_W,FRAME_H], fill=AC_RED)
        path = os.path.join(self.temp_dir, f"frame_{num:04d}.png")
        img.save(path, "PNG", optimize=False)
        return path


def _fmt(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
