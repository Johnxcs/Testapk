"""Main pipeline: narration -> timings -> typewriter frames -> ffmpeg mp4."""
import copy
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from . import media, music as music_mod, narration, render_info, settings, topics, typer
from .captions import CaptionOverlay
from .card_renderer import CARD_KINDS, CardRenderer
from .editor_renderer import EditorRenderer
from .shorts import ShortsComposer
from .theme import get_theme
from .title_renderer import TitleRenderer


def _mmss(frames, fps):
    s = int(frames / fps)
    return f"{s // 60}:{s % 60:02d}"


def _apply_overrides(topic, overrides):
    """Settings chosen in the app win over what a topic file says."""
    for k in ("theme", "layout", "resolution", "font_size", "handle", "cursor"):
        if overrides.get(k) is not None:
            topic[k] = overrides[k]
    if overrides.get("voice"):
        topic["voice"] = {**topic.get("voice", {}), **overrides["voice"]}


def _prepare_scenes(topic):
    """Default run command for 'run' scenes that have no terminal text."""
    filename = topic.get("filename", "main.py")
    runners = {"py": "python", "js": "node", "rb": "ruby", "sh": "bash",
               "ts": "npx tsx", "go": "go run"}
    runner = runners.get(filename.rsplit(".", 1)[-1], "run")
    for sc in topic["scenes"]:
        if sc.get("kind") == "run" and not sc.get("terminal"):
            sc["terminal"] = f"$ {runner} {filename}"


