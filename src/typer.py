"""Typewriter timing model: converts narration durations into per-scene frame counts."""
from dataclasses import dataclass, field

from .card_renderer import CARD_KINDS, count_units


@dataclass
class SceneTiming:
    kind: str = "code"           # code | title | wait | run
    narration: str = ""
    code: str = ""
    code_mode: str = "replace"   # replace = clear editor first, append = continue
    code_before: str = ""        # buffer already on screen when this scene starts
    term_text: str = ""          # terminal lines typed by a 'run' scene
    term_before: str = ""        # terminal scrollback already present
    title: str = ""
    subtitle: str = ""
    chars: int = 0
    delay_frames: int = 0
    typing_frames: int = 0
    frames: int = 0
    start_frame: int = 0
    card: dict = None            # scene dict for text/bullets/steps/quote/compare/stat/image


def build_timings(scenes, durations, fps, cfg):
    fps = int(fps)
    speed = float(cfg.get("typing_speed", 1.0)) or 1.0
    coverage = float(cfg.get("narration_coverage", 0.85))
    delay = int(float(cfg.get("typing_delay", 0.35)) * fps)
    pause = int(float(cfg.get("pause_after_scene", 0.6)) * fps)
    base_cps = float(cfg.get("base_typing_cps", 9.0))
    wait_default = float(cfg.get("wait_duration", 3.0))

    out = []
    start = 0
    base = ""
    term = ""
    for sc, dur in zip(scenes, durations):
        kind = sc.get("kind", "code")
        t = SceneTiming(kind=kind, narration=sc.get("narration", ""), delay_frames=delay)
        t.start_frame = start

        if kind == "title":
            t.title = sc.get("title", "")
            t.subtitle = sc.get("subtitle", "")
            t.chars = len(t.title) + len(t.subtitle)
        elif kind == "run":
            t.code_before = base
            t.term_text = sc.get("terminal", "")
            t.term_before = term
            t.chars = len(t.term_text)
        elif kind == "code":
            t.code = sc.get("code", "")
            t.code_mode = sc.get("code_mode", "append")
            t.code_before = base
            t.chars = len(t.code)
        elif kind in CARD_KINDS:
            t.card = sc
            t.chars = count_units(sc)
        else:  # wait
            t.code_before = base
            t.term_before = term
            t.frames = int(round((dur if dur > 0.05 else wait_default) * fps))
            out.append(t)
            start += t.frames
            continue

        avail = int(round(dur * fps)) if dur > 0.05 else 0
        if avail > 0:
            t.typing_frames = max(1, int(avail * coverage) - delay)
            t.frames = avail + pause
        else:
            t.typing_frames = max(1, int(t.chars / (base_cps * speed) * fps))
            t.frames = delay + t.typing_frames + pause

        if kind == "code":
            base = base + t.code if t.code_mode != "replace" else t.code
        elif kind == "run":
            term = term + t.term_text
        out.append(t)
        start += t.frames
    return out


def visible_index(frame, t: SceneTiming):
    """How many characters of the current scene's text are typed at `frame`."""
    if t.chars <= 0:
        return 0
    if frame < t.delay_frames:
        return 0
    t_i = frame - t.delay_frames
    if t.typing_frames <= 0 or t_i >= t.typing_frames:
        return t.chars
    return min(t.chars, int(t.chars * t_i / t.typing_frames))


def buffer_at(t: SceneTiming, k):
    if t.kind == "code":
        typed = t.code[:k]
        return (t.code_before + typed) if t.code_mode != "replace" else typed
    return t.code_before


def terminal_at(t: SceneTiming, k):
    """Terminal text at character index k (relative to this scene): the
    command line is typed, output lines appear instantly once done."""
    text = t.term_text
    lines = text.split("\n")
    cmd = lines[0]
    rest = text[len(cmd):]
    if not cmd.startswith("$") or k <= len(cmd):
        return t.term_before + text[:k]
    return t.term_before + cmd + rest
