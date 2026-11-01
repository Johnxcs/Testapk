"""YouTube Shorts layout: vertical 9:16 full-bleed editor + optional handle text."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .theme import blend


def _font(path, size):
    size = int(size)
    if path:
        return ImageFont.truetype(path, size), size
    return ImageFont.load_default(size=size), size


class ShortsComposer:
    def __init__(self, w, h, fps, font_path, theme, cfg, timings,
                 card_size=None):
        self.w, self.h = w, h
        self.fps = int(fps)
        self.theme = theme
        self.timings = timings
        self.handle = str(cfg.get("handle", "") or "")
        self.pad = max(18, int(w * 0.022))

        # editor geometry: the editor fills the whole vertical frame
        self.card_x, self.card_y = card_size[0], card_size[1]
        self.card_w, self.card_h = card_size[2], card_size[3]
        self.full_bleed = (self.card_w, self.card_h) == (w, h)
        if not self.full_bleed:
            self.mask = Image.new("L", (self.card_w, self.card_h), 0)
            ImageDraw.Draw(self.mask).rounded_rectangle(
                [0, 0, self.card_w - 1, self.card_h - 1],
                radius=max(16, self.card_w // 32), fill=255)
        else:
            self.mask = None

        self.small_font, _ = _font(font_path, w / 27.0)

    # ---------- helpers ----------
    def _draw_handle(self, d):
        text = self.handle
        y = int(self.h * 0.030)
        d.text((self.pad, y), text, font=self.small_font,
               fill=blend("#ffffff", self.theme["bg"], 0.25), stroke_width=2,
               stroke_fill="#000000")

    # ---------- main ----------
    def compose(self, img, scene_index, frame_in):
        out = Image.new("RGB", (self.w, self.h), self.theme["bg"])
        if img.size == (self.w, self.h) or self.full_bleed:
            out.paste(img, (self.card_x, self.card_y))
        else:
            # soft drop shadow for the card
            sh = Image.new("L", (self.w, self.h), 0)
            ImageDraw.Draw(sh).rounded_rectangle(
                [self.card_x + 6, self.card_y + 10,
                 self.card_x + self.card_w + 6, self.card_y + self.card_h + 10],
                radius=self.mask.size[0] // 32, fill=110)
            sh = sh.filter(ImageFilter.GaussianBlur(14))
            dark = Image.new("RGB", (self.w, self.h), "#000000")
            out.paste(dark, (0, 0), sh)
            out.paste(img, (self.card_x, self.card_y), self.mask)
        d = ImageDraw.Draw(out)
        if self.handle:
            self._draw_handle(d)
        return out
