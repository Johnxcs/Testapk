"""Text shown on the Home and About tabs.

Two layers, the later one wins:  built-in defaults  <  content.json (shipped inside the app).
Only the app owner changes the text, by editing content.json before building the APK.
Users of the app cannot change it.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BUILTIN = {
    "tabs": {"home": "Home", "editor": "Editor", "about": "About"},
    "home": {"title": "Code Reels", "tagline": "", "tip": "", "topics_label": "YOUR VIDEOS",
             "empty_title": "Make your first video", "empty_text": "Tap New to start.",
             "empty_button": "+  New video", "render_button": "Render video"},
    "about": {"app_name": "Code Reels", "version": "1.0", "tagline": "", "description": "",
              "features": [], "how_to": [], "author": "", "email": "", "website": "", "links": [],
              "privacy": "", "credits": "", "footer": ""},
}


def _merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _read(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def defaults() -> dict:
    return _merge(BUILTIN, _read(ROOT / "content.json"))


def load() -> dict:
    return defaults()


def get(path, default=""):
    d = load()
    for part in path.split("."):
        if not isinstance(d, dict) or part not in d:
            return default
        d = d[part]
    return d


def get_in(d, path, default=""):
    for part in path.split("."):
        if not isinstance(d, dict) or part not in d:
            return default
        d = d[part]
    return d


def parse_links(lines):
    """['GitHub | https://...', 'https://x.com'] -> [(label, url)]"""
    out = []
    for line in lines or []:
        line = str(line).strip()
        if not line:
            continue
        if "|" in line:
            label, url = (p.strip() for p in line.split("|", 1))
        else:
            label, url = line, line
        if url and "://" not in url and not url.startswith("mailto:"):
            url = "https://" + url
        out.append((label or url, url))
    return out