def _setup(topic, topic_id, path, cfg, overrides, durations):
    """Build timings + renderers; returns an object with .frame_for(scene, frame)."""
    fps = int(overrides.get("fps") or topic.get("fps") or cfg["fps"])
    w, h = topic.get("resolution", cfg["resolution"])
    layout = str(topic.get("layout", cfg.get("layout", "shorts"))).lower()
    shorts = layout == "shorts" or h > w
    theme = get_theme(topic.get("theme", cfg["theme"]))
    scenes = topic["scenes"]
    timings = typer.build_timings(scenes, durations, fps, cfg)
    total_frames = sum(t.frames for t in timings)

    fs = topic.get("font_size", cfg["font_size"])
    render_cfg = {**cfg, "font_size": fs,
                  "handle": topic.get("handle", cfg.get("handle", "")),
                  "cursor": topic.get("cursor", cfg.get("cursor", "bar"))}
    card_size = (0, 0, w, h) if shorts else None
    editor = EditorRenderer(w, h, fps, _font(topic, cfg), theme, render_cfg,
                            filename=topic.get("filename", "main.py"),
                            language_label=str(topic.get("language", "python")).capitalize(),
                            window_title=topic.get("title", ""))
    title_renderers = {}
    for i, sc in enumerate(scenes):
        if sc.get("kind") == "title":
            title_renderers[i] = TitleRenderer(
                w, h, fps, _font(topic, cfg), theme, render_cfg,
                title=sc.get("title", ""),
                footer=topic.get("title", "") if sc.get("subtitle") else "")
    cards = None
    if any(sc.get("kind") in CARD_KINDS for sc in scenes):
        from .fonts import PROJECT_ROOT
        cards = CardRenderer(w, h, fps, _font(topic, cfg), theme, render_cfg,
                             footer=topic.get("title", ""), captions=bool(overrides.get("captions")),
                             base_dirs=[PROJECT_ROOT, topics.TOPICS_DIR, Path(path).parent,
                                        settings.data_dir(),
                                        Path("/storage/emulated/0/CodeReels"),
                                        Path(overrides.get("out") or cfg["output_dir"])])
    composer = (ShortsComposer(w, h, fps, _font(topic, cfg), theme, render_cfg, timings,
                               card_size=card_size) if shorts else None)
    captions = None
    if overrides.get("captions"):
        captions = CaptionOverlay(w, h, theme, [sc.get("narration", "") for sc in scenes],
                                  [d * fps for d in durations], _font(topic, cfg))

    def frame_for(t_i, f):
        """Full composed frame for scene t_i at local frame f."""
        t = timings[t_i]
        blink_half = max(1, int(fps * 0.55))
        blink = (f // blink_half) % 2 == 0
        typing_window = t.delay_frames <= f < t.delay_frames + t.typing_frames
        if t.kind == "title":
            r = title_renderers[t_i]
            k = typer.visible_index(f, t)
            k_title = min(len(t.title), k)
            k_sub = k - k_title
            cursor = True if typing_window else blink
            img = r.render_full(t.title, k_title, k_sub, t.subtitle, cursor)
        elif t.kind in CARD_KINDS:
            img = cards.render(t_i, t.card, typer.visible_index(f, t))
        else:
            k = typer.visible_index(f, t)
            buf = typer.buffer_at(t, k)
            typing = (t.kind in ("code", "run") and typing_window and k < t.chars)
            term_text = typer.terminal_at(t, k) if t.kind == "run" else t.term_before
            term_typing = t.kind == "run" and typing_window and k < t.chars
            img = editor.render_code_frame(buf, typing or blink, terminal_text=term_text,
                                           term_cursor_on=term_typing or blink)
        if composer:
            img = composer.compose(img, t_i, f)
        if captions:
            img = captions.apply(img, t_i, f)
        return img

    return SimpleNamespace(timings=timings, frame_for=frame_for, total_frames=total_frames,
                           fps=fps, w=w, h=h, scenes=scenes)


def preview_scene(topic, idx, cfg, overrides=None, topic_id="preview", base_path="topic.json"):
    """One still frame of scene `idx` (as it looks once typed) — no voice, no video."""
    overrides = dict(overrides or {})
    topic = copy.deepcopy(topic)
    _apply_overrides(topic, overrides)
    _prepare_scenes(topic)
    durs = [narration.estimate_duration(sc.get("narration", ""))
            if str(sc.get("narration", "")).strip() else 0.0 for sc in topic["scenes"]]
    S = _setup(topic, topic_id, Path(base_path), cfg, overrides, durs)
    t = S.timings[idx]
    f = min(t.frames - 1, t.delay_frames + t.typing_frames)
    return S.frame_for(idx, f)


def render_topic(topic_id, cfg, overrides):
    path, topic = topics.load(topic_id)
    _apply_overrides(topic, overrides)
    scenes = topic["scenes"]
    sigs = [render_info.scene_sig(sc) for sc in scenes]       # before defaults are filled in
    _prepare_scenes(topic)
    fps = int(overrides.get("fps") or topic.get("fps") or cfg["fps"])
    voice_cfg = {**cfg["voice"], **topic.get("voice", {})}
    engine = narration.pick_engine(voice_cfg.get("engine", "auto"))
    no_audio = overrides.get("no_audio", False)
    if no_audio:
        engine = "mock"

    out_dir = Path(overrides.get("out") or cfg["output_dir"]) / topic_id
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Rendering '{topic.get('title', topic_id)}' ({topic_id}) ===")
    print(f"  voice engine: {engine}{' (silent mock — no audio track)' if engine == 'mock' else ''}")
    print(f"  output: {out_dir}")

    # 1. narrate every scene
    wav_paths, durations = [], []
    for i, sc in enumerate(scenes):
        wav = None
        dur = 0.0
        narration_text = sc.get("narration", "")
        if narration_text.strip():
            # mock still produces a silent wav so timings are deterministic
            wav = audio_dir / f"narration_{i:02d}.wav"
            dur = narration.synthesize(narration_text, wav, engine=engine, voice=voice_cfg)
        wav_paths.append(wav)
        durations.append(dur)

    # 2. timing model + renderers
    S = _setup(topic, topic_id, path, cfg, overrides, durations)
    timings, total_frames = S.timings, S.total_frames
    w, h = S.w, S.h
    print(f"  duration: {total_frames / fps:.1f}s, {total_frames} frames @ {fps} fps")
    try:
        render_info.save(topic_id, sigs, [t.frames / fps for t in timings])
    except Exception:
        pass

    # 3. audio track (silence when mock — keeps everything keyed to video length)
    track = audio_dir / "full_track.wav"
    narration.build_full_track(wav_paths, [t.frames for t in timings], track, fps)
    music = overrides.get("music")
    if music and engine != "mock":
        try:
            music_mod.mix_into(track, music["path"], music.get("volume", 0.15), audio_dir)
            print("  background music: mixed in")
        except Exception as e:
            print(f"  (music skipped: {e})")

    frame_for = S.frame_for
    out_mp4 = out_dir / "video.mp4"
    writer = media.open_writer(out_mp4, w, h, fps, cfg.get("crf", 20),
                               None if engine == "mock" else track,
                               topic.get("title", topic_id))
    done = 0
    try:
        for t_i, t in enumerate(timings):
            for f in range(t.frames):
                writer.write(frame_for(t_i, f))
                done += 1
                if done % 30 == 0 or done == total_frames:
                    pct = 100 * done // total_frames
                    print(f"\r  frames {done}/{total_frames} ({pct}%)", end="", flush=True)
    finally:
        writer.close()
    print()

    # 4. previews + transcript
    preview = frame_for(len(timings) - 1, max(0, timings[-1].frames - 1))
    preview.save(out_dir / "preview_final_frame.png")
    _write_transcript(out_dir, topic, scenes, timings, fps, engine)
    print(f"  done -> {out_mp4}")
    return out_mp4


def _font(topic, cfg):
    from .fonts import find_font
    return find_font(topic.get("font") or cfg.get("font", ""))


def _write_transcript(out_dir, topic, scenes, timings, fps, engine):
    lines = [topic.get("title", "Untitled"), "=" * 40, ""]
    notes = {
        "title": lambda sc: sc.get("title", "") + (" — " + sc.get("subtitle", "") if sc.get("subtitle") else ""),
        "code": lambda sc: (sc.get("code", "") or "").rstrip(),
        "run": lambda sc: (sc.get("terminal", "") or "").strip(),
        "wait": lambda sc: "(pause)",
    }
    for kk in CARD_KINDS:
        notes[kk] = lambda sc: " | ".join(str(v) for key, v in sc.items()
                                           if key in ("heading", "body", "text", "author", "value", "label", "caption")
                                           and v)
    for sc, t in zip(scenes, timings):
        kind = t.kind
        lines.append(f"[{_mmss(t.start_frame, fps)} – {_mmss(t.start_frame + t.frames, fps)}] "
                     f"({kind})")
        note = notes.get(kind, lambda s: "")(sc)
        if note:
            lines.append(note)
        if sc.get("narration"):
            lines.append(f"VO: {sc['narration']}")
        lines.append("")
    lines.append(f"voice engine: {engine}")
    (out_dir / "transcript.txt").write_text("\n".join(lines), encoding="utf-8")
