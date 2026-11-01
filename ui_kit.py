"""Shared look & widgets for the Code Reels app (Kivy)."""
from pathlib import Path

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget

ROOT = Path(__file__).resolve().parent


# ------------------------------- theme -------------------------------
def rgb(h, a=1.0):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


BG = rgb("#0F1115")
CARD = rgb("#181B22")
CARD2 = rgb("#232834")
CARD2_ON = rgb("#323A4D")
ACCENT = rgb("#5B8CFF")
ACCENT_DN = rgb("#3F6FE0")
DISABLED = rgb("#2A2F3B")
TEXT = rgb("#E8EAF0")
MUTED = rgb("#8A90A0")
GOOD, BAD, MUTED_HEX = "3DDC97", "FF6B6B", "8A90A0"
MONO = str(ROOT / "fonts" / "DejaVuSansMono.ttf")


def style_card(w, bg=CARD, radius=16):
    with w.canvas.before:
        col = Color(*bg)
        rr = RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(radius)])

    def upd(*_):
        rr.pos, rr.size = w.pos, w.size
    w.bind(pos=upd, size=upd)
    return w


def style_button(w, bg=CARD2, bg_on=CARD2_ON, radius=14, fg=TEXT, border=None):
    """Flat rounded button; `bg_on` is the pressed colour (or selected colour for toggles)."""
    w.background_normal = ""
    w.background_down = ""
    w.background_color = (0, 0, 0, 0)
    w.color = fg
    w.disabled_color = (1, 1, 1, 0.55)
    with w.canvas.before:
        col = Color(*bg)
        rr = RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(radius)])
        if border:
            Color(*border)
            ln = Line(rounded_rectangle=(w.x, w.y, w.width, w.height, dp(radius)), width=dp(1))

    def upd(*_):
        col.rgba = DISABLED if w.disabled else (bg_on if w.state == "down" else bg)
        rr.pos, rr.size = w.pos, w.size
        if border:
            ln.rounded_rectangle = (w.x, w.y, w.width, w.height, dp(radius))
    w.bind(pos=upd, size=upd, state=upd, disabled=upd)
    upd()
    return w


UIFONT = str(ROOT / "fonts" / "ui" / "DejaVuSans.ttf")


def tool_button(glyph, label, cb, tint=None):
    """Toolbar button: big glyph over a small label."""
    g = f"[font={UIFONT}]{glyph}[/font]" if Path(UIFONT).is_file() else glyph
    color = "%02x%02x%02x" % tuple(int(c * 255) for c in (tint or TEXT)[:3])
    b = Button(text=f"[size={int(sp(22))}][color={color}]{g}[/color][/size]\n"
                    f"[size={int(sp(12))}]{label}[/size]",
               markup=True, halign="center", valign="middle")
    bg = blend_rgba(CARD2, tint, 0.16) if tint else CARD2
    style_button(b, bg, CARD2_ON, radius=16, fg=(tint or TEXT), border=blend_rgba(bg, (1, 1, 1, 1), 0.10))
    b.bind(on_release=cb)
    return b


def blend_rgba(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3)) + (1.0,)


def lbl(text, size=14, color=TEXT, bold=False, height=None, halign="left"):
    l = Label(text=text, font_size=sp(size), color=color, bold=bold, markup=True,
              halign=halign, valign="middle")
    if height:
        l.size_hint_y = None
        l.height = dp(height)
    l.bind(size=lambda i, s: setattr(i, "text_size", s))
    return l


def segmented(options, group, default):
    row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(42))
    btns = {}
    for o in options:
        b = ToggleButton(text=o, group=group, allow_no_selection=False,
                         state="down" if o == default else "normal", font_size=sp(14))
        style_button(b, CARD2, ACCENT, radius=11)
        row.add_widget(b)
        btns[o] = b
    return row, btns


def selected(btns):
    return next(k for k, b in btns.items() if b.state == "down")


class Bar(Widget):
    value = NumericProperty(0)

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas:
            Color(*CARD2)
            self._t = RoundedRectangle(radius=[dp(5)])
            Color(*ACCENT)
            self._f = RoundedRectangle(radius=[dp(5)])
        self.bind(pos=self._u, size=self._u, value=self._u)

    def _u(self, *_):
        self._t.pos, self._t.size = self.pos, self.size
        w = max(0, min(100, self.value)) / 100 * self.width
        self._f.pos, self._f.size = self.pos, (w, self.height)


def confirm(title, message, yes_text, on_yes, danger=True):
    """Dark confirmation popup. `message` must already be markup-safe."""
    box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))
    style_card(box, CARD, 20)
    box.add_widget(lbl(f"[b]{title}[/b]", 18, TEXT, height=30))
    box.add_widget(lbl(message, 14, MUTED))
    row = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(48))
    pop = Popup(title="", separator_height=0, content=box, auto_dismiss=True,
                size_hint=(0.88, None), height=dp(220), background="",
                background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.65))
    no = Button(text="Cancel", font_size=sp(15))
    style_button(no, CARD2, CARD2_ON, radius=14)
    no.bind(on_release=lambda *_: pop.dismiss())
    yes = Button(text=f"[b]{yes_text}[/b]", markup=True, font_size=sp(15))
    if danger:
        style_button(yes, rgb("#E5484D"), rgb("#B8393D"), radius=14, fg=(1, 1, 1, 1))
    else:
        style_button(yes, ACCENT, ACCENT_DN, radius=14, fg=(1, 1, 1, 1))
    yes.bind(on_release=lambda *_: (pop.dismiss(), on_yes()))
    row.add_widget(no)
    row.add_widget(yes)
    box.add_widget(row)
    pop.open()


def framed_input(text="", multiline=False, height=46, mono=False, hint=""):
    """Rounded text box. Returns (frame, text_input)."""
    ti = TextInput(text=text, multiline=multiline, size_hint_y=None, height=dp(height),
                   hint_text=hint, write_tab=False, background_normal="",
                   background_active="", background_color=(0, 0, 0, 0),
                   foreground_color=TEXT, cursor_color=ACCENT,
                   hint_text_color=(1, 1, 1, 0.28),
                   selection_color=(0.36, 0.55, 1, 0.35), font_size=sp(15),
                   padding=[dp(10), dp(12), dp(10), dp(12)])
    if mono and Path(MONO).is_file():
        ti.font_name = MONO
        ti.font_size = sp(13)
    frame = BoxLayout(size_hint_y=None, height=dp(height) + dp(8), padding=dp(4))
    style_card(frame, CARD2, 12)
    frame.add_widget(ti)
    return frame, ti
