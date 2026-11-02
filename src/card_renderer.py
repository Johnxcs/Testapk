"""Content cards for non-code scenes: text, bullets, steps, quote, compare, stat, image.

Every card reveals itself over the narration (typewriter), so it works with the same
timing model as code scenes: `count_units(scene)` = how many reveal steps the scene has.
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .theme import blend

CARD_KINDS = ("text", "bullets", "steps", "quote", "compare", "stat", "image")
STAT_UNITS = 24      # reveal steps used by the count-up of a 'stat' value
IMG_UNITS = 30       # reveal steps used by the fade-in of an 'image'
UI_DIR = Path(__file__).resolve().parent.parent / "fonts" / "ui"
GREEN, RED = "#3ddc97", "#ff6b6b"


def _s(v):
    return "" if v is None else str(v)


def _items(v):
    if isinstance(v, list):
        return [_s(x) for x in v]
    return [_s(v)] if v else []


def count_units(sc):
    k, n = sc.get("kind"), len(_s(sc.get("heading")))
    if k == "text":
        n += len(_s(sc.get("body")))
    elif k in ("bullets", "steps"):
        n += sum(len(i) for i in _items(sc.get("items")))
    elif k == "quote":
        n = len(_s(sc.get("text"))) + (len(_s(sc.get("author"))) + 2 if sc.get("author") else 0)
    elif k == "compare":
        for side in ("left", "right"):
            d = sc.get(side) or {}
            n += len(_s(d.get("title"))) + sum(len(i) for i in _items(d.get("items")))
    elif k == "stat":
        n += STAT_UNITS + len(_s(sc.get("label")))
    elif k == "image":
        n += IMG_UNITS + len(_s(sc.get("caption")))
    return max(1, n)


def _wrap(text, font, maxw):
    """Word-wrap -> [(line, start_index_in_original_text)]."""
    out, base = [], 0
    for para in text.split("\n"):
        cur, cs = "", base
        for m in re.finditer(r"\S+", para):
            word = m.group()
            cand = word if not cur else cur + " " + word
            if cur and font.getlength(cand) > maxw:
                out.append((cur, cs))
                cur, cs = word, base + m.start()
            else:
                if not cur:
                    cs = base + m.start()
                cur = cand
            while font.getlength(cur) > maxw and len(cur) > 1:   # very long word
                cut = len(cur)
                while cut > 1 and font.getlength(cur[:cut]) > maxw:
                    cut -= 1
                out.append((cur[:cut], cs))
                cur, cs = cur[cut:], cs + cut
        if cur:
            out.append((cur, cs))
        elif not para:
            out.append(("", base))
        base += len(para) + 1
    return out


def _count_text(value, p):
    m = re.match(r"^(\D*?)(-?\d[\d,]*\.?\d*)(.*)$", value, re.S)
    if not m:
        return value if p > 0 else ""
    pre, num, suf = m.groups()
    dec = len(num.split(".")[1]) if "." in num else 0
    v = float(num.replace(",", "")) * (1 - (1 - p) ** 3)
    txt = f"{v:,.{dec}f}" if "," in num else f"{v:.{dec}f}"
    return pre + txt + suf


class CardRenderer:
    def __init__(self, w, h, fps, font_path, theme, cfg, footer="", base_dirs=(), captions=False):
        self.w, self.h = w, h
        self.theme = theme
        self.vertical = h > w
        self.pad = int(w * 0.08)
        self.top = int(h * (0.13 if self.vertical else 0.10))
        self.bottom = int(h * (0.80 if self.vertical else 0.90))
        if captions:                      # keep clear of the caption strip
            self.bottom = int(h * (0.62 if self.vertical else 0.74))
        self.mono = font_path
        self.footer = footer
        self.base_dirs = [Path(p) for p in base_dirs]
        self.accent = theme["accent"]
        self.fg, self.muted = "#eaeaea", "#9aa8b4"
        self._fonts, self._layouts, self._images, self._masks = {}, {}, {}, {}
        self.bg = self._make_bg()

    # ---------- fonts / background ----------
    def _font(self, size, bold=False):
        size = max(10, int(size))
        key = (size, bold)
        if key not in self._fonts:
            cands = [UI_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
                     Path("/system/fonts/Roboto-Bold.ttf" if bold else "/system/fonts/Roboto-Regular.ttf"),
                     Path("/system/fonts/NotoSans-Bold.ttf" if bold else "/system/fonts/NotoSans-Regular.ttf")]
            path = next((str(c) for c in cands if c.is_file()), self.mono)
            self._fonts[key] = (ImageFont.truetype(path, size) if path
                                else ImageFont.load_default(size=size))
        return self._fonts[key]

    def _make_bg(self):
        top = blend(self.theme["bg"], self.accent, 0.10)
        img = Image.new("RGB", (self.w, self.h), self.theme["bg"])
        d = ImageDraw.Draw(img)
        for y in range(self.h):
            d.line([(0, y), (self.w, y)], fill=blend(top, self.theme["bg"], min(1, y / (self.h * 0.55))))
        d.rectangle([self.pad, int(self.h * 0.055), self.pad + 90, int(self.h * 0.055) + 6],
                    fill=self.accent)
        if self.footer:
            f = self._font(self.w / 30)
            fw = f.getlength(self.footer)
            fy = self.h - int(self.h * 0.075) if self.vertical else self.h - 60
            d.text(((self.w - fw) / 2, fy), self.footer, font=f, fill=self.theme["inactive"])
        return img

    # ---------- layout ----------
    def _add_text(self, ops, x, y, text, font, fill, off, maxw, align="left", gap=1.25):
        lh = int(font.size * gap)
        for line, start in _wrap(text, font, maxw):
            lx = x + (maxw - font.getlength(line)) / 2 if align == "center" else x
            ops.append(("text", lx, y, line, font, fill, off + start))
            y += lh
        return y

    def _heading(self, ops, y, sc, s, color=None):
        text = _s(sc.get("heading"))
        if not text:
            return y, 0
        f = self._font(self.w * 0.085 * s, True)
        color = color or sc.get("accent") or self.accent
        y = self._add_text(ops, self.pad, y, text, f, color, 0, self.w - 2 * self.pad)
        ops.append(("rect", self.pad, y + 6, 140, 6, color, len(text)))
        return y + int(self.w * 0.06), len(text)

    def _column(self, x, cw, y0, title, items, color, off, s):
        w = self.w
        padp = int(w * 0.035)
        ft, fi = self._font(w * 0.056 * s, True), self._font(w * 0.048 * s)
        ops, y = [], y0 + padp
        y = self._add_text(ops, x + padp, y, title, ft, color, off, cw - 2 * padp)
        off += len(title)
        y += int(w * 0.015)
        r = int(fi.size * 0.2)
        for it in items:
            tx = x + padp + int(fi.size * 1.1)
            y2 = self._add_text(ops, tx, y, it, fi, self.fg, off, cw - 2 * padp - int(fi.size * 1.1))
            ops.insert(0, ("dot", x + padp + r, y + int(fi.size * 0.7), r, color, off))
            y = y2 + int(fi.size * 0.35)
            off += len(it)
        return ops, y + padp - int(fi.size * 0.35) - y0, off

    def _build(self, sc, s):
        w, pad = self.w, self.pad
        maxw = w - 2 * pad
        kind, ops, y = sc.get("kind"), [], 0
        accent = sc.get("accent") or self.accent

        if kind == "text":
            y, off = self._heading(ops, y, sc, s)
            y = self._add_text(ops, pad, y, _s(sc.get("body")), self._font(w * 0.05 * s),
                               self.fg, off, maxw)
        elif kind in ("bullets", "steps"):
            y, off = self._heading(ops, y, sc, s)
            fs = self._font(w * 0.058 * s)
            ind = int(fs.size * 1.7)
            for i, it in enumerate(_items(sc.get("items"))):
                r = int(fs.size * 0.22) if kind == "bullets" else int(fs.size * 0.55)
                cy = y + int(fs.size * 1.25) // 2
                if kind == "bullets":
                    ops.append(("dot", pad + r, cy, r, accent, off))
                else:
                    ops.append(("num", pad + r, cy, r, str(i + 1),
                                self._font(fs.size * 0.75, True), accent, off))
                y = self._add_text(ops, pad + ind, y, it, fs, self.fg, off, maxw - ind)
                y += int(fs.size * 0.55)
                off += len(it)
        elif kind == "quote":
            ops.append(("text", pad, y - int(w * 0.04), "\u201c", self._font(w * 0.3 * s, True), accent, 0))
            y += int(w * 0.17)
            text = _s(sc.get("text"))
            y = self._add_text(ops, pad, y, text, self._font(w * 0.064 * s), self.fg, 0, maxw)
            if sc.get("author"):
                y += int(w * 0.03)
                y = self._add_text(ops, pad, y, "\u2014 " + _s(sc.get("author")),
                                   self._font(w * 0.042 * s, True), accent, len(text), maxw)
        elif kind == "compare":
            y, off = self._heading(ops, y, sc, s)
            sides = []
            for side, color in (("left", GREEN), ("right", RED)):
                d = sc.get(side) or {}
                sides.append((_s(d.get("title")), _items(d.get("items")), color))
            gap = int(w * 0.03)
            if self.vertical:
                for title, items, color in sides:
                    cops, hh, off2 = self._column(pad, maxw, y, title, items, color, off, s)
                    ops.append(("rrect", pad, y, maxw, hh, blend(self.theme["bg"], color, 0.14),
                                blend(color, self.theme["bg"], 0.45), off, int(w * 0.03)))
                    ops.extend(cops)
                    y += hh + gap
                    off = off2
            else:
                cw = (maxw - gap) // 2
                built, hmax = [], 0
                for n, (title, items, color) in enumerate(sides):
                    x = pad + n * (cw + gap)
                    cops, hh, off = self._column(x, cw, y, title, items, color, off, s)
                    built.append((x, color, cops, off))
                    hmax = max(hmax, hh)
                for x, color, cops, _ in built:
                    ops.append(("rrect", x, y, cw, hmax, blend(self.theme["bg"], color, 0.14),
                                blend(color, self.theme["bg"], 0.45), 0, int(w * 0.03)))
                    ops.extend(cops)
                y += hmax + gap
        elif kind == "stat":
            y, off = self._heading(ops, y, sc, s, color=self.muted)
            value = _s(sc.get("value"))
            fv = self._font(w * 0.30 * s, True)
            while fv.getlength(value) > maxw and fv.size > 30:
                fv = self._font(fv.size - 6, True)
            ops.append(("stat", (w - fv.getlength(value)) / 2, y, value, fv, accent, off))
            y += int(fv.size * 1.35)
            y = self._add_text(ops, pad, y, _s(sc.get("label")), self._font(w * 0.055 * s),
                               self.fg, off + STAT_UNITS, maxw, align="center")
        elif kind == "image":
            y, off = self._heading(ops, y, sc, s)
            cap = _s(sc.get("caption"))
            avail = (self.bottom - self.top) * (0.62 if cap else 0.88)
            ih = int(min(avail, maxw * 1.25) if self.vertical else avail)
            ops.append(("image", pad, y, maxw, ih, _s(sc.get("image")), _s(sc.get("fit") or "cover"), off))
            y += ih + int(w * 0.05)
            if cap:
                y = self._add_text(ops, pad, y, cap, self._font(w * 0.048 * s), self.fg,
                                   off + IMG_UNITS, maxw, align="center")
        return ops, max(0, y - int(w * 0.03))

    def _layout(self, idx, sc):
        if idx not in self._layouts:
            s = 1.0
            avail = self.bottom - self.top
            for _ in range(8):
                ops, hh = self._build(sc, s)
                if hh <= avail:
                    break
                s *= 0.9
            y0 = self.top + max(0, (avail - hh) // 2)
            self._layouts[idx] = (ops, y0, count_units(sc), sc.get("accent") or self.accent)
        return self._layouts[idx]

    # ---------- images ----------
    def _find_image(self, p):
        p = Path(p.strip())
        for c in ([p] if p.is_absolute() else [b / p for b in self.base_dirs]):
            if c.is_file():
                return c
        return None

    def _base_image(self, path, tw, th, fit):
        key = (str(path), tw, th, fit)
        if key not in self._images:
            im = Image.open(path).convert("RGB")
            iw, ih = im.size
            if fit == "contain":
                sc = min(tw / iw, th / ih)
                im = im.resize((max(1, int(iw * sc)), max(1, int(ih * sc))), Image.LANCZOS)
                canvas = Image.new("RGB", (tw, th), blend(self.theme["bg"], "#000000", 0.4))
                canvas.paste(im, ((tw - im.width) // 2, (th - im.height) // 2))
                im = canvas
            else:
                sc = max(tw * 1.12 / iw, th * 1.12 / ih)
                im = im.resize((max(tw, int(iw * sc)), max(th, int(ih * sc))), Image.LANCZOS)
            self._images[key] = im
        return self._images[key]

    def _mask(self, w, h, r):
        if (w, h) not in self._masks:
            m = Image.new("L", (w, h), 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
            self._masks[(w, h)] = m
        return self._masks[(w, h)]

    # ---------- drawing ----------
    def render(self, idx, sc, k):
        ops, y0, total, accent = self._layout(idx, sc)
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        for op in ops:
            t = op[0]
            if t == "text":
                _, x, y, line, font, fill, off = op
                n = k - off
                if n <= 0:
                    continue
                d.text((x, y0 + y), line[:n], font=font, fill=fill)
                if n < len(line) and k < total:          # typing cursor
                    cx = x + font.getlength(line[:n]) + 3
                    d.rectangle([cx, y0 + y + 4, cx + 4, y0 + y + int(font.size * 1.05)], fill=accent)
            elif t == "rect":
                _, x, y, rw, rh, fill, off = op
                if k >= off:
                    d.rectangle([x, y0 + y, x + rw, y0 + y + rh], fill=fill)
            elif t == "rrect":
                _, x, y, rw, rh, fill, outline, off, rad = op
                if k >= off:
                    d.rounded_rectangle([x, y0 + y, x + rw, y0 + y + rh], radius=rad,
                                        fill=fill, outline=outline, width=3)
            elif t == "dot":
                _, cx, cy, r, fill, off = op
                if k > off:
                    d.ellipse([cx - r, y0 + cy - r, cx + r, y0 + cy + r], fill=fill)
            elif t == "num":
                _, cx, cy, r, label, font, fill, off = op
                if k > off:
                    d.ellipse([cx - r, y0 + cy - r, cx + r, y0 + cy + r], fill=fill)
                    d.text((cx, y0 + cy), label, font=font, fill=self.theme["bg"], anchor="mm")
            elif t == "stat":
                _, x, y, value, font, fill, off = op
                p = max(0.0, min(1.0, (k - off) / STAT_UNITS))
                if k > off - 1:
                    txt = _count_text(value, p)
                    if txt:
                        d.text((x, y0 + y), txt, font=font, fill=fill)
            elif t == "image":
                self._draw_image(img, d, op, k, y0, accent, total)
        return img

    def _draw_image(self, img, d, op, k, y0, accent, total):
        _, x, y, tw, th, rel, fit, off = op
        y += y0
        path = self._find_image(rel)
        if path is None:
            d.rounded_rectangle([x, y, x + tw, y + th], radius=24,
                                fill=blend(self.theme["bg"], "#ffffff", 0.06),
                                outline=self.theme["inactive"], width=3)
            f = self._font(self.w * 0.04)
            lines = _wrap(f"Image not found:\n{rel}", f, tw - 60)
            yy = y + th // 2 - len(lines) * int(f.size * 1.25) // 2
            for line, _ in lines:
                d.text((x + (tw - f.getlength(line)) / 2, yy), line, font=f, fill=self.muted)
                yy += int(f.size * 1.25)
            return
        a = max(0.0, min(1.0, (k - off) / (IMG_UNITS * 0.5)))
        if a <= 0:
            return
        base = self._base_image(path, tw, th, fit)
        if fit == "contain":
            photo = base
        else:
            p = max(0.0, min(1.0, k / max(1, total)))
            z = 1.12 - 0.10 * p
            cw, ch = int(tw * z), int(th * z)
            l, t = (base.width - cw) // 2, (base.height - ch) // 2
            photo = base.crop((l, t, l + cw, t + ch)).resize((tw, th), Image.BILINEAR)
        region = img.crop((x, y, x + tw, y + th))
        photo = Image.blend(region, photo, a) if a < 1 else photo
        img.paste(photo, (x, y), self._mask(tw, th, int(self.w * 0.03)))
