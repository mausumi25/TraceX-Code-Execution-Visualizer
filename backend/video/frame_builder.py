"""
frame_builder.py
Renders each execution step as a 1280×720 PNG using Pillow.

Layout
------
┌────────────────────────────────────────────────────────────┐
│  HEADER: logo · language badge · step counter · event badge│
├─────────────────────────────────┬──────────────────────────┤
│   CODE PANEL (760 px wide)      │  SIDE PANEL (520 px)     │
│   gutter + highlighted code     │  VARIABLES               │
│                                 │  CALL STACK              │
│                                 │  OUTPUT                  │
├─────────────────────────────────┴──────────────────────────┤
│  FOOTER: line info · watermark                              │
└────────────────────────────────────────────────────────────┘
"""
import os
import tempfile

from PIL import Image, ImageDraw, ImageFont

# ── Frame dimensions ──────────────────────────────────────────────────────────
FRAME_W = 1280
FRAME_H = 720
HEADER_H = 52
FOOTER_H = 38
CODE_W = 760          # code panel width
SIDE_W = FRAME_W - CODE_W  # side panel width

# ── Dark theme palette ────────────────────────────────────────────────────────
BG            = (13,  17,  23)
PANEL_BG      = (22,  27,  34)
HEADER_BG     = (21,  27,  35)
FOOTER_BG     = (17,  21,  28)
GUTTER_BG     = (17,  21,  28)
BORDER        = (48,  54,  61)
LINE_HL_OK    = (40,  75,  50)   # green-tinted highlight for active line
LINE_HL_ERR   = (75,  30,  30)   # red-tinted highlight for error line
LINE_ACCENT_OK= (63, 185,  80)
LINE_ACCENT_ERR= (248, 81,  73)

# Text
TEXT         = (230, 237, 243)
TEXT_SEC     = (125, 133, 144)
TEXT_DIM     = (72,  80,  89)

# Syntax colours
KW_COLOR     = (255, 123, 114)  # keywords
STR_COLOR    = (115, 192,  90)  # strings
CMT_COLOR    = ( 88, 166, 255)  # comments / line-nos (selected)
NUM_COLOR    = (210, 153,  34)  # numbers
ID_COLOR     = TEXT

# Side-panel accent colours
ACCENT_BLUE  = ( 56, 139, 253)
ACCENT_CYAN  = ( 79, 197, 232)
ACCENT_PURPLE= (188, 140, 228)
ACCENT_ORANGE= (210, 153,  34)
ACCENT_GREEN = ( 63, 185,  80)
ACCENT_RED   = (248,  81,  73)

# Badge colours per event
BADGE_OK  = ( 35, 134,  54)
BADGE_EXC = (187, 128,   9)
BADGE_ERR = (218,  54,  51)

# ── Language → badge colour ───────────────────────────────────────────────────
LANG_COLORS = {
    "PYTHON":     ( 55, 118, 171),
    "JAVASCRIPT": (200, 160,   0),
    "C":          ( 85, 170, 211),
    "CPP":        ( 0,  150, 136),  # teal
    "JAVA":       (248, 152,  32),
}

# ── Keywords to highlight ─────────────────────────────────────────────────────
KEYWORDS = {
    # Python
    "def","class","return","if","else","elif","for","while","import","from",
    "in","not","and","or","True","False","None","try","except","finally",
    "with","as","pass","break","continue","lambda","yield","del","raise",
    "global","nonlocal","async","await","is","print",
    # JS
    "var","let","const","function","new","this","typeof","instanceof",
    "switch","case","default","throw","catch","of","=>",
    # C
    "int","float","double","char","void","struct","typedef","enum","union",
    "return","if","else","for","while","do","break","continue","include",
    "printf","scanf","malloc","free","sizeof","NULL","main",
    # C++
    "class","public","private","protected","namespace","using","template",
    "typename","virtual","override","const","auto","nullptr","bool","true",
    "false","string","vector","map","set","cout","cin","endl","std",
    "new","delete","try","catch","throw","static","inline","explicit",
}


