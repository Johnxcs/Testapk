"""Global configuration: config.json merged over built-in defaults."""
import copy
import json
from pathlib import Path

DEFAULTS = {
    "output_dir": "output",
    "fps": 30,
    "resolution": [1080, 1920],   # vertical YouTube Shorts format
    "layout": "shorts",           # shorts = vertical; editor = classic 16:9
    "font": "",
    "font_size": 34,
    "cursor": "bar",
    "theme": "dark-plus",
    "handle": "",                 # e.g. "@yourhandle" shown top-left
    "voice": {"engine": "auto", "name": "fil-PH-AngeloNeural", "lang": "tl", "rate": ""},
    "typing_speed": 1.0,
    "base_typing_cps": 9.0,
    "typing_delay": 0.35,
    "narration_coverage": 0.85,
    "pause_after_scene": 0.6,
    "wait_duration": 3.0,
    "crf": 20,
}


def load_config(path=None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    p = Path(path or "config.json")
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"config.json is not valid JSON: {e}")
        if isinstance(data, dict):
            for k, v in data.items():
                if k.startswith("_"):
                    continue
                if k == "voice" and isinstance(v, dict):
                    cfg["voice"].update(v)
                else:
                    cfg[k] = v
    return cfg
