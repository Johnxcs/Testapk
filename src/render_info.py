"""Remember the real per-scene lengths of the last render, so the editor can show them."""
import hashlib
import json

from . import settings


def scene_sig(sc) -> str:
    return hashlib.md5(json.dumps(sc, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def _path(tid):
    return settings.data_dir() / "render_info" / f"{tid}.json"


def save(tid, sigs, seconds):
    p = _path(tid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"scenes": {s: round(float(x), 2) for s, x in zip(sigs, seconds)}}), encoding="utf-8")


def load(tid) -> dict:
    """signature -> seconds (empty if the topic was never rendered)."""
    try:
        return json.loads(_path(tid).read_text(encoding="utf-8")).get("scenes", {})
    except Exception:
        return {}