# ── Font helpers ──────────────────────────────────────────────────────────────
def _load_font(size: int, mono: bool = True) -> ImageFont.FreeTypeFont:
    if mono:
        candidates = [
            "C:/Windows/Fonts/consola.ttf",   # Consolas (Windows)
            "C:/Windows/Fonts/cour.ttf",
            "/System/Library/Fonts/Monaco.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Return pixel width of text using textbbox (Pillow ≥ 8)."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    except AttributeError:
        # Pillow < 8 fallback
        w, _ = draw.textsize(text, font=font)  # type: ignore[attr-defined]
        return w


def _rrect(draw: ImageDraw.ImageDraw, box, radius: int = 5, **kw):
    """Rounded rectangle with graceful fallback."""
    try:
        draw.rounded_rectangle(box, radius=radius, **kw)
    except AttributeError:
        draw.rectangle(box, **kw)


# ── Main builder class ────────────────────────────────────────────────────────
class FrameBuilder:
    def __init__(self, code_lines: list[str], language: str = "python"):
        self.code_lines = code_lines
        self.language = language.upper()
        self.total_lines = len(code_lines)

        # Fonts
        self.f_code   = _load_font(13, mono=True)
        self.f_ui     = _load_font(12, mono=False)
        self.f_header = _load_font(14, mono=False)
        self.f_label  = _load_font(11, mono=False)

        # Measure a single character width for the monospace font
        tmp_img = Image.new("RGB", (200, 40))
        tmp_drw = ImageDraw.Draw(tmp_img)
        self._char_w = max(1, _text_w(tmp_drw, "W", self.f_code))
        self._line_h = 19  # pixels per code line

        self.temp_dir = tempfile.mkdtemp(prefix="trace_frames_")

    # ── Public API ────────────────────────────────────────────────────────────
    def build_frames(self, steps: list[dict]) -> list[str]:
        total = len(steps)
        return [self._build_frame(s, i + 1, total) for i, s in enumerate(steps)]

    # ── Frame assembly ────────────────────────────────────────────────────────
    def _build_frame(self, step: dict, step_num: int, total: int) -> str:
        img  = Image.new("RGB", (FRAME_W, FRAME_H), BG)
        draw = ImageDraw.Draw(img)

        self._draw_header(draw, step, step_num, total)
        self._draw_code_panel(draw, step)
        self._draw_side_panel(draw, step)
        self._draw_footer(draw, step)

        # Divider between code and side panel
        draw.rectangle([CODE_W, HEADER_H, CODE_W + 1, FRAME_H - FOOTER_H], fill=BORDER)

        path = os.path.join(self.temp_dir, f"frame_{step_num:04d}.png")
        img.save(path, "PNG", optimize=False)
        return path

    # ── Header ────────────────────────────────────────────────────────────────
    def _draw_header(self, draw, step, step_num, total):
        draw.rectangle([0, 0, FRAME_W, HEADER_H], fill=HEADER_BG)
        draw.rectangle([0, HEADER_H - 1, FRAME_W, HEADER_H], fill=BORDER)

        # Logo
        draw.text((18, 15), "⟨trace⟩", fill=ACCENT_CYAN, font=self.f_header)

        # Language badge
        lang_text = self.language
        lc = LANG_COLORS.get(self.language, ACCENT_BLUE)
        lx = 130
        lw = _text_w(draw, lang_text, self.f_label) + 16
        _rrect(draw, [lx, 14, lx + lw, HEADER_H - 14], radius=4, fill=lc)
        draw.text((lx + 8, 16), lang_text, fill=(255, 255, 255), font=self.f_label)

        # Step counter (centred)
        step_text = f"Step  {step_num} / {total}"
        sw = _text_w(draw, step_text, self.f_header)
        draw.text(((FRAME_W - sw) // 2, 15), step_text, fill=TEXT, font=self.f_header)

        # Event badge (right)
        event = step.get("event", "line")
        has_error = bool(step.get("error"))
        if event == "error" or (has_error and event != "exception"):
            badge_col, badge_txt = BADGE_ERR, "RUNTIME ERROR"
        elif event == "exception" or has_error:
            badge_col, badge_txt = BADGE_EXC, "EXCEPTION"
        else:
            badge_col, badge_txt = BADGE_OK, "EXECUTING"

        bw = _text_w(draw, badge_txt, self.f_label) + 20
        bx = FRAME_W - bw - 16
        _rrect(draw, [bx, 14, bx + bw, HEADER_H - 14], radius=4, fill=badge_col)
        draw.text((bx + 10, 16), badge_txt, fill=(255, 255, 255), font=self.f_label)

    # ── Code panel ────────────────────────────────────────────────────────────
    def _draw_code_panel(self, draw, step):
        x0, y0, x1, y1 = 0, HEADER_H, CODE_W, FRAME_H - FOOTER_H
        draw.rectangle([x0, y0, x1, y1], fill=PANEL_BG)

        cur = step.get("line", 0)
        has_err = bool(step.get("error"))
        gutter = 50

        # Gutter background
        draw.rectangle([x0, y0, x0 + gutter, y1], fill=GUTTER_BG)

        # Visible window (scroll to keep current line centred)
        avail_h = y1 - y0 - 8
        max_vis = avail_h // self._line_h
        half = max_vis // 2
        start = max(0, cur - 1 - half)
        end   = min(self.total_lines, start + max_vis)

        for idx, li in enumerate(range(start, end)):
            lineno = li + 1
            raw_line = self.code_lines[li] if li < len(self.code_lines) else ""
            ly = y0 + 6 + idx * self._line_h

            # Current-line highlight
            if lineno == cur:
                hl = LINE_HL_ERR if has_err else LINE_HL_OK
                draw.rectangle([x0, ly - 1, x1, ly + self._line_h - 2], fill=hl)
                acc = LINE_ACCENT_ERR if has_err else LINE_ACCENT_OK
                draw.rectangle([x0, ly - 1, x0 + 3, ly + self._line_h - 2], fill=acc)

            # Line number
            ln_str = str(lineno)
            ln_w   = _text_w(draw, ln_str, self.f_code)
            ln_col = ACCENT_BLUE if lineno == cur else TEXT_DIM
            draw.text((x0 + gutter - ln_w - 8, ly), ln_str, fill=ln_col, font=self.f_code)

            # Arrow indicator
            if lineno == cur:
                arrow_col = LINE_ACCENT_ERR if has_err else LINE_ACCENT_OK
                draw.text((x0 + 4, ly), "▶", fill=arrow_col, font=self.f_code)

            # Code text with syntax colours
            code_x = x0 + gutter + 10
            max_chars = max(1, (x1 - code_x - 8) // self._char_w)
            display   = raw_line.expandtabs(4)
            if len(display) > max_chars:
                display = display[: max_chars - 1] + "…"
            self._draw_syntax(draw, code_x, ly, display)

        # Error annotation at bottom of code panel
        if has_err:
            err_msg = step["error"]
            ey = y1 - 52
            draw.rectangle([x0 + 6, ey, x1 - 6, y1 - 6], fill=(55, 18, 18))
            _rrect(draw, [x0 + 6, ey, x1 - 6, y1 - 6], radius=6,
                   outline=ACCENT_RED, width=1)
            draw.text((x0 + 14, ey + 6), "⚠  Error", fill=ACCENT_RED, font=self.f_label)
            for ei, el in enumerate(err_msg[:160].split("\n")[:2]):
                draw.text((x0 + 14, ey + 22 + ei * 14), el,
                          fill=(230, 150, 100), font=self.f_label)

    # ── Syntax colouring ───────────────────────────────────────────────────────
    def _draw_syntax(self, draw, x, y, text):
        tokens = self._tokenise(text)
        cx = x
        for kind, tok in tokens:
            if kind == "keyword":  col = KW_COLOR
            elif kind == "string": col = STR_COLOR
            elif kind == "comment":col = CMT_COLOR
            elif kind == "number": col = NUM_COLOR
            else:                  col = TEXT

            draw.text((cx, y), tok, fill=col, font=self.f_code)
            try:
                bbox = draw.textbbox((cx, y), tok, font=self.f_code)
                cx = bbox[2]
            except AttributeError:
                w, _ = draw.textsize(tok, font=self.f_code)  # type: ignore
                cx += w

    def _tokenise(self, text: str) -> list[tuple[str, str]]:
        tokens = []
        i = 0
        while i < len(text):
            c = text[i]
            # Comment
            if c == "#" or text[i:i+2] in ("//", "/*"):
                tokens.append(("comment", text[i:]))
                break
            # String (single / double quote)
            if c in ('"', "'"):
                quote = c
                j = i + 1
                while j < len(text) and text[j] != quote:
                    j += 1
                tokens.append(("string", text[i: j + 1]))
                i = j + 1
                continue
            # Number
            if c.isdigit():
                j = i
                while j < len(text) and (text[j].isdigit() or text[j] == "."):
                    j += 1
                tokens.append(("number", text[i:j]))
                i = j
                continue
            # Word
            if c.isalpha() or c == "_":
                j = i
                while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                word = text[i:j]
                tokens.append(("keyword" if word in KEYWORDS else "identifier", word))
                i = j
                continue
            tokens.append(("other", c))
            i += 1
        return tokens

    # ── Side panel ────────────────────────────────────────────────────────────
    def _draw_side_panel(self, draw, step):
        x0 = CODE_W + 2
        y0 = HEADER_H
        x1 = FRAME_W
        y  = y0 + 12

        def section_title(title, col=ACCENT_BLUE):
            nonlocal y
            draw.text((x0 + 10, y), title, fill=col, font=self.f_label)
            y += 18
            draw.rectangle([x0 + 8, y, x1 - 8, y + 1], fill=BORDER)
            y += 6

        # ── Variables ────────────────────────────────────────────────────────
        section_title("VARIABLES")
        lvars = step.get("locals", {})
        if lvars:
            for k, v in list(lvars.items())[:10]:
                vk = str(k)
                vv = str(v)
                kw = _text_w(draw, vk, self.f_ui)
                draw.text((x0 + 10, y), vk, fill=ACCENT_PURPLE, font=self.f_ui)
                draw.text((x0 + 10 + kw + 4, y), "=", fill=TEXT_SEC, font=self.f_ui)
                max_c = max(1, (x1 - x0 - kw - 40) // max(self._char_w, 1))
                vv_d = vv[:max_c] + ("…" if len(vv) > max_c else "")
                draw.text((x0 + 10 + kw + 18, y), vv_d, fill=ACCENT_ORANGE, font=self.f_ui)
                y += 19
                if y > FRAME_H - FOOTER_H - 150:
                    break
        else:
            draw.text((x0 + 10, y), "No variables yet", fill=TEXT_DIM, font=self.f_ui)
            y += 19
        y += 8

        # ── Call Stack ───────────────────────────────────────────────────────
        section_title("CALL STACK")
        stack = step.get("stack") or ["__main__"]
        for frame_name in reversed(stack[:5]):
            draw.text((x0 + 10, y), f"→  {frame_name}()", fill=ACCENT_CYAN, font=self.f_ui)
            y += 18
        y += 8

        # ── Output ───────────────────────────────────────────────────────────
        section_title("OUTPUT")
        out_text = (step.get("stdout") or "").strip()
        box_h = min(130, FRAME_H - FOOTER_H - y - 10)
        draw.rectangle([x0 + 8, y, x1 - 8, y + box_h], fill=FOOTER_BG)
        _rrect(draw, [x0 + 8, y, x1 - 8, y + box_h], radius=4, outline=BORDER, width=1)

        if out_text:
            out_lines = out_text.split("\n")[-7:]
            for oi, ol in enumerate(out_lines):
                oy = y + 6 + oi * 15
                if oy + 14 > y + box_h:
                    break
                max_c = max(1, (SIDE_W - 24) // max(self._char_w, 1))
                draw.text((x0 + 14, oy), ol[:max_c], fill=ACCENT_GREEN, font=self.f_ui)
        else:
            draw.text((x0 + 14, y + 8), "(no output yet)", fill=TEXT_DIM, font=self.f_ui)

    # ── Footer ────────────────────────────────────────────────────────────────
    def _draw_footer(self, draw, step):
        y0 = FRAME_H - FOOTER_H
        draw.rectangle([0, y0, FRAME_W, FRAME_H], fill=FOOTER_BG)
        draw.rectangle([0, y0, FRAME_W, y0 + 1], fill=BORDER)

        line_num = step.get("line", "?")
        draw.text((18, y0 + 11), f"Line {line_num}", fill=TEXT_SEC, font=self.f_label)
        wm = "⟨trace⟩  |  Code Execution Visualizer"
        wm_w = _text_w(draw, wm, self.f_label)
        draw.text((FRAME_W - wm_w - 18, y0 + 11), wm, fill=TEXT_DIM, font=self.f_label)
