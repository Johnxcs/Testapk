"""About tab + the editor that changes the text of the Home and About tabs."""
from pathlib import Path

from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image as KImage
from kivy.uix.screenmanager import Screen
from kivy.utils import escape_markup

from src import content
from ui_kit import (ACCENT, ACCENT_DN, BAD, CARD, CARD2, CARD2_ON, GOOD, MUTED, ROOT, TEXT,
                    auto_card, auto_label, confirm, framed_input, lbl, nav_holder, scroll_column,
                    style_button, style_card)

ICON = ROOT / "icon.png"


def _esc(v):
    return escape_markup(str(v))


class AboutScreen:
    def __init__(self, app):
        self.app = app
        self.scr = self._build()

    def screens(self):
        return [self.scr]

    def _build(self):
        scr = Screen(name="about")
        outer = BoxLayout(orientation="vertical")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        bar = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(52))
        bar.add_widget(lbl("[b]About[/b]", 24, TEXT, height=52))
        edit = Button(text="Edit text", size_hint_x=None, width=dp(110), font_size=sp(14), bold=True)
        style_button(edit, CARD2, CARD2_ON, radius=14, border=(1, 1, 1, 0.10))
        edit.bind(on_release=lambda *_: self.app.content_ui.open())
        bar.add_widget(edit)
        root.add_widget(bar)
        sv, self.box = scroll_column(spacing=12, padding=(0, 0, 0, dp(20)))
        root.add_widget(sv)
        outer.add_widget(root)
        outer.add_widget(nav_holder(self.app, "about"))
        scr.add_widget(outer)
        self.refresh()
        return scr

    # ---------------------------------------------------------------- content
    def refresh(self):
        A = content.get("about") or {}
        box = self.box
        box.clear_widgets()

        head = auto_card(padding=18, spacing=8)
        if ICON.is_file():
            img = KImage(source=str(ICON), size_hint=(None, None), size=(dp(88), dp(88)),
                         pos_hint={"center_x": 0.5}, allow_stretch=True)
            holder = BoxLayout(size_hint_y=None, height=dp(92))
            holder.add_widget(BoxLayout())
            holder.add_widget(img)
            holder.add_widget(BoxLayout())
            head.add_widget(holder)
        head.add_widget(auto_label(f"[b]{_esc(A.get('app_name', ''))}[/b]", 26, TEXT, halign="center"))
        if A.get("version"):
            head.add_widget(auto_label(f"Version {_esc(A['version'])}", 13, MUTED, halign="center"))
        if A.get("tagline"):
            head.add_widget(auto_label(_esc(A["tagline"]), 15, ACCENT, halign="center"))
        box.add_widget(head)

        self._section("ABOUT", [A.get("description")])
        self._section("FEATURES", [f"\u2022  {_esc(x)}" for x in A.get("features", []) if str(x).strip()], raw=True)
        self._section("HOW IT WORKS", [f"{i}.  {_esc(x)}" for i, x in enumerate(
            [x for x in A.get("how_to", []) if str(x).strip()], 1)], raw=True)

        # contact & links
        links = content.parse_links(A.get("links"))
        if A.get("website"):
            links.insert(0, ("Website", A["website"] if "://" in A["website"] else "https://" + A["website"]))
        if A.get("email"):
            links.insert(0, (f"Email  {A['email']}", "mailto:" + A["email"]))
        if A.get("author") or links:
            card = auto_card()
            card.add_widget(auto_label("[b]CONTACT[/b]", 11, ACCENT))
            if A.get("author"):
                card.add_widget(auto_label(f"By {_esc(A['author'])}", 15, TEXT))
            for label, url in links:
                b = Button(text=_esc(label), markup=True, size_hint_y=None, height=dp(46), font_size=sp(15))
                style_button(b, CARD2, CARD2_ON, radius=12, border=(1, 1, 1, 0.10))
                b.bind(on_release=lambda *_, u=url: self.app.open_url(u))
                card.add_widget(b)
            box.add_widget(card)

        self._section("PRIVACY", [A.get("privacy")])
        self._section("CREDITS", [A.get("credits")])
        if A.get("footer"):
            box.add_widget(auto_label(_esc(A["footer"]), 13, MUTED, halign="center"))
        box.add_widget(auto_label("To change any text on this page or on Home, tap Edit text.",
                                  11, MUTED, halign="center"))

    def _section(self, title, lines, raw=False):
        lines = [l for l in lines if l and str(l).strip()]
        if not lines:
            return
        card = auto_card()
        card.add_widget(auto_label(f"[b]{title}[/b]", 11, ACCENT))
        for l in lines:
            card.add_widget(auto_label(l if raw else _esc(l), 15, TEXT))
        self.box.add_widget(card)


