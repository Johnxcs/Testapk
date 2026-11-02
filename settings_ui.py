"""Settings screen: look, voice, music (all saved to settings.json as you change them)."""
import threading
from pathlib import Path

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.screenmanager import Screen
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.togglebutton import ToggleButton
from kivy.utils import escape_markup

from scene_editor import DarkOption
from src import music_check, settings
from src.theme import THEMES
from ui_kit import (MUTED_HEX, ACCENT, ACCENT_DN, BAD, CARD, CARD2, CARD2_ON, GOOD, MUTED, TEXT, confirm,
                    framed_input, lbl, scroll_column, style_button, style_card)

LAYOUTS = {"Vertical 9:16": "vertical", "Horizontal 16:9": "horizontal"}
AUTO_VOICE = "Automatic (Filipino first)"


def _spinner(values, text):
    s = Spinner(text=text, values=values, size_hint_y=None, height=dp(48), font_size=sp(15),
                option_cls=DarkOption)
    style_button(s, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
    return s


class SettingsScreen:
    def __init__(self, app):
        self.app = app
        self.voices = []
        self._loading = False
        self._building = False
        self._dirty = set()
        self.scr = self._build()
        self.check = MusicCheck(app, self)

    def screen(self):
        return self.scr

    def screens(self):
        return [self.scr, self.check.scr]

    # ------------------------------------------------------------------ build
    def _build(self):
        scr = Screen(name="settings")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        bar = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        back = Button(text="‹  Back", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(back)
        back.bind(on_release=self.close)
        bar.add_widget(back)
        bar.add_widget(lbl("Settings", 18, TEXT, bold=True, halign="center"))
        bar.add_widget(BoxLayout(size_hint_x=None, width=dp(90)))
        root.add_widget(bar)

        sv, box = scroll_column(spacing=10, padding=(0, 0, 0, dp(60)))
        root.add_widget(sv)
        scr.add_widget(root)

        # ---- LOOK
        look = self._card(box, "LOOK")
        look.add_widget(lbl("Theme", 12, MUTED, height=20))
        self.theme_sp = _spinner(sorted(THEMES), "dark-plus")
        self.theme_sp.bind(text=lambda *_: self._changed("theme"))
        look.add_widget(self.theme_sp)
        look.add_widget(lbl("Video shape", 12, MUTED, height=20))
        self.layout_btns = self._segmented(look, list(LAYOUTS), "layout", "layout")
        look.add_widget(lbl("Cursor", 12, MUTED, height=20))
        self.cursor_btns = self._segmented(look, ["Bar", "Block"], "cursor", "cursor")
        self.font_lbl = lbl("", 12, MUTED, height=20)
        look.add_widget(self.font_lbl)
        self.font_sl = self._slider(look, 24, 48, 1, 34)
        self.font_sl.bind(value=lambda *_: (self._font_label(), self._changed("font_size")))
        look.add_widget(lbl("Your handle (shown on the video)", 12, MUTED, height=20))
        frame, self.handle_in = framed_input("", hint="@yourname")
        self.handle_in.bind(text=lambda *_: self._changed("handle"))
        look.add_widget(frame)
        self._fit(look)

        # ---- VOICE
        voice = self._card(box, "VOICE")
        self.voice_note = lbl("", 12, MUTED, height=20)
        voice.add_widget(self.voice_note)
        voice.add_widget(lbl("Language", 12, MUTED, height=20))
        self.lang_sp = _spinner([], "Loading…")
        self.lang_sp.bind(text=self._on_lang)
        voice.add_widget(self.lang_sp)
        voice.add_widget(lbl("Voice", 12, MUTED, height=20))
        self.voice_sp = _spinner([], AUTO_VOICE)
        self.voice_sp.bind(text=lambda *_: self._changed("voice"))
        voice.add_widget(self.voice_sp)
        self.rate_lbl = lbl("", 12, MUTED, height=20)
        voice.add_widget(self.rate_lbl)
        self.rate_sl = self._slider(voice, 0.6, 1.6, 0.05, 1.0)
        self.rate_sl.bind(value=lambda *_: (self._rate_label(), self._changed("speech_rate")))
        test = Button(text="▶  Test voice", size_hint_y=None, height=dp(46), font_size=sp(15))
        style_button(test, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
        test.bind(on_release=self.test_voice)
        voice.add_widget(test)
        self._fit(voice)

        # ---- MUSIC
        music = self._card(box, "BACKGROUND MUSIC")
        self.music_lbl = lbl("", 14, TEXT, height=26)
        music.add_widget(self.music_lbl)
        row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(46))
        pick = Button(text="Choose song", font_size=sp(15), bold=True)
        style_button(pick, ACCENT, ACCENT_DN, radius=12, fg=(1, 1, 1, 1))
        pick.bind(on_release=self.pick_music)
        clear = Button(text="Remove", font_size=sp(15), size_hint_x=0.5)
        style_button(clear, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
        clear.bind(on_release=self.clear_music)
        row.add_widget(pick)
        row.add_widget(clear)
        music.add_widget(row)
        self.lic_lbl = lbl("", 12, MUTED, height=20)
        music.add_widget(self.lic_lbl)
        chk = Button(text="Check copyright / change licence", size_hint_y=None, height=dp(44), font_size=sp(14))
        style_button(chk, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
        chk.bind(on_release=self.recheck_music)
        music.add_widget(chk)
        self.vol_lbl = lbl("", 12, MUTED, height=20)
        music.add_widget(self.vol_lbl)
        self.vol_sl = self._slider(music, 5, 50, 1, 15)
        self.vol_sl.bind(value=lambda *_: (self._vol_label(), self._changed("music_volume")))
        music.add_widget(lbl("Turn music on or off with the Music box on the home screen.", 11, MUTED, height=18))
        self._fit(music)

        txt = self._card(box, "APP TEXT")
        eb = Button(text="Edit Home & About text", size_hint_y=None, height=dp(46), font_size=sp(15))
        style_button(eb, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
        eb.bind(on_release=lambda *_: self.app.content_ui.open())
        txt.add_widget(eb)
        self._fit(txt)
        return scr

    def _card(self, box, title):
        card = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(6), size_hint_y=None)
        style_card(card, CARD, 16)
        card.add_widget(lbl(f"[b]{title}[/b]", 11, ACCENT, height=22))
        box.add_widget(card)
        return card

    def _fit(self, card):
        """Card height = sum of children (they all have fixed heights)."""
        card.height = sum(c.height for c in card.children) + dp(6) * (len(card.children) - 1) + dp(28)

    def _slider(self, parent, lo, hi, step, val):
        sl = Slider(min=lo, max=hi, step=step, value=val, size_hint_y=None, height=dp(38),
                    value_track=True, value_track_color=ACCENT, cursor_size=(dp(24), dp(24)))
        parent.add_widget(sl)
        return sl

    def _segmented(self, parent, options, group, key):
        row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(42))
        btns = {}
        for o in options:
            b = ToggleButton(text=o, group=group, allow_no_selection=False, font_size=sp(14))
            style_button(b, CARD2, ACCENT, radius=11)
            b.bind(state=lambda *_, k=key: self._changed(k))
            row.add_widget(b)
            btns[o] = b
        parent.add_widget(row)
        return btns

    @staticmethod
    def _chosen(btns):
        return next((k for k, b in btns.items() if b.state == "down"), None)

    def _font_label(self):
        self.font_lbl.text = f"Code font size: {int(self.font_sl.value)}"

    def _rate_label(self):
        self.rate_lbl.text = f"Speaking speed: {self.rate_sl.value:.2f}\u00d7"

    def _vol_label(self):
        self.vol_lbl.text = f"Music volume: {int(self.vol_sl.value)}%"

    # ------------------------------------------------------------------ load / save
    def open(self):
        self._load()
        self.app.go("settings", "left")
        if not self.voices and not self._loading:
            self._load_voices()

    def close(self, *_):
        self._save_now()
        self.app.refresh_options()
        self.app.go("home", "right")

    def _load(self):
        S = settings.load()
        self._building = True
        self.theme_sp.text = S.get("theme", "dark-plus") if S.get("theme", "dark-plus") in THEMES else "dark-plus"
        lay = S.get("layout", "vertical")
        for name, key in LAYOUTS.items():
            self.layout_btns[name].state = "down" if key == lay else "normal"
        cur = S.get("cursor", "bar")
        self.cursor_btns["Bar"].state = "down" if cur != "block" else "normal"
        self.cursor_btns["Block"].state = "down" if cur == "block" else "normal"
        self.font_sl.value = S.get("font_size", 34)
        self.handle_in.text = S.get("handle", "")
        self.rate_sl.value = S.get("speech_rate", 1.0)
        self.vol_sl.value = int(round(S.get("music_volume", 0.15) * 100))
        self._font_label()
        self._rate_label()
        self._vol_label()
        mp = S.get("music_path", "")
        self.music_lbl.text = escape_markup(S.get("music_name") or Path(mp).name) if mp else "No song chosen"
        lic = S.get("music_license")
        self.lic_lbl.text = (f"Licence: {escape_markup(music_check.LICENSES[lic])}" if lic in music_check.LICENSES
                             else ("Not checked yet. Music stays off until you choose a licence." if mp else ""))
        self._building = False

    def _changed(self, key):
        """Only settings you actually touch are saved, so topics keep their own look otherwise."""
        if self._building:
            return
        self._dirty.add(key)
        Clock.unschedule(self._save_now)
        Clock.schedule_once(self._save_now, 0.6)

    def _save_now(self, *_):
        d, upd = self._dirty, {}
        if not d:
            return
        if "theme" in d:
            upd["theme"] = self.theme_sp.text
        if "layout" in d:
            upd["layout"] = LAYOUTS.get(self._chosen(self.layout_btns), "vertical")
        if "cursor" in d:
            upd["cursor"] = "block" if self._chosen(self.cursor_btns) == "Block" else "bar"
        if "font_size" in d:
            upd["font_size"] = int(self.font_sl.value)
        if "handle" in d:
            upd["handle"] = self.handle_in.text.strip() or None
        if "speech_rate" in d:
            upd["speech_rate"] = round(float(self.rate_sl.value), 2) if abs(self.rate_sl.value - 1.0) > 0.01 else None
        if "music_volume" in d:
            upd["music_volume"] = round(self.vol_sl.value / 100.0, 2)
        if "voice" in d and self.voices:
            upd["voice_name"], upd["voice_locale"] = self._voice_name(), self._lang_tag()
        self._dirty = set()
        settings.update(**upd)

    # ------------------------------------------------------------------ voices
    def _load_voices(self):
        if not self.app.is_android:
            self.voice_note.text = "Voice choices are available on the phone."
            self.lang_sp.text, self.voice_sp.text = "-", "-"
            return
        self._loading = True
        self.voice_note.text = "Looking for voices on your phone…"

        def work():
            try:
                from src.android_media import list_voices
                voices = list_voices()
            except Exception as e:
                voices, err = [], str(e)
            else:
                err = ""
            Clock.schedule_once(lambda dt: self._voices_ready(voices, err), 0)
        threading.Thread(target=work, daemon=True).start()

    def _voices_ready(self, voices, err):
        self._loading = False
        self.voices = voices
        if not voices:
            self.voice_note.text = f"[color={BAD}]No voices found. {escape_markup(err)}[/color]"
            return
        self.voice_note.text = f"{len(voices)} voices installed"
        langs = sorted({v["lang"] for v in voices})
        S = settings.load()
        saved = next((v for v in voices if v["name"] == S.get("voice_name")), None)
        pick = (saved or next((v for v in voices if v["tag"].startswith(("fil", "tl"))), None) or voices[0])
        self._building = True
        self.lang_sp.values = langs
        self.lang_sp.text = pick["lang"]
        self._fill_voices(pick["lang"], saved["name"] if saved else None)
        self._building = False

    def _fill_voices(self, lang, select=None):
        items = [v for v in self.voices if v["lang"] == lang]
        names = [AUTO_VOICE] + [self._label(v) for v in items]
        self.voice_sp.values = names
        chosen = next((self._label(v) for v in items if v["name"] == select), AUTO_VOICE)
        self.voice_sp.text = chosen

    @staticmethod
    def _label(v):
        return f"{v['name']}{'  (online)' if v['network'] else ''}"

    def _on_lang(self, spinner, text):
        if self._building or not self.voices:
            return
        self._building = True
        self._fill_voices(text)
        self._building = False
        self._changed("voice")

    def _voice_name(self):
        text = self.voice_sp.text
        for v in self.voices:
            if self._label(v) == text:
                return v["name"]
        return None

    def _lang_tag(self):
        v = next((v for v in self.voices if v["lang"] == self.lang_sp.text), None)
        return v["tag"] if v and self._voice_name() else None

    def test_voice(self, *_):
        if not self.app.is_android:
            return
        self._save_now()
        S = settings.load()
        voice = {"voice_name": S.get("voice_name"), "locale": S.get("voice_locale"),
                 "speech_rate": S.get("speech_rate")}
        try:
            from src.android_media import speak_sample
            speak_sample("Kumusta! Ito ang boses para sa iyong video.", voice)
        except Exception as e:
            self.voice_note.text = f"[color={BAD}]Couldn't play: {escape_markup(str(e))}[/color]"

    # ------------------------------------------------------------------ music
    def pick_music(self, *_):
        self.app.pick_files(self._music_picked, "audio/*", False,
                            settings.data_dir() / "music", "music")

    def _music_picked(self, paths, names):
        if not paths:
            return
        settings.update(music_path=str(paths[0]), music_name=(names[0] if names else Path(paths[0]).name),
                        music_enabled=None, music_license=None, music_credit=None)
        self._load()
        self.check.open(paths[0], names[0] if names else Path(paths[0]).name)

    def recheck_music(self, *_):
        S = settings.load()
        mp = S.get("music_path")
        if not mp or not Path(mp).is_file():
            return
        self.check.open(mp, S.get("music_name") or Path(mp).name)

    def clear_music(self, *_):
        S = settings.load()
        mp = S.get("music_path")
        settings.update(music_path=None, music_name=None, music_enabled=None,
                        music_license=None, music_credit=None)
        try:
            if mp and Path(mp).parent == settings.data_dir() / "music":
                Path(mp).unlink(missing_ok=True)
        except Exception:
            pass
        self._load()


class MusicCheck:
    """Shown after you pick a song: what the file says, optional online check, licence."""

    def __init__(self, app, owner):
        self.app, self.owner = app, owner
        self.path, self.name, self.risk, self.credit_hint = None, "", "unknown", ""
        self.scr = self._build()

    def _build(self):
        scr = Screen(name="musiccheck")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        bar = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cancel = Button(text="Remove", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(cancel)
        cancel.bind(on_release=self.cancel)
        bar.add_widget(cancel)
        bar.add_widget(lbl("Check this song", 16, TEXT, bold=True, halign="center"))
        self.use_btn = Button(text="Use", size_hint_x=None, width=dp(90), font_size=sp(15), bold=True)
        style_button(self.use_btn, ACCENT, ACCENT_DN, fg=(1, 1, 1, 1))
        self.use_btn.bind(on_release=self.use)
        bar.add_widget(self.use_btn)
        root.add_widget(bar)

        sv, box = scroll_column(spacing=10, padding=(0, 0, 0, dp(60)))
        root.add_widget(sv)
        scr.add_widget(root)

        info = self.owner._card(box, "WHAT THE FILE SAYS")
        self.info_card = info
        self.file_lbl = lbl("", 14, TEXT, bold=True, height=24)
        info.add_widget(self.file_lbl)
        self.tags_lbl = lbl("", 13, MUTED, height=100)
        info.add_widget(self.tags_lbl)
        self.verdict = lbl("", 14, TEXT, height=96)
        info.add_widget(self.verdict)
        self.owner._fit(info)

        online = self.owner._card(box, "ONLINE CHECK  (optional)")
        online.add_widget(lbl("Matches a short clip against a database of released songs (AudD). "
                              "Needs internet and a free token from audd.io.", 12, MUTED, height=52))
        frame, self.token_in = framed_input(settings.load().get("audd_token", ""), hint="AudD API token")
        online.add_widget(frame)
        self.check_btn = Button(text="Check online", size_hint_y=None, height=dp(46), font_size=sp(15))
        style_button(self.check_btn, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
        self.check_btn.bind(on_release=self.run_online)
        online.add_widget(self.check_btn)
        self.online_lbl = lbl("", 13, MUTED, height=76)
        online.add_widget(self.online_lbl)
        online.add_widget(lbl("No match does not mean the song is free. Platforms run their own checks.",
                              11, MUTED, height=30))
        self.owner._fit(online)

        lic = self.owner._card(box, "YOUR LICENCE  (required)")
        lic.add_widget(lbl("Why can you use this song in your videos?", 13, TEXT, height=24))
        self.lic_sp = _spinner(list(music_check.LICENSES.values()), "Choose…")
        self.lic_sp.bind(text=self._lic_changed)
        lic.add_widget(self.lic_sp)
        self.credit_frame, self.credit_in = framed_input("", hint="Credit line, e.g. Music: Title by Artist")
        lic.add_widget(self.credit_frame)
        lic.add_widget(lbl(f"Free sources: {music_check.FREE_SOURCES}.", 11, MUTED, height=34))
        self.lic_note = lbl("", 12, MUTED, height=44)
        lic.add_widget(self.lic_note)
        self.owner._fit(lic)
        return scr

    # ---------------------------------------------------------------- flow
    def open(self, path, name):
        self.path, self.name = Path(path), name
        S = settings.load()
        tags = music_check.read_tags(self.path)
        res = music_check.assess(tags, name)
        self.risk, self.credit_hint = res["risk"], res["credit"]
        self.file_lbl.text = escape_markup(name)
        order = ("title", "artist", "album", "year", "copyright", "publisher", "isrc")
        shown = [f"{k.capitalize()}: {tags[k]}" for k in order if tags.get(k)]
        self.tags_lbl.text = escape_markup("\n".join(shown)) if shown else "No tags found in the file."
        color, head = {
            "likely": (BAD, "Looks like a commercial song, so it is probably copyrighted."),
            "possible": ("FFB86C", "May be a commercial song. Be careful."),
            "free_hint": (GOOD, "The tags mention a free or Creative Commons licence. Read the licence."),
            "unknown": (MUTED_HEX, "Can't tell from the tags."),
        }[self.risk]
        why = "\n".join("\u2022 " + r for r in res["reasons"])
        self.verdict.text = f"[b][color={color}]{head}[/color][/b]\n{escape_markup(why)}"
        # grow the labels to fit their text, then re-measure the card
        est = lambda t, n=38: sum(len(x) // n + 1 for x in t.split("\n"))
        self.tags_lbl.height = dp(20) * max(1, est("\n".join(shown) or "x")) + dp(6)
        self.verdict.height = dp(20) * (est(head, 34) + est(why)) + dp(10)
        self.owner._fit(self.info_card)
        self.token_in.text = S.get("audd_token", "")
        self.online_lbl.text = ""
        self.lic_sp.text = music_check.LICENSES.get(S.get("music_license"), "Choose…")
        self.credit_in.text = S.get("music_credit") or (self.credit_hint if self.risk == "free_hint" else "")
        self._lic_changed()
        self.app.go("musiccheck", "left")

    def _key(self):
        return next((k for k, v in music_check.LICENSES.items() if v == self.lic_sp.text), None)

    def _lic_changed(self, *_):
        key = self._key()
        self.credit_frame.opacity = 1 if key == "cc" else 0
        self.credit_frame.height = dp(54) if key == "cc" else 0
        if key == "cc" and not self.credit_in.text.strip():
            self.credit_in.text = self.credit_hint
        self.lic_note.text = {
            "own": "Great. Keep proof that it's yours (project files, original recording).",
            "licensed": "Keep the licence or receipt. Some licences limit monetising.",
            "cc": "Read the licence. Most need the credit line below in your description.",
            "copyrighted": "[color=FF6B6B]Platforms may mute, block or claim the video. Not recommended.[/color]",
            "unsure": "If you're not sure, don't use it. Pick a song from a free source above.",
        }.get(key, "")
        self.use_btn.disabled = key not in settings.LICENSE_KEYS

    def run_online(self, *_):
        token = self.token_in.text.strip()
        if not token:
            self.online_lbl.text = f"[color={BAD}]Paste your AudD token first.[/color]"
            return
        settings.update(audd_token=token)
        self.check_btn.disabled = True
        self.online_lbl.text = "Checking… this can take up to a minute."

        def work():
            try:
                res = music_check.online_check(self.path, token, settings.data_dir())
                if res:
                    msg = (f"[b][color={BAD}]Match found:[/color][/b] {escape_markup(res['title'])} \u2014 "
                           f"{escape_markup(res['artist'])}\n{escape_markup(res['album'])} "
                           f"{escape_markup(res['label'])}\nThis is a released song.")
                    self.risk = "likely"
                else:
                    msg = "No match found. This does not prove it is safe."
            except BaseException as e:
                msg = f"[color={BAD}]Couldn't check: {escape_markup(str(e))}[/color]"
            Clock.schedule_once(lambda dt: self._online_done(msg), 0)
        threading.Thread(target=work, daemon=True).start()

    def _online_done(self, msg):
        self.check_btn.disabled = False
        self.online_lbl.text = msg

    def use(self, *_):
        key = self._key()
        if key not in settings.LICENSE_KEYS:
            return
        credit = self.credit_in.text.strip()
        if key == "cc" and not credit:
            self.lic_note.text = f"[color={BAD}]Add the credit line first.[/color]"
            return
        if self.risk in ("likely", "possible") and key in ("own", "licensed"):
            confirm("Double-check", "This file looks like a released song. Only continue if you really "
                    "own it or hold a licence that covers videos.", "I have the rights",
                    lambda: self._save(key, credit), danger=False)
        else:
            self._save(key, credit)

    def _save(self, key, credit):
        settings.update(music_license=key, music_credit=(credit if key == "cc" else None) or None,
                        music_enabled=True, music_risk=self.risk)
        self.owner._load()
        self.app.refresh_options()
        self.app.go("settings", "right")

    def cancel(self, *_):
        self.owner.clear_music()
        self.app.refresh_options()
        self.app.go("settings", "right")
