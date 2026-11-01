"""Scene length estimates (before any voice is rendered), using the real timing model."""
from . import typer
from .narration import estimate_duration


def scene_durations(scenes, cfg, fps=30):
    """Estimated seconds for each scene (same rules the renderer uses)."""
    durs = []
    for sc in scenes:
        text = str(sc.get("narration", "") or "")
        durs.append(estimate_duration(text) if text.strip() else 0.0)
    timings = typer.build_timings(scenes, durs, fps, cfg)
    return [t.frames / fps for t in timings]


def fmt(seconds):
    """12.4 -> '0:12', 75 -> '1:15'."""
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"
