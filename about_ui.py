"""About tab. Its text comes from content.json (only the app owner edits that file)."""
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

    def _section(self, title, lines, raw=False):
        lines = [l for l in lines if l and str(l).strip()]
        if not lines:
            return
        card = auto_card()
        card.add_widget(auto_label(f"[b]{title}[/b]", 11, ACCENT))
        for l in lines:
            card.add_widget(auto_label(l if raw else _esc(l), 15, TEXT))
        self.box.add_widget(card)
