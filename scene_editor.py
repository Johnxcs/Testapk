"""Form-based topic / scene editor (Kivy): lists scenes and edits each one with proper inputs."""
import copy
import json
import threading
from pathlib import Path

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image as KImage
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput
from kivy.utils import escape_markup

from src import estimate, render_info, settings, topics
from src.config import DEFAULTS, load_config
from src.script_import import script_to_scenes
from src.narration import estimate_duration
from src.scene_templates import TEMPLATES
from ui_kit import (ACCENT, ACCENT_DN, BAD, CARD, CARD2, CARD2_ON, GOOD, MONO, MUTED, ROOT,
                    TEXT, UIFONT, confirm, framed_input, lbl, rgb, style_button, style_card)

# kind -> (label, colour)
KIND_INFO = {
    "title": ("Title", "5B8CFF"), "code": ("Code", "4EC9B0"), "run": ("Run", "FFB86C"),
    "wait": ("Pause", "8A90A0"), "text": ("Text", "C792EA"), "bullets": ("Bullets", "7EE787"),
    "steps": ("Steps", "79C0FF"), "quote": ("Quote", "F78166"), "compare": ("Compare", "FFA657"),
    "stat": ("Stat", "E3B341"), "image": ("Image", "FF7EB6"),
}
LABEL_TO_KIND = {v[0]: k for k, v in KIND_INFO.items()}
KIND_TEMPLATE = {"title": "Title", "code": "Code", "run": "Run", "wait": "Pause", "text": "Text",
                 "bullets": "Bullets", "steps": "Steps", "quote": "Quote", "compare": "Compare",
                 "stat": "Stat", "image": "Image"}

# per-kind form fields: (key, label, type[, extra])
FIELDS = {
    "title": [("title", "Title", "line"), ("subtitle", "Subtitle", "line")],
    "code": [("code_mode", "Code mode", "choice", ["append", "replace"]),
             ("code", "Code", "mono", 230)],
    "run": [("terminal", "Terminal text (first line = typed command, e.g. $ java Main)", "mono", 170)],
    "wait": [],
    "text": [("heading", "Heading", "line"), ("body", "Body text", "multi", 150)],
    "bullets": [("heading", "Heading", "line"), ("items", "Bullet points (one per line)", "lines", 170)],
    "steps": [("heading", "Heading", "line"), ("items", "Steps (one per line)", "lines", 170)],
    "quote": [("text", "Quote", "multi", 150), ("author", "Author", "line")],
    "compare": [("heading", "Heading", "line"),
                ("left.title", "Left title (green)", "line"),
                ("left.items", "Left items (one per line)", "lines", 120),
                ("right.title", "Right title (red)", "line"),
                ("right.items", "Right items (one per line)", "lines", 120)],
    "stat": [("heading", "Heading (optional)", "line"), ("value", "Big value, e.g. 95%", "line"),
             ("label", "Label under the value", "multi", 90)],
    "image": [("heading", "Heading (optional)", "line"), ("image", "Image", "image"),
              ("fit", "Fit", "choice", ["cover", "contain"]), ("caption", "Caption", "multi", 90)],
}
NARRATION = ("narration", "Narration (what the voice says)", "multi", 150)
TOPIC_FIELDS = [("title", "Video title", "My video"), ("handle", "Your handle (shown on the video)", "@yourname"),
                ("filename", "Code file name", "Main.java"), ("language", "Code language", "java")]


class DarkOption(SpinnerOption):
    def __init__(self, **kw):
        super().__init__(**kw)
        style_button(self, CARD2, CARD2_ON, radius=0)
        self.height = dp(46)
        self.font_size = sp(15)


def _get(d, key, default=None):
    for part in key.split("."):
        if not isinstance(d, dict) or part not in d:
            return default
        d = d[part]
    return d


def _set(d, key, value):
    parts = key.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def _del(d, key):
    parts = key.split(".")
    for part in parts[:-1]:
        d = d.get(part)
        if not isinstance(d, dict):
            return
    d.pop(parts[-1], None)