HOME_FIELDS = [
    ("home.title", "App title (big, at the top of Home)", "line"),
    ("home.tagline", "Tagline under the title", "line"),
    ("home.tip", "Tip card on Home (leave empty to hide it)", "multi"),
    ("home.topics_label", "Heading above your videos", "line"),
    ("home.empty_title", "Title when there are no videos", "line"),
    ("home.empty_text", "Text when there are no videos", "multi"),
    ("home.empty_button", "Button when there are no videos", "line"),
    ("home.render_button", "Render button text", "line"),
    ("tabs.home", "Tab name 1", "line"),
    ("tabs.editor", "Tab name 2", "line"),
    ("tabs.about", "Tab name 3", "line"),
]
ABOUT_FIELDS = [
    ("about.app_name", "App name", "line"),
    ("about.version", "Version", "line"),
    ("about.tagline", "Tagline", "line"),
    ("about.description", "Description", "multi"),
    ("about.features", "Features (one per line)", "lines"),
    ("about.how_to", "How it works (one step per line)", "lines"),
    ("about.author", "Your name", "line"),
    ("about.email", "Contact email", "line"),
    ("about.website", "Website", "line"),
    ("about.links", "More links (one per line:  Label | https://...)", "lines"),
    ("about.privacy", "Privacy note", "multi"),
    ("about.credits", "Credits and licences", "multi"),
    ("about.footer", "Footer line", "line"),
]


class ContentEditor:
    """Form for every text on Home and About. Saved in the phone's data folder."""

    def __init__(self, app):
        self.app = app
        self.inputs = {}
        self.scr = self._build()

    def screens(self):
        return [self.scr]

    def _build(self):
        scr = Screen(name="content")
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        bar = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cancel = Button(text="Cancel", size_hint_x=None, width=dp(90), font_size=sp(15))
        style_button(cancel)
        cancel.bind(on_release=lambda *_: self.app.go("about", "right"))
        bar.add_widget(cancel)
        bar.add_widget(lbl("Edit Home & About", 16, TEXT, bold=True, halign="center"))
        save = Button(text="Save", size_hint_x=None, width=dp(90), font_size=sp(15), bold=True)
        style_button(save, ACCENT, ACCENT_DN, fg=(1, 1, 1, 1))
        save.bind(on_release=self.save)
        bar.add_widget(save)
        root.add_widget(bar)
        sv, self.box = scroll_column(spacing=6, padding=(0, 0, 0, dp(90)))
        root.add_widget(sv)
        scr.add_widget(root)
        return scr

    def open(self):
        C = content.load()
        box = self.box
        box.clear_widgets()
        self.inputs = {}
        box.add_widget(auto_label("Change any text, then press Save. Changes stay on your phone and "
                                  "survive app updates. Empty boxes hide that part of the page.",
                                  12, MUTED))
        for title, fields in (("HOME TAB", HOME_FIELDS), ("ABOUT TAB", ABOUT_FIELDS)):
            box.add_widget(lbl(f"[b]{title}[/b]", 13, ACCENT, height=34))
            for key, label, typ in fields:
                box.add_widget(lbl(f"[b]{label.upper()}[/b]", 10, MUTED, height=22))
                value = content.get_in(C, key, "")
                if typ == "line":
                    frame, ti = framed_input(str(value))
                elif typ == "multi":
                    frame, ti = framed_input(str(value), multiline=True, height=120)
                else:
                    text = "\n".join(str(v) for v in value) if isinstance(value, list) else str(value)
                    frame, ti = framed_input(text, multiline=True, height=150)
                box.add_widget(frame)
                self.inputs[key] = (typ, ti)
        reset = Button(text="Reset all text to the defaults", size_hint_y=None, height=dp(48), font_size=sp(14))
        style_button(reset, rgb_red(), rgb_red(0.7), radius=12, fg=(1, 1, 1, 1))
        reset.bind(on_release=lambda *_: confirm(
            "Reset text?", "Home and About go back to the text that came with the app.",
            "Reset", self._reset))
        box.add_widget(reset)
        self.app.go("content", "left")

    def save(self, *_):
        values = {}
        for key, (typ, ti) in self.inputs.items():
            values[key] = ([l.strip() for l in ti.text.split("\n") if l.strip()]
                           if typ == "lines" else ti.text.strip())
        content.save_changes(values)
        self.app.apply_content()
        self.app.go("about", "right")

    def _reset(self):
        content.reset()
        self.app.apply_content()
        self.app.go("about", "right")


def rgb_red(k=1.0):
    return (0.9 * k, 0.28 * k, 0.30 * k, 1)
