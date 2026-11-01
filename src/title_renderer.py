"""Title / outro card: big centered typewriter text on a dark background."""
from PIL import Image, ImageDraw, ImageFont


class TitleRenderer:
    def __init__(self, width, height, fps, font_path, theme, cfg, footer="",
                 title=""):
        self.w, self.h = width, height
        self.fps = int(fps)
        self.theme = theme
        self.footer = footer
        self.title = title
        self.title_font, self.title_size = self._make_font(font_path, max(24, width // 9))
        self.sub_size = max(16, self.title_size // 3)
        self.sub_font = ImageFont.truetype(font_path, self.sub_size) if font_path \
            else ImageFont.load_default(size=self.sub_size)
        self.bg = Image.new("RGB", (width, height), theme["bg"])
        d = ImageDraw.Draw(self.bg)
        # vertical (9:16) frames get extra bottom margin (YouTube Shorts UI zone)
        self.vertical = height > width
        footer_y = height - int(height * 0.075) if self.vertical else height - 60
        if footer:
            fw = self.sub_font.getlength(footer)
            d.text(((width - fw) / 2, footer_y), footer,
                   font=self.sub_font, fill=theme["inactive"])
        self.title_color = "#eaeaea"
        self.sub_color = "#9aa8b4"
        self.cursor_color = theme["accent"]

    def _make_font(self, path, size):
        self.title_size = int(size)
        if not path:
            return ImageFont.load_default(size=self.title_size), self.title_size
        f = ImageFont.truetype(path, self.title_size)
        probe = Image.new("RGB", (10, 10))
        dp = ImageDraw.Draw(probe)
        # shrink only if the actual title overflows (never below a readable size)
        while self.title_size > 44 and dp.textlength(self.title or "M" * 40, font=f) > self.w * 0.9:
            self.title_size -= 4
            f = ImageFont.truetype(path, self.title_size)
        return f, self.title_size

    def render_frame(self, full_title, k_title, k_sub, cursor_on):
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        t, ts = self.title_font, self.title_size
        y = int(self.h * 0.38) - ts // 2
        main = full_title[:k_title] if k_title < len(full_title) else full_title
        if main:
            mw = t.getlength(main)
            d.text(((self.w - mw) / 2, y), main, font=t, fill=self.title_color)
        full_w = t.getlength(full_title) or 1
        bw = int(220 * min(1.0, t.getlength(main) / full_w))
        if bw > 2:
            d.rectangle([(self.w - bw) / 2, y + int(ts * 1.2),
                         (self.w + bw) / 2, y + int(ts * 1.2) + 4],
                        fill=self.theme["accent"])
        sy = y + int(ts * 1.55)
        if k_sub > 0:
            sub = full_title  # placeholder, replaced below
            d.text((0, -100), "", font=t)  # no-op keep draw state trivial
        return img, (sy, k_sub)

    def render_full(self, full_title, k_title, k_sub, full_sub, cursor_on):
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        t, ts = self.title_font, self.title_size
        ty_frac = 0.34 if self.vertical else 0.38
        y = int(self.h * ty_frac) - ts // 2
        main = full_title[:k_title]
        mw = t.getlength(main) if main else 0
        if main:
            d.text(((self.w - mw) / 2, y), main, font=t, fill=self.title_color)
        full_w = t.getlength(full_title) or 1
        bw = int(220 * max(0.0, min(1.0, mw / full_w)))
        if bw > 2:
            d.rectangle([(self.w - bw) / 2, y + int(ts * 1.2),
                         (self.w + bw) / 2, y + int(ts * 1.2) + 4],
                        fill=self.theme["accent"])
        sy = y + int(ts * 1.55)
        if k_sub > 0:
            sub = full_sub[:k_sub]
            if sub:
                sw = self.sub_font.getlength(sub)
                d.text(((self.w - sw) / 2, sy), sub, font=self.sub_font,
                       fill=self.sub_color)
        if cursor_on:
            typing_title = k_title < len(full_title)
            if typing_title or k_sub == 0:
                cw = t.getlength("M")
                cx = (self.w - mw) / 2 + mw
                d.rectangle([cx, y + 4, cx + cw * 0.8, y + ts], fill=self.cursor_color)
            else:
                sub = full_sub[:k_sub]
                cw = self.sub_font.getlength("M")
                sw = self.sub_font.getlength(sub)
                cx = (self.w - sw) / 2 + sw
                d.rectangle([cx, sy + 2, cx + cw, sy + ts // 4 + 6],
                            fill=self.cursor_color)
        return img