def summary(sc):
    k = sc.get("kind")
    items = [str(i) for i in sc.get("items", [])] if isinstance(sc.get("items"), list) else []
    first = lambda t: next((l.strip() for l in str(t or "").split("\n") if l.strip()), "")
    if k == "code":
        t = first(sc.get("code"))
    elif k == "run":
        t = first(sc.get("terminal"))
    elif k == "title":
        t = str(sc.get("title", ""))
    elif k in ("bullets", "steps"):
        t = (str(sc.get("heading", "")) or (items[0] if items else "")) + (f"  ·  {len(items)} items" if items else "")
    elif k == "compare":
        t = str(sc.get("heading", "")) or f"{_get(sc, 'left.title', '')} vs {_get(sc, 'right.title', '')}"
    elif k == "stat":
        t = f"{sc.get('value', '')}  {sc.get('label', '')}"
    elif k == "image":
        t = Path(str(sc.get("image", ""))).name
    elif k == "quote":
        t = str(sc.get("text", ""))
    elif k == "text":
        t = str(sc.get("heading", "")) or first(sc.get("body"))
    else:
        t = ""
    t = t.strip() or first(sc.get("narration")) or "(empty)"
    return t if len(t) <= 54 else t[:52] + "…"


class SceneEditor:
    def __init__(self, app):
        self.app = app
        self.tid, self.data = None, {}
        try:
            self.cfg = load_config(str(ROOT / "config.json"))
        except BaseException:
            self.cfg = copy.deepcopy(DEFAULTS)
        self.topic_inputs = {}
        self.idx, self.scene, self.inputs = None, {}, {}
        self._screens = [self._build_list(), self._build_form(), self._build_json(), self._build_paste()]

    def screens(self):
        return self._screens

    # ------------------------------------------------------------ list screen
    def _build_list(self):
        scr = Screen(name="scenes")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        bar = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        back = Button(text="‹  Back", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(back)
        back.bind(on_release=self.close)
        self.list_title = lbl("", 16, TEXT, bold=True)
        js = Button(text="JSON", size_hint_x=None, width=dp(76), font_size=sp(14))
        style_button(js)
        js.bind(on_release=self.open_json)
        for w in (back, self.list_title, js):
            bar.add_widget(w)
        root.add_widget(bar)

        chips = ScrollView(size_hint_y=None, height=dp(42), bar_width=0, do_scroll_y=False)
        row = BoxLayout(size_hint_x=None, spacing=dp(8))
        row.bind(minimum_width=row.setter("width"))
        paste = Button(text="Paste script", size_hint_x=None, width=dp(120), font_size=sp(13), bold=True)
        style_button(paste, rgb("#2B6E54"), rgb("#1F5240"), radius=12, fg=(1, 1, 1, 1))
        paste.bind(on_release=self.open_paste)
        row.add_widget(paste)
        pick = Button(text="Pick images", size_hint_x=None, width=dp(120), font_size=sp(13), bold=True)
        style_button(pick, ACCENT, ACCENT_DN, radius=12, fg=(1, 1, 1, 1))
        pick.bind(on_release=lambda *_: self.app.pick_images(self.add_image_scenes))
        row.add_widget(pick)
        for name in TEMPLATES:
            b = Button(text=f"+ {name}", size_hint_x=None, width=dp(30) + dp(9) * len(name), font_size=sp(13))
            style_button(b, CARD2, ACCENT, radius=12)
            b.bind(on_release=lambda _b, n=name: self.new_scene(n))
            row.add_widget(b)
        chips.add_widget(row)
        root.add_widget(chips)

        self.msg = lbl("", 12, MUTED, height=18)
        root.add_widget(self.msg)

        sv = ScrollView(do_scroll_x=False, bar_width=dp(3))
        self.list_box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None,
                                  padding=(0, 0, 0, dp(30)))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        sv.add_widget(self.list_box)
        root.add_widget(sv)
        scr.add_widget(root)
        return scr

    def notify(self, text, bad=False):
        color = BAD if bad else GOOD
        self.msg.text = f"[color={color}]{escape_markup(text)}[/color]"

    def open(self, tid):
        try:
            data = json.loads(topics.topic_path(tid).read_text(encoding="utf-8"))
            if not isinstance(data.get("scenes"), list):
                data["scenes"] = []
        except Exception as e:
            return self.app.say(f"Can't open {tid}: {e}", "bad")
        self.tid, self.data = tid, data
        self.msg.text = ""
        self.refresh_list()
        self.app.go("scenes", "left")

    def close(self, *_):
        self._persist()
        self.app.refresh_topics(select=self.tid)
        self.app.go("home", "right")

    def _sync_topic_fields(self):
        for key, ti in self.topic_inputs.items():
            val = ti.text.strip()
            if val or key == "title":
                self.data[key] = val or self.tid
            else:
                self.data.pop(key, None)

    def _persist(self):
        self._sync_topic_fields()
        topics.topic_path(self.tid).write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def refresh_list(self):
        self.list_title.text = escape_markup(str(self.data.get("title") or self.tid))
        box = self.list_box
        box.clear_widgets()
        # topic details card
        card = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(4),
                         size_hint_y=None, height=dp(12 * 2 + len(TOPIC_FIELDS) * 78))
        style_card(card, CARD, 16)
        self.topic_inputs = {}
        for key, label, hint in TOPIC_FIELDS:
            card.add_widget(lbl(f"[b]{label.upper()}[/b]", 11, MUTED, height=20))
            frame, ti = framed_input(str(self.data.get(key, "")), hint=hint)
            card.add_widget(frame)
            self.topic_inputs[key] = ti
        box.add_widget(card)

        scenes = self.data["scenes"]
        est = estimate.scene_durations(scenes, self.cfg) if scenes else []
        info = render_info.load(self.tid)
        actual = [info.get(render_info.scene_sig(sc)) for sc in scenes]
        durs = [a if a else e for a, e in zip(actual, est)]
        real = sum(1 for a in actual if a)
        total = sum(durs)
        warn = "  \u00b7  over 60s" if total > 60 else ""
        color = "FFB86C" if total > 60 else "3DDC97"
        approx = "" if scenes and real == len(scenes) else "\u2248 "
        head = BoxLayout(size_hint_y=None, height=dp(40), padding=(dp(4), 0))
        head.add_widget(lbl(f"[b]SCENES  ({len(scenes)})[/b]", 11, MUTED, height=40))
        total_lbl = lbl(f"[b][color={color}]{approx}{estimate.fmt(total)}[/color][/b]  [color=8A90A0]total{warn}[/color]",
                        15, TEXT, height=40, halign="right")
        head.add_widget(total_lbl)
        box.add_widget(head)
        if scenes:
            note = ("Real lengths from your last render." if real == len(scenes) else
                    f"{real} of {len(scenes)} scenes have a real length from your last render; the rest are estimates."
                    if real else "Estimates. Render once to see the real lengths.")
            box.add_widget(lbl(note, 11, MUTED, height=16))
        else:
            box.add_widget(lbl("No scenes yet. Tap “+ Title”, “+ Code”, “+ Text”… above.", 14, MUTED, height=40))
        start = 0.0
        for i, sc in enumerate(scenes):
            box.add_widget(self._row(i, sc, start, durs[i], bool(actual[i])))
            start += durs[i]

    def _row(self, i, sc, start=0.0, dur=0.0, real=False):
        label, color = KIND_INFO.get(sc.get("kind"), (str(sc.get("kind")), "8A90A0"))
        row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(78))
        main = Button(
            text=(f"[b]{i + 1}   [color={color}]{label}[/color][/b]"
                  f"   [size={int(sp(13))}][color=8A90A0]{estimate.fmt(start)}  \u00b7  {"" if real else "\u2248 "}{dur:.1f}s{" real" if real else ""}[/color][/size]\n"
                  f"[size={int(sp(13))}][color=8A90A0]{escape_markup(summary(sc))}[/color][/size]"),
            markup=True, halign="left", valign="middle", font_size=sp(16), padding_x=dp(14))
        main.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(28), s[1])))
        style_button(main, CARD, CARD2_ON, radius=14, border=(1, 1, 1, 0.08))
        main.bind(on_release=lambda *_, i=i: self.open_form(i))
        row.add_widget(main)
        grid = GridLayout(cols=2, spacing=dp(4), size_hint_x=None, width=dp(92))
        font = UIFONT if Path(UIFONT).is_file() else "Roboto"
        for glyph, cb, tint in (("\u25b2", lambda *_, i=i: self.move(i, -1), None),
                                ("\u25bc", lambda *_, i=i: self.move(i, 1), None),
                                ("\u29c9", lambda *_, i=i: self.duplicate(i), None),
                                ("\u2715", lambda *_, i=i: self.ask_delete(i), rgb("#FF6B6B"))):
            b = Button(text=glyph, font_name=font, font_size=sp(15))
            style_button(b, CARD2, CARD2_ON, radius=10, fg=tint or TEXT)
            b.bind(on_release=cb)
            grid.add_widget(b)
        row.add_widget(grid)
        return row

    def move(self, i, d):
        scenes, j = self.data["scenes"], i + d
        if 0 <= j < len(scenes):
            scenes[i], scenes[j] = scenes[j], scenes[i]
            self._persist()
            self.refresh_list()

    def duplicate(self, i):
        self.data["scenes"].insert(i + 1, copy.deepcopy(self.data["scenes"][i]))
        self._persist()
        self.refresh_list()
        self.notify(f"Duplicated scene {i + 1}")

    def ask_delete(self, i):
        sc = self.data["scenes"][i]
        label = KIND_INFO.get(sc.get("kind"), (sc.get("kind"), ""))[0]
        confirm("Delete this scene?", f"Scene {i + 1} ({escape_markup(str(label))}) will be removed.",
                "Delete", lambda: self._delete(i))

    def _delete(self, i):
        del self.data["scenes"][i]
        self._persist()
        self.refresh_list()
        self.notify("Scene deleted")

    @staticmethod
    def _insert_index(scenes, sc):
        """Keep a closing title card last."""
        if len(scenes) >= 2 and scenes[-1].get("kind") == "title" and sc.get("kind") != "title":
            return len(scenes) - 1
        return len(scenes)

    def _insert_scene(self, sc):
        scenes = self.data["scenes"]
        scenes.insert(self._insert_index(scenes, sc), sc)

    def add_image_scenes(self, paths, names=None):
        for p in paths:
            self._insert_scene({"kind": "image", "image": str(p), "fit": "cover",
                                "caption": "", "narration": ""})
        self._persist()
        self.refresh_list()
        self.notify(f"Added {len(paths)} image scene(s). Tap one to add a caption.")

    def new_scene(self, template_name):
        self.open_form(None, copy.deepcopy(TEMPLATES[template_name]))

    # ------------------------------------------------------------ scene form
    def _build_form(self):
        scr = Screen(name="scene")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        bar = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cancel = Button(text="Cancel", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(cancel)
        cancel.bind(on_release=lambda *_: self.app.go("scenes", "right"))
        self.form_title = lbl("", 16, TEXT, bold=True, halign="center")
        save = Button(text="Save", size_hint_x=None, width=dp(90), font_size=sp(15), bold=True)
        style_button(save, ACCENT, ACCENT_DN, fg=(1, 1, 1, 1))
        save.bind(on_release=self.save_form)
        for w in (cancel, self.form_title, save):
            bar.add_widget(w)
        root.add_widget(bar)
        self.prev_btn = Button(text="\u25b6  Preview this scene", size_hint_y=None, height=dp(46), font_size=sp(15))
        style_button(self.prev_btn, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
        self.prev_btn.bind(on_release=self.preview)
        root.add_widget(self.prev_btn)
        sv = ScrollView(do_scroll_x=False, bar_width=dp(3))
        self.form_box = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None,
                                  padding=(0, 0, 0, dp(60)))
        self.form_box.bind(minimum_height=self.form_box.setter("height"))
        sv.add_widget(self.form_box)
        root.add_widget(sv)
        scr.add_widget(root)
        return scr

    def open_form(self, idx, template=None):
        self.idx = idx
        self.scene = copy.deepcopy(self.data["scenes"][idx]) if idx is not None else template
        self._form_base = f"Scene {idx + 1}" if idx is not None else "New scene"
        self.form_title.text = self._form_base
        self._render_form()
        self.app.go("scene", "left")

    def _render_form(self):
        box = self.form_box
        box.clear_widgets()
        self.inputs = {}
        kind = self.scene.get("kind", "text")

        box.add_widget(lbl("[b]SCENE TYPE[/b]", 11, MUTED, height=20))
        sp_kind = Spinner(text=KIND_INFO.get(kind, (kind, ""))[0], values=[v[0] for v in KIND_INFO.values()],
                          size_hint_y=None, height=dp(50), font_size=sp(16), option_cls=DarkOption)
        style_button(sp_kind, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
        sp_kind.bind(text=self._on_kind)
        box.add_widget(sp_kind)

        for spec in FIELDS.get(kind, []) + [NARRATION]:
            key, label, typ = spec[0], spec[1], spec[2]
            extra = spec[3] if len(spec) > 3 else None
            box.add_widget(lbl(f"[b]{label.upper()}[/b]", 11, MUTED, height=22))
            value = _get(self.scene, key, "")
            if typ == "line":
                frame, w = framed_input(str(value))
                box.add_widget(frame)
            elif typ in ("multi", "mono"):
                frame, w = framed_input(str(value), multiline=True, height=extra or 140, mono=(typ == "mono"))
                box.add_widget(frame)
            elif typ == "lines":
                text = "\n".join(str(v) for v in value) if isinstance(value, list) else str(value)
                frame, w = framed_input(text, multiline=True, height=extra or 140)
                box.add_widget(frame)
            elif typ == "choice":
                w = Spinner(text=str(value or extra[0]), values=extra, size_hint_y=None, height=dp(50),
                            font_size=sp(16), option_cls=DarkOption)
                style_button(w, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
                box.add_widget(w)
            elif typ == "image":
                w = self._image_field(box, str(value))
            else:
                continue
            self.inputs[key] = (typ, w)

        self.narr_label = lbl("", 12, MUTED, height=22)
        box.add_widget(self.narr_label)
        for _typ, w in self.inputs.values():
            w.bind(text=self._update_time)
        self._update_time()

    def _update_time(self, *_):
        try:
            sc = self._collect()
            dur = estimate.scene_durations([sc], self.cfg)[0]
            text = str(sc.get("narration", "") or "")
            words = len(text.split())
            self.form_title.text = f"{self._form_base}  \u00b7  \u2248 {dur:.1f}s"
            if text.strip():
                self.narr_label.text = (f"Voice \u2248 {estimate_duration(text):.1f}s  ({words} words)  \u00b7  "
                                        f"scene \u2248 {dur:.1f}s")
            else:
                self.narr_label.text = f"No narration: scene \u2248 {dur:.1f}s (typing speed)"
        except Exception:
            pass

    def _image_field(self, box, value):
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(54))
        frame, ti = framed_input(value, hint="images/pic.png  or  /storage/emulated/0/...")
        row.add_widget(frame)
        pick = Button(text="Pick", size_hint_x=None, width=dp(84), font_size=sp(15), bold=True)
        style_button(pick, ACCENT, ACCENT_DN, radius=12, fg=(1, 1, 1, 1))
        pick.bind(on_release=lambda *_: self.app.pick_images(
            lambda paths, names=None: setattr(ti, "text", str(paths[0])) if paths else None))
        row.add_widget(pick)
        box.add_widget(row)
        preview = KImage(size_hint_y=None, height=dp(170), allow_stretch=True, keep_ratio=True)
        box.add_widget(preview)

        def update(*_):
            t = ti.text.strip()
            for cand in (Path(t), ROOT / t, Path("/storage/emulated/0/CodeReels") / t):
                if t and cand.is_file():
                    preview.source = str(cand)
                    preview.height = dp(170)
                    return
            preview.source = ""
            preview.height = 0
        ti.bind(text=update)
        update()
        return ti

    def _read(self, typ, w):
        if typ == "lines":
            return [l.strip() for l in w.text.split("\n") if l.strip()]
        return w.text

    def _collect(self):
        sc = copy.deepcopy(self.scene)
        for key, (typ, w) in self.inputs.items():
            v = self._read(typ, w)
            if key == "narration" or v not in ("", []):
                _set(sc, key, v)
            else:
                _del(sc, key)
        return sc

    def _on_kind(self, spinner, text):
        new_kind = LABEL_TO_KIND.get(text)
        if not new_kind or new_kind == self.scene.get("kind"):
            return
        old = self._collect()
        new = copy.deepcopy(TEMPLATES[KIND_TEMPLATE[new_kind]])
        new["narration"] = old.get("narration", "")
        if "heading" in new and old.get("title"):
            new["heading"] = old["title"]
        self.scene = new
        Clock.schedule_once(lambda dt: self._render_form(), 0)

    def preview(self, *_):
        """Render one still frame of this scene (with your settings) and show it."""
        sc = self._collect()
        data = copy.deepcopy(self.data)
        scenes = data["scenes"]
        if self.idx is None:
            i = self._insert_index(scenes, sc)
            scenes.insert(i, sc)
        else:
            i = self.idx
            scenes[i] = sc
        self.prev_btn.disabled = True
        self.prev_btn.text = "Rendering preview\u2026"
        base = topics.TOPICS_DIR / f"{self.tid}.json"

        def work():
            try:
                from src import video
                img = video.preview_scene(data, i, self.cfg, settings.render_overrides(), self.tid, base)
                img.thumbnail((960, 960))
                out = settings.data_dir() / "preview.png"
                img.save(out)
                Clock.schedule_once(lambda dt: self._show_preview(str(out), ""), 0)
            except BaseException as e:      # topics/video raise SystemExit with messages
                Clock.schedule_once(lambda dt, m=str(e): self._show_preview("", m), 0)
        threading.Thread(target=work, daemon=True).start()

    def _show_preview(self, path, error):
        self.prev_btn.disabled = False
        self.prev_btn.text = "\u25b6  Preview this scene"
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        style_card(box, CARD, 18)
        if error:
            box.add_widget(lbl(f"[color={BAD}]Couldn't make the preview: {escape_markup(error)}[/color]", 14, TEXT))
        else:
            box.add_widget(KImage(source=path, nocache=True, allow_stretch=True, keep_ratio=True))
            box.add_widget(lbl("Estimated look. Tap outside to close.", 11, MUTED, height=18, halign="center"))
        Popup(title="", separator_height=0, content=box, size_hint=(0.94, 0.92), background="",
              background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.7)).open()

    def save_form(self, *_):
        sc = self._collect()
        if self.idx is None:
            self._insert_scene(sc)
        else:
            self.data["scenes"][self.idx] = sc
        self._persist()
        self.refresh_list()
        self.notify("Scene saved")
        self.app.go("scenes", "right")

    # ------------------------------------------------------------ paste a script
    def _build_paste(self):
        scr = Screen(name="paste")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        bar = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cancel = Button(text="Cancel", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(cancel)
        cancel.bind(on_release=lambda *_: self.app.go("scenes", "right"))
        bar.add_widget(cancel)
        bar.add_widget(lbl("Paste script", 16, TEXT, bold=True, halign="center"))
        add = Button(text="Add", size_hint_x=None, width=dp(90), font_size=sp(15), bold=True)
        style_button(add, ACCENT, ACCENT_DN, fg=(1, 1, 1, 1))
        add.bind(on_release=self.add_pasted)
        bar.add_widget(add)
        root.add_widget(bar)
        root.add_widget(lbl("Blank line = new scene.  # heading   - bullets   1. steps   > quote   ``` code", 11, MUTED, height=28))
        frame, self.paste_in = framed_input("", multiline=True, height=300,
                                            hint="Paste your notes or script here\u2026")
        frame.size_hint_y = 1
        self.paste_in.size_hint_y = 1
        self.paste_in.bind(text=self._paste_update)
        root.add_widget(frame)
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(40))
        self.paste_title = CheckBox(size_hint_x=None, width=dp(36), active=True, color=ACCENT)
        self.paste_title.bind(active=self._paste_update)
        row.add_widget(self.paste_title)
        row.add_widget(lbl("Add a title card and a closing card", 14, TEXT, height=40))
        root.add_widget(row)
        self.paste_count = lbl("", 13, MUTED, height=24)
        root.add_widget(self.paste_count)
        scr.add_widget(root)
        return scr

    def open_paste(self, *_):
        self.paste_in.text = ""
        self.paste_title.active = not self.data["scenes"]
        self._paste_update()
        self.app.go("paste", "left")

    def _paste_update(self, *_):
        n = len(script_to_scenes(self.paste_in.text, add_title=self.paste_title.active))
        self.paste_count.text = f"Will add {n} scene{'s' if n != 1 else ''}" if n else "Nothing to add yet"

    def add_pasted(self, *_):
        new = script_to_scenes(self.paste_in.text, add_title=self.paste_title.active)
        if not new:
            return
        scenes = self.data["scenes"]
        closing = len(scenes) >= 2 and scenes[-1].get("kind") == "title"
        pos = len(scenes) - 1 if (closing and not self.paste_title.active) else len(scenes)
        scenes[pos:pos] = new
        self._persist()
        self.refresh_list()
        self.notify(f"Added {len(new)} scene(s) from your script. Tap one to adjust it.")
        self.app.go("scenes", "right")

    # ------------------------------------------------------------ raw JSON (advanced)
    def _build_json(self):
        scr = Screen(name="json")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        bar = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        back = Button(text="‹  Back", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(back)
        back.bind(on_release=lambda *_: self.app.go("scenes", "right"))
        bar.add_widget(back)
        bar.add_widget(lbl("Advanced: raw JSON", 16, TEXT, bold=True))
        save = Button(text="Save", size_hint_x=None, width=dp(90), font_size=sp(15), bold=True)
        style_button(save, ACCENT, ACCENT_DN, fg=(1, 1, 1, 1))
        save.bind(on_release=self.save_json)
        bar.add_widget(save)
        root.add_widget(bar)
        frame, self.json_input = framed_input("", multiline=True, height=400, mono=True)
        frame.size_hint_y = 1
        self.json_input.size_hint_y = 1
        root.add_widget(frame)
        self.json_msg = lbl("", 12, MUTED, height=20)
        root.add_widget(self.json_msg)
        scr.add_widget(root)
        return scr

    def open_json(self, *_):
        self._sync_topic_fields()
        self.json_input.text = json.dumps(self.data, indent=2, ensure_ascii=False)
        self.json_msg.text = ""
        self.app.go("json", "left")

    def save_json(self, *_):
        try:
            data = json.loads(self.json_input.text)
            if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
                raise ValueError('needs a "scenes" list')
        except Exception as e:
            self.json_msg.text = f"[color={BAD}]Invalid JSON, not saved: {escape_markup(str(e))}[/color]"
            return
        self.data = data
        self._persist()
        self.refresh_list()
        self.app.go("scenes", "right")
