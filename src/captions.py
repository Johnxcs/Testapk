"""Burned-in captions synced to the narration, with the current word highlighted."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

UI_DIR = Path(__file__).resolve().parent.parent / "fonts" / "ui"


def _weight(word):
    w = max(2, len(word))
    if word[-1:] in ".!?":
        w += 4
    elif word[-1:] in ",;:":
        w += 2
    return w


def build_chunks(text, dur_frames, max_words=4, max_chars=26):
    """-> [{'start','end','words':[(word,start,end)]}] in frames relative to the scene start."""
    words = str(text or "").split()
    if not words or dur_frames <= 0:
        return []
    weights = [_weight(w) for w in words]
    total, acc, starts, ends = sum(weights), 0, [], []
    for wt in weights:
        starts.append(acc / total * dur_frames)
        acc += wt
        ends.append(acc / total * dur_frames)
    groups, cur, chars = [], [], 0
    for i, w in enumerate(words):
        if cur and (len(cur) >= max_words or chars + 1 + len(w) > max_chars):
            groups.append(cur)
            cur, chars = [], 0
        cur.append(i)
        chars += len(w) + (1 if chars else 0)
        if w[-1:] in ".!?":
            groups.append(cur)
            cur, chars = [], 0
    if cur:
        groups.append(cur)
    out = [{"start": starts[g[0]], "end": ends[g[-1]],
            "words": [(words[i], starts[i], ends[i]) for i in g]} for g in groups]
    for a, b in zip(out, out[1:]):
        a["end"] = b["start"]
    return out


class CaptionOverlay:
    def __init__(self, w, h, theme, texts, dur_frames, font_path=None):
        self.w, self.h = w, h
        self.accent = theme["accent"]
        self.chunks = [build_chunks(t, d) for t, d in zip(texts, dur_frames)]
        bold = UI_DIR / "DejaVuSans-Bold.ttf"
        path = str(bold) if bold.is_file() else font_path
        size = int(w * (0.058 if h > w else 0.04))
        self.font = ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)
        self.cy = int(h * (0.70 if h > w else 0.86))
        self.stroke = max(2, int(w * 0.006))
        self._masks = {}

    def _mask(self, bw, bh):
        if (bw, bh) not in self._masks:
            m = Image.new("L", (bw, bh), 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, bw - 1, bh - 1], radius=int(bh * 0.28), fill=150)
            self._masks[(bw, bh)] = m
        return self._masks[(bw, bh)]

    def apply(self, img, scene_idx, frame):
        chunks = self.chunks[scene_idx] if scene_idx < len(self.chunks) else []
        chunk = next((c for c in chunks if c["start"] <= frame < c["end"]), None)
        if chunk is None and chunks and frame >= chunks[-1]["end"]:
            return img                       # speech finished
        if chunk is None:
            return img
        f, maxw = self.font, int(self.w * 0.86)
        space = f.getlength(" ")
        lines, cur, curw = [], [], 0.0
        for word, s, e in chunk["words"]:
            ww = f.getlength(word)
            if cur and curw + space + ww > maxw:
                lines.append((cur, curw))
                cur, curw = [], 0.0
            curw += (space if cur else 0) + ww
            cur.append((word, s, e, ww))
        lines.append((cur, curw))
        lh = int(f.size * 1.3)
        bw = int(max(lw for _, lw in lines) + f.size * 1.2)
        bh = lh * len(lines) + int(f.size * 0.5)
        x0, y0 = (self.w - bw) // 2, self.cy - bh // 2
        img = img.copy()
        img.paste(Image.new("RGB", (bw, bh), (0, 0, 0)), (x0, y0), self._mask(bw, bh))
        d = ImageDraw.Draw(img)
        y = y0 + int(f.size * 0.25)
        for words, lw in lines:
            x = (self.w - lw) / 2
            for word, s, e, ww in words:
                active = s <= frame < e
                d.text((x, y), word, font=f, fill=self.accent if active else "#ffffff",
                       stroke_width=self.stroke, stroke_fill="#000000")
                x += ww + space
            y += lh
        return img
