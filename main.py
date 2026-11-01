"""Code Reels — Android front-end (Kivy) for the coding-video-maker pipeline."""
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.utils import escape_markup

from src import topics
from scene_editor import SceneEditor

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_BOOTLOGO" in os.environ


from ui_kit import *  # noqa: F401,F403  (theme, buttons, helpers)


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
        self.editor_ui = SceneEditor(self)
        for scr in self.editor_ui.screens():
            self.sm.add_widget(scr)
        self.refresh_topics()
        keep_screen_on()
        return self.sm

    def on_pause(self):
        return True            # stay alive while Android settings / the image picker are open

    def on_resume(self):
        pass

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

        acts = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(66))
        acts.add_widget(tool_button("\u270e", "Edit", self.open_editor))
        acts.add_widget(tool_button("\uff0b", "New", self.new_topic, tint=rgb("#3DDC97")))
        acts.add_widget(tool_button("\u29c9", "Copy", self.dup_topic))
        acts.add_widget(tool_button("\u2715", "Delete", self.ask_delete, tint=rgb("#FF6B6B")))
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
        self.say(f"Created topic-{n}.", "good")
        self.editor_ui.open(f"topic-{n}")

    def open_editor(self, *_):
        if not self.selected_topic:
            return self.say("Pick a topic first.", "bad")
        self.editor_ui.open(self.selected_topic)

    def dup_topic(self, *_):
        tid = self.selected_topic
        if not tid:
            return self.say("Pick a topic first.", "bad")
        base, new, n = f"{tid}-copy", f"{tid}-copy", 1
        while (topics.TOPICS_DIR / f"{new}.json").exists():
            n += 1
            new = f"{base}{n}"
        try:
            data = json.loads(topics.topic_path(tid).read_text(encoding="utf-8"))
            data["title"] = f"{data.get('title', tid)} (copy)"
            (topics.TOPICS_DIR / f"{new}.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            return self.say(f"Couldn't copy: {e}", "bad")
        self.refresh_topics(select=new)
        self.say(f"Copied to {new}.json", "good")

    def ask_delete(self, *_):
        tid = self.selected_topic
        if not tid:
            return self.say("Pick a topic first.", "bad")
        confirm("Delete this topic?", f"{escape_markup(tid)}.json will be removed. "
                "Videos you already rendered are kept.", "Delete", lambda: self.delete_topic(tid))

    def delete_topic(self, tid):
        try:
            topics.topic_path(tid).unlink()
        except Exception as e:
            return self.say(f"Couldn't delete: {e}", "bad")
        self.selected_topic = None
        self.refresh_topics()
        self.say(f"Deleted {tid}.json", "good")

    # ---------- pick images from the phone ----------
    IMG_REQ = 7731

    def images_dir(self) -> Path:
        if IS_ANDROID:
            if has_storage_access():
                return SHARED_DIR / "images"
            try:
                return Path(_activity().getExternalFilesDir(None).getAbsolutePath()) / "images"
            except Exception:
                pass
        return ROOT / "images"

    def pick_images(self, callback):
        """Open the gallery picker; callback(list_of_paths) runs on the UI thread."""
        if not IS_ANDROID:
            return self.editor_ui.notify("Picking images works on the phone only.", True)
        try:
            from android import activity
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            self._pick_cb = callback
            if not getattr(self, "_bound", False):
                activity.bind(on_activity_result=self._on_result)
                self._bound = True
            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("image/*")
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
            _activity().startActivityForResult(intent, self.IMG_REQ)
        except Exception as e:
            self.editor_ui.notify(f"Can't open the picker: {e}", True)

    def _on_result(self, request, result, data):
        if request != self.IMG_REQ or result != -1 or data is None:
            return
        try:
            from jnius import autoclass
            uris = []
            clip = data.getClipData()
            if clip is not None:
                uris = [clip.getItemAt(i).getUri() for i in range(clip.getItemCount())]
            elif data.getData() is not None:
                uris = [data.getData()]
            resolver = _activity().getContentResolver()
            FileUtils = autoclass("android.os.FileUtils")
            FOS = autoclass("java.io.FileOutputStream")
            out_dir = self.images_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            stamp, paths = time.strftime("%Y%m%d_%H%M%S"), []
            for n, uri in enumerate(uris, 1):
                ext = {"image/png": ".png", "image/webp": ".webp"}.get(
                    str(resolver.getType(uri) or ""), ".jpg")
                dest = out_dir / f"img_{stamp}_{n}{ext}"
                ins, outs = resolver.openInputStream(uri), FOS(str(dest))
                FileUtils.copy(ins, outs)
                ins.close()
                outs.close()
                paths.append(dest)
            cb = self._pick_cb
            Clock.schedule_once(lambda dt: cb(paths), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self.editor_ui.notify(f"Couldn't import: {e}", True), 0)

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
