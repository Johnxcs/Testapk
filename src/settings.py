"""User settings (settings.json in the persistent data folder) -> render overrides."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOLUTIONS = {"vertical": [1080, 1920], "horizontal": [1920, 1080]}
_data = None


def set_data_dir(p):
    global _data
    _data = Path(p)
    _data.mkdir(parents=True, exist_ok=True)


def data_dir() -> Path:
    return _data or ROOT


def _file() -> Path:
    return data_dir() / "settings.json"


def load() -> dict:
    try:
        d = json.loads(_file().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d):
    _file().write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def update(**kw) -> dict:
    d = load()
    for k, v in kw.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    save(d)
    return d


def render_overrides(S=None) -> dict:
    """Only what the user actually set; topics keep their own values otherwise."""
    S = load() if S is None else S
    o = {}
    if S.get("theme"):
        o["theme"] = S["theme"]
    lay = S.get("layout")
    if lay in RESOLUTIONS:
        o["resolution"] = RESOLUTIONS[lay]
        o["layout"] = "shorts" if lay == "vertical" else "editor"
    if S.get("font_size"):
        o["font_size"] = int(S["font_size"])
    if S.get("handle"):
        o["handle"] = S["handle"]
    if S.get("cursor"):
        o["cursor"] = S["cursor"]
    voice = {k: v for k, v in (("locale", S.get("voice_locale")), ("voice_name", S.get("voice_name")),
                               ("speech_rate", S.get("speech_rate"))) if v}
    if voice:
        o["voice"] = voice
    o["captions"] = bool(S.get("captions"))
    mp = S.get("music_path")
    if S.get("music_enabled") and mp and Path(mp).is_file():
        o["music"] = {"path": mp, "volume": float(S.get("music_volume", 0.15))}
    return o
