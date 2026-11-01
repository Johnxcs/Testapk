"""Renders a fake code editor window (static chrome + dynamic text) with a
bottom TERMINAL panel. Terminal text is typed by 'run' scenes."""
from PIL import Image, ImageDraw, ImageFont

from .highlight import highlight_lines


class EditorRenderer:
    def __init__(self, width, height, fps, font_path, theme, cfg,
                 filename="main.py", language_label="Python", window_title=""):
        self.w, self.h = width, height
        self.fps = int(fps)
        self.theme = theme
        self.filename = filename
        self.language_label = language_label
        self.window_title = window_title or filename

        fs = int(cfg.get("font_size", 22))
        if font_path:
            self.font = ImageFont.truetype(font_path, fs)
        else:
            self.font = ImageFont.load_default(size=fs)
        self.cw = self.font.getlength("M")
        self.ascent, self.descent = self.font.getmetrics()
        self.lh = int(fs * 1.6)

        # chrome heights scale with the font so big vertical renders stay usable
        self.title_h, self.tab_h, self.status_h = \
            int(fs * 1.5), int(fs * 1.35), int(fs * 1.1)
        self.term_header_h = int(fs * 1.2)
        self.term_lines = 4
        self.editor_top = self.title_h + self.tab_h
        self.status_y = height - self.status_h
        self.term_top = self.status_y - self.term_header_h - self.term_lines \
            * self.lh
        self.pad = int(fs * 0.7)
        self.gutter_w = int(self.cw * 4) + 10
        self.x_text = self.pad + self.gutter_w
        area = self.term_top - self.editor_top - 2 * self.pad
        self.max_lines = max(3, area // self.lh)
        self.cursor_style = cfg.get("cursor", "bar")
        self.language = language_label.lower() or "python"
        self.line_hl = _blend(theme["bg"], "#ffffff", 0.045)
        self.sep = _blend(theme["bg"], "#ffffff", 0.10)
        self._terminal_footer = "UTF-8    LF"
        self._build_static()

    # ---------- static chrome (rendered once) ----------
    def _build_static(self):
        w, h, t = self.w, self.h, self.theme
        fs = self.font.size if hasattr(self.font, "size") else self.lh / 1.6
        bg = Image.new("RGB", (w, h), t["bg"])
        d = ImageDraw.Draw(bg)
        dot_r = max(4, int(fs * 0.19))
        gap_d = int(fs * 0.67)
        # window title bar
        d.rectangle([0, 0, w, self.title_h], fill=t["chrome"])
        cy = self.title_h // 2
        for i, col in enumerate(t["traffic"]):
            d.ellipse([22 + i * gap_d - dot_r, cy - dot_r,
                       22 + i * gap_d + dot_r, cy + dot_r], fill=col)
        title = f"{self.filename} — {self.window_title}"
        self._center_text(d, title, self.title_h, t["chrome_text"])
        # tab bar with one active tab + unsaved dot
        d.rectangle([0, self.title_h, w, self.editor_top], fill=t["tabbar"])
        tw = self.font.getlength(self.filename) + 36
        d.rectangle([8, self.title_h, 8 + tw, self.editor_top], fill=t["tab"])
        d.rectangle([8, self.editor_top - 2, 8 + tw, self.editor_top], fill=t["accent"])
        d.text((8 + 12, self.title_h + (self.tab_h - (self.ascent + self.descent)) // 2),
               self.filename, font=self.font, fill=t["tab_text"])
        dcy = self.title_h + self.tab_h // 2
        d.ellipse([8 + tw - 18, dcy - 4, 8 + tw - 10, dcy + 4], fill=t["dot_saved"])
        # gutter separator
        d.line([(self.pad + self.gutter_w - 6, self.editor_top + 6),
                (self.pad + self.gutter_w - 6, self.term_top)], fill=self.sep)
        # ---- terminal panel ----
        d.rectangle([0, self.term_top, w, self.status_y], fill=t["terminal_bg"])
        d.rectangle([0, self.term_top, w, self.term_top + self.term_header_h],
                    fill=t["terminal_header"])
        labels = ["TERMINAL", "OUTPUT", "PROBLEM", "PORTS"]
        tx = 14
        thc = (self.ascent + self.descent)
        for i, lab in enumerate(labels):
            lw = self.font.getlength(lab)
            if i == 0:  # active tab
                d.rectangle([tx - 8, self.term_top, tx + lw + 8,
                             self.term_top + self.term_header_h],
                            fill=t["terminal_bg"])
                d.rectangle([tx - 8, self.term_top + self.term_header_h - 2,
                             tx + lw + 8, self.term_top + self.term_header_h],
                            fill=t["accent"])
            d.text((tx, self.term_top + (self.term_header_h - thc) // 2), lab,
                   font=self.font,
                   fill=t["terminal_tab_text"] if i == 0 else t["terminal_inactive"])
            tx += lw + (24 if i == 0 else 18)
        d.text((w - 34, self.term_top + (self.term_header_h - thc) // 2), "+",
               font=self.font, fill=t["terminal_inactive"])
        d.line([(0, self.term_top - 1), (w, self.term_top - 1)],
               fill=t["terminal_header"])
        # ---- status bar ----
        d.rectangle([0, self.status_y, w, h], fill=t["status"])
        base = self.status_y + (self.status_h - thc) // 2
        d.text((10, base), f"{self.filename}", font=self.font, fill=t["status_text"])
        d.text((10 + self.font.getlength(self.filename) + 20, base),
               self.language_label, font=self.font, fill=t["status_text"])
        d.text((w - self.font.getlength(self._terminal_footer) - 10, base),
               self._terminal_footer, font=self.font, fill=t["status_text"])
        self.bg = bg
        self.status_base = base

    def _center_text(self, d, text, band_h, color):
        w = self.font.getlength(text)
        d.text(((self.w - w) / 2, (band_h - (self.ascent + self.descent)) / 2),
               text, font=self.font, fill=color)

    def _draw_terminal(self, d, text, cursor_on):
        t = self.theme
        raw = text.split("\n")
        view = raw[-self.term_lines:]
        start_i = len(raw) - len(view)
        y0 = self.term_top + self.term_header_h + 8
        for row, line in enumerate(view):
            y = y0 + row * self.lh
            if line.startswith("$"):
                d.text((self.pad, y), "$", font=self.font, fill=t["prompt"])
                d.text((self.pad + self.cw + self.font.getlength(" "), y), line[1:].strip(),
                       font=self.font, fill=t["fg"])
            elif line:
                d.text((self.pad, y), line, font=self.font, fill=t["term_out"])
        if cursor_on and len(text) < 400:
            last = raw[-1]
            row = len(view) - 1
            y = y0 + row * self.lh
            if last.startswith("$"):
                x = self.pad + self.cw + self.font.getlength(" ") + \
                    self.font.getlength(last[1:].strip())
            else:
                x = self.pad + self.font.getlength(last)
            d.rectangle([x, y, x + 2, y + self.lh - 6], fill=t["cursor"])

    # ---------- dynamic frames ----------
    def render_code_frame(self, buffer_str, cursor_on, terminal_text="",
                          term_cursor_on=False):
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        t = self.theme
        lines = highlight_lines(buffer_str, self.language, t["tok"], t["fg"])
        raw = buffer_str.split("\n")
        cy, cx = len(raw) - 1, len(raw[-1])
        view0 = max(0, min(cy - self.max_lines + 1, len(raw) - self.max_lines))
        if view0 < 0:
            view0 = 0

        for row, line in enumerate(raw[view0:view0 + self.max_lines]):
            idx = view0 + row
            y = self.editor_top + self.pad + row * self.lh
            active = idx == cy
            if active:
                d.rectangle([4, y - 2, self.w - 6, y + self.lh - 2], fill=self.line_hl)
            num = str(idx + 1)
            nw = self.font.getlength(num)
            d.text((self.pad + self.gutter_w - 8 - nw, y), num, font=self.font,
                   fill=t["gutter_active"] if active else t["gutter"])
            x = self.x_text
            for seg, color in lines[idx] if idx < len(lines) else []:
                d.text((x, y), seg, font=self.font, fill=color or t["fg"])
                x += len(seg) * self.cw
        # code cursor
        if cursor_on and cy - view0 < self.max_lines:
            y = self.editor_top + self.pad + (cy - view0) * self.lh
            cx_pos = self.x_text + cx * self.cw
            if self.cursor_style == "block":
                d.rectangle([cx_pos, y, cx_pos + self.cw - 1, y + self.lh - 2],
                            fill=t["cursor"])
            else:
                d.rectangle([cx_pos, y - 1, cx_pos + 2, y + self.lh - 3], fill=t["cursor"])
        # terminal panel content
        self._draw_terminal(d, terminal_text, term_cursor_on)
        # dynamic Ln/Col on status bar (static right-side labels preserved)
        pos = f"Ln {cy + 1}, Col {cx + 1}"
        full = pos + "      " + self._terminal_footer
        fw = self.font.getlength(full)
        d.rectangle([self.w - fw - 12, self.status_y, self.w, self.h],
                    fill=t["status"])
        d.text((self.w - fw - 12, self.status_base), full,
               font=self.font, fill=t["status_text"])
        return img


def _blend(a, b, t):
    from .theme import blend

    return blend(a, b, t)
