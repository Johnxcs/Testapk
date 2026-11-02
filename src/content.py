"""Text shown on the Home and About tabs.

Three layers, later ones win:  built-in defaults  <  content.json (shipped with the app)
<  content_user.json in the app data folder (what you save from the in-app editor).
"""
import copy
import json
from pathlib import Path

from . import settings

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


def user_file() -> Path:
    return settings.data_dir() / "content_user.json"


def defaults() -> dict:
    return _merge(BUILTIN, _read(ROOT / "content.json"))


def load() -> dict:
    return _merge(defaults(), _read(user_file()))


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


def set_in(d, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def save_changes(values: dict):
    """values: {'home.title': 'x', ...}. Only differences from the shipped defaults are stored."""
    base, user = defaults(), {}
    for path, v in values.items():
        if v != get_in(base, path, None):
            set_in(user, path, v)
    f = user_file()
    if user:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(user, indent=2, ensure_ascii=False), encoding="utf-8")
    elif f.exists():
        f.unlink()


def reset():
    try:
        user_file().unlink(missing_ok=True)
    except Exception:
        pass


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
