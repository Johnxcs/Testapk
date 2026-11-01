"""Code Reels — Android front-end (Kivy) for the coding-video-maker pipeline."""
import json
import os
import re
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.utils import escape_markup

from src import topics

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_BOOTLOGO" in os.environ


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


def style_button(w, bg=CARD2, bg_on=CARD2_ON, radius=14, fg=TEXT):
    """Flat rounded button; `bg_on` is the pressed colour (or selected colour for toggles)."""
    w.background_normal = ""
    w.background_down = ""
    w.background_color = (0, 0, 0, 0)
    w.color = fg
    w.disabled_color = (1, 1, 1, 0.55)
    with w.canvas.before:
        col = Color(*bg)
        rr = RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(radius)])

    def upd(*_):
        col.rgba = DISABLED if w.disabled else (bg_on if w.state == "down" else bg)
        rr.pos, rr.size = w.pos, w.size
    w.bind(pos=upd, size=upd, state=upd, disabled=upd)
    upd()
    return w


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


# ---------------------------- Android helpers ----------------------------
def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


SHARED_DIR = Path("/storage/emulated/0/CodeReels")


def _sdk():
    from jnius import autoclass
    return autoclass("android.os.Build$VERSION").SDK_INT


def has_storage_access() -> bool:
    """True when the app may create /storage/emulated/0/CodeReels."""
    if not IS_ANDROID:
        return True
    try:
        if _sdk() >= 30:
            from jnius import autoclass
            return bool(autoclass("android.os.Environment").isExternalStorageManager())
        from android.permissions import Permission, check_permission
        return bool(check_permission(Permission.WRITE_EXTERNAL_STORAGE))
    except Exception:
        return False


def request_storage_access():
    try:
        if _sdk() >= 30:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            Uri = autoclass("android.net.Uri")
            act = _activity()
            intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                            Uri.parse("package:" + act.getPackageName()))
            act.startActivity(intent)
        else:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.WRITE_EXTERNAL_STORAGE,
                                 Permission.READ_EXTERNAL_STORAGE])
    except Exception as e:
        print(f"(could not open permission screen: {e})")


def output_dir() -> Path:
    """Preferred: /storage/emulated/0/CodeReels. Fallback: the app's own folder."""
    if IS_ANDROID:
        if has_storage_access():
            try:
                SHARED_DIR.mkdir(parents=True, exist_ok=True)
                return SHARED_DIR
            except OSError:
                pass
        try:
            return Path(_activity().getExternalFilesDir(None).getAbsolutePath()) / "output"
        except Exception:
            pass
    return ROOT / "output"


def scan_file(path):
    """Make a file show up in Gallery."""
    try:
        from jnius import autoclass
        autoclass("android.media.MediaScannerConnection").scanFile(
            _activity(), [str(path)], None, None)
    except Exception:
        pass


def keep_screen_on():
    if not IS_ANDROID:
        return
    try:
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def _go():
            _activity().getWindow().addFlags(128)  # FLAG_KEEP_SCREEN_ON
        _go()
    except Exception:
        pass


def publish_to_gallery(mp4: Path, display_name: str) -> bool:
    """Copy the finished video into Movies/CodeReels (visible in Gallery). Android 10+."""
    if not IS_ANDROID:
        return False
    try:
        from jnius import autoclass
        ContentValues = autoclass("android.content.ContentValues")
        Media = autoclass("android.provider.MediaStore$Video$Media")
        resolver = _activity().getContentResolver()
        v = ContentValues()
        v.put("_display_name", display_name)
        v.put("mime_type", "video/mp4")
        v.put("relative_path", "Movies/CodeReels")
        uri = resolver.insert(Media.EXTERNAL_CONTENT_URI, v)
        out = resolver.openOutputStream(uri)
        with open(mp4, "rb") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk, 0, len(chunk))
        out.close()
        return True
    except Exception as e:
        print(f"(could not copy to Gallery: {e})")
        return False


class _LogStream:
    def __init__(self, on_line):
        self.on_line = on_line

    def write(self, s):
        for line in s.replace("\r", "\n").split("\n"):
            if line.strip():
                self.on_line(line.strip())
        return len(s)

    def flush(self):
        pass


# ---------------------------------- app ----------------------------------
class ReelsApp(App):
    title = "Code Reels"

    def build(self):
        Window.clearcolor = BG
        if IS_ANDROID:
            Window.softinput_mode = "resize"
        self.selected_topic = None
        self.sm = ScreenManager(transition=SlideTransition(duration=0.18))
        self.sm.add_widget(self._home())
        self.sm.add_widget(self._editor())
        self.refresh_topics()
        keep_screen_on()
        return self.sm

    # ---------- home screen ----------
    def _home(self):
        scr = Screen(name="home")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        head = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(62))
        head.add_widget(lbl("[b]Code Reels[/b]", 28, TEXT, height=38))
        head.add_widget(lbl("Typing-code videos with voice-over", 13, MUTED, height=20))
        root.add_widget(head)

        root.add_widget(lbl("[b]TOPIC[/b]", 11, MUTED, height=16))
        sv = ScrollView(bar_width=0, do_scroll_x=False)
        self.topic_box = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.topic_box.bind(minimum_height=self.topic_box.setter("height"))
        sv.add_widget(self.topic_box)
        root.add_widget(sv)

        opts = style_card(BoxLayout(orientation="vertical", padding=dp(14),
                                    spacing=dp(8), size_hint_y=None, height=dp(180)))
        opts.add_widget(lbl("[b]FRAME RATE[/b]", 11, MUTED, height=16))
        row, self.fps_btns = segmented(["24", "30", "60"], "fps", "30")
        opts.add_widget(row)
        opts.add_widget(lbl("[b]NARRATION[/b]", 11, MUTED, height=16))
        row, self.voice_btns = segmented(["Voice-over", "Silent"], "voice", "Voice-over")
        opts.add_widget(row)
        root.add_widget(opts)

        acts = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(48))
        for text, cb in (("Edit JSON", self.open_editor), ("+  New topic", self.new_topic)):
            b = Button(text=text, font_size=sp(15))
            style_button(b)
            b.bind(on_release=cb)
            acts.add_widget(b)
        root.add_widget(acts)

        self.render_btn = Button(text="[b]Render video[/b]", markup=True, font_size=sp(18),
                                 size_hint_y=None, height=dp(60))
        style_button(self.render_btn, ACCENT, ACCENT_DN, radius=18, fg=(1, 1, 1, 1))
        self.render_btn.bind(on_release=self.start_render)
        root.add_widget(self.render_btn)

        self.bar = Bar(size_hint_y=None, height=dp(10))
        root.add_widget(self.bar)
        self.status = lbl("Ready.", 12, MUTED, height=40)
        root.add_widget(self.status)

        scr.add_widget(root)
        return scr

    # ---------- editor screen ----------
    def _editor(self):
        scr = Screen(name="edit")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        bar = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(48))
        back = Button(text="‹  Back", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(back)
        back.bind(on_release=lambda *_: self.go("home", "right"))
        self.edit_title = lbl("", 16, TEXT, bold=True)
        save = Button(text="Save", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(save, ACCENT, ACCENT_DN, fg=(1, 1, 1, 1))
        save.bind(on_release=self.save_topic)
        for w in (back, self.edit_title, save):
            bar.add_widget(w)
        root.add_widget(bar)

        self.editor = TextInput(
            multiline=True, font_name=MONO if Path(MONO).is_file() else "Roboto",
            font_size=sp(13), background_normal="", background_active="",
            background_color=CARD, foreground_color=TEXT, cursor_color=ACCENT,
            selection_color=(0.36, 0.55, 1, 0.35), padding=[dp(14), dp(14)])
        root.add_widget(self.editor)
        self.edit_msg = lbl("", 12, MUTED, height=20)
        root.add_widget(self.edit_msg)
        scr.add_widget(root)
        return scr

    def go(self, name, direction):
        self.sm.transition.direction = direction
        self.sm.current = name

    # ---------- topics ----------
    def refresh_topics(self, select=None):
        ids = topics.list_topics()
        self.topic_box.clear_widgets()
        if not ids:
            self.selected_topic = None
            self.topic_box.add_widget(lbl("No topics yet. Tap “New topic”.", 14, MUTED, height=40))
            return
        if select in ids:
            self.selected_topic = select
        elif self.selected_topic not in ids:
            self.selected_topic = ids[0]
        for tid in ids:
            title, n = tid, 0
            try:
                data = json.loads(topics.topic_path(tid).read_text(encoding="utf-8"))
                title = data.get("title", tid)
                n = len(data.get("scenes", []))
            except Exception:
                title = f"{tid}  (invalid JSON)"
            b = ToggleButton(
                text=f"[b]{escape_markup(title)}[/b]\n"
                     f"[size={int(sp(12))}][color={MUTED_HEX}]{n} scenes  ·  {escape_markup(tid)}[/color][/size]",
                markup=True, group="topic", allow_no_selection=False,
                state="down" if tid == self.selected_topic else "normal",
                size_hint_y=None, height=dp(66), font_size=sp(16),
                halign="left", valign="middle", padding_x=dp(16))
            b.bind(size=lambda i, s: setattr(i, "text_size", (s[0] - dp(32), s[1])))
            style_button(b, CARD, rgb("#27407A"), radius=14)
            b.bind(state=lambda inst, st, t=tid: self._pick(t) if st == "down" else None)
            self.topic_box.add_widget(b)

    def _pick(self, tid):
        self.selected_topic = tid

    def new_topic(self, *_):
        n = 1
        while (topics.TOPICS_DIR / f"topic-{n}.json").exists():
            n += 1
        topics.create(f"topic-{n}")
        self.refresh_topics(select=f"topic-{n}")
        self.say(f"Created topic-{n}. Tap “Edit JSON” to change it.", "good")

    def open_editor(self, *_):
        if not self.selected_topic:
            return self.say("Pick a topic first.", "bad")
        self.edit_title.text = f"{self.selected_topic}.json"
        self.edit_msg.text = ""
        self.editor.text = topics.topic_path(self.selected_topic).read_text(encoding="utf-8")
        self.go("edit", "left")

    def save_topic(self, *_):
        try:
            json.loads(self.editor.text)
        except json.JSONDecodeError as e:
            self.edit_msg.text = f"[color={BAD}]Invalid JSON, not saved: {escape_markup(str(e))}[/color]"
            return
        topics.topic_path(self.selected_topic).write_text(self.editor.text, encoding="utf-8")
        self.refresh_topics(select=self.selected_topic)
        self.say(f"Saved {self.selected_topic}.json", "good")
        self.go("home", "right")

    # ---------- rendering ----------
    def say(self, msg, kind="info"):
        color = {"good": GOOD, "bad": BAD}.get(kind, MUTED_HEX)
        Clock.schedule_once(
            lambda dt: setattr(self.status, "text", f"[color={color}]{escape_markup(msg)}[/color]"), 0)

    def _on_line(self, line):
        m = re.search(r"\((\d+)%\)", line)
        if m:
            pct = int(m.group(1))
            Clock.schedule_once(lambda dt: self._progress(pct), 0)
        self.say(line)

    def _progress(self, pct):
        self.bar.value = pct
        self.render_btn.text = f"[b]Rendering…  {pct}%[/b]"

    def start_render(self, *_):
        if not self.selected_topic:
            return self.say("Pick a topic first.", "bad")
        if IS_ANDROID and not has_storage_access() and not getattr(self, "_asked", False):
            self._asked = True
            request_storage_access()
            return self.say("Turn on “Allow access to all files” for Code Reels, "
                            "come back, then tap Render again.", "info")
        self.render_btn.disabled = True
        self.render_btn.text = "[b]Starting…[/b]"
        self.bar.value = 0
        fps = int(selected(self.fps_btns))
        silent = selected(self.voice_btns) == "Silent"
        threading.Thread(target=self._render, daemon=True,
                         args=(self.selected_topic, fps, silent)).start()

    def _render(self, tid, fps, silent):
        old = sys.stdout
        sys.stdout = _LogStream(self._on_line)
        try:
            from src.config import load_config
            from src.video import render_topic
            cfg = load_config(str(ROOT / "config.json"))
            out = output_dir()
            mp4 = Path(render_topic(tid, cfg, {"fps": fps, "out": str(out),
                                               "no_audio": silent}))
            if out == SHARED_DIR:
                scan_file(mp4)
                self.say(f"Done. Saved to CodeReels/{mp4.parent.name}/{mp4.name}", "good")
            elif publish_to_gallery(mp4, f"{tid}.mp4"):
                self.say(f"Done. Saved to Movies/CodeReels/{tid}.mp4", "good")
            else:
                self.say(f"Done. {mp4}", "good")
            Clock.schedule_once(lambda dt: setattr(self.bar, "value", 100), 0)
        except BaseException as e:  # topics.py raises SystemExit with messages
            import traceback
            traceback.print_exc(file=sys.__stderr__)
            self.say(f"Couldn't render: {e}", "bad")
        finally:
            sys.stdout = old

            def reset(dt):
                self.render_btn.disabled = False
                self.render_btn.text = "[b]Render video[/b]"
            Clock.schedule_once(reset, 0)


if __name__ == "__main__":
    ReelsApp().run()
