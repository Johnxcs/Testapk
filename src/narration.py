"""Voice-over synthesis (edge-tts / gTTS / pyttsx3 / silent estimate) + WAV utilities."""
import asyncio
import os
import shutil
import subprocess
import wave
from pathlib import Path

ON_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_BOOTLOGO" in os.environ
RATE = 44100
SAMPWIDTH, CHANNELS = 2, 1


class NarrationError(RuntimeError):
    pass


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def require_ffmpeg():
    exe = ffmpeg_exe()
    if not exe:
        raise NarrationError(
            "ffmpeg not found.\n"
            "  pip install imageio-ffmpeg   (bundled static ffmpeg — easiest)\n"
            "  or install ffmpeg with your OS package manager."
        )
    return exe


def pick_engine(requested):
    if ON_ANDROID and requested != "mock":
        return "android"      # the phone's own text-to-speech
    if requested and requested != "auto":
        return requested
    for name, module in (("edge", "edge_tts"), ("gtts", "gtts"), ("pyttsx3", "pyttsx3")):
        try:
            __import__(module)
            return name
        except Exception:
            continue
    return "mock"


def estimate_duration(text):
    """Rough narration length in seconds — used when no TTS engine available."""
    words = max(1, len(text.split()))
    return max(1.2, words / 2.4)


def _av_to_wav(src, dst_wav):
    """Decode any audio file to 44.1 kHz mono s16 WAV with PyAV (no ffmpeg binary)."""
    import av
    inp = av.open(str(src))
    rs = av.AudioResampler(format="s16", layout="mono", rate=RATE)

    def as_list(x):
        return [] if x is None else (x if isinstance(x, list) else [x])

    with wave.open(str(dst_wav), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPWIDTH)
        w.setframerate(RATE)
        for frame in inp.decode(audio=0):
            for rf in as_list(rs.resample(frame)):
                w.writeframes(bytes(rf.planes[0])[: rf.samples * SAMPWIDTH])
        try:
            for rf in as_list(rs.resample(None)):
                w.writeframes(bytes(rf.planes[0])[: rf.samples * SAMPWIDTH])
        except Exception:
            pass
    inp.close()


def _convert_to_wav(exe, src, dst_wav):
    if not exe:
        _av_to_wav(src, dst_wav)
        return
    cmd = [exe, "-y", "-loglevel", "error", "-i", str(src),
           "-ac", str(CHANNELS), "-ar", str(RATE),
           "-sample_fmt", "s16", str(dst_wav)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise NarrationError(f"ffmpeg audio convert failed:\n{p.stderr[-800:]}")


def _wav_duration(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def synthesize(text, out_wav, engine="mock", voice=None):
    """Create a 44100 Hz mono 16-bit WAV for `text`; return its duration in seconds."""
    voice = voice or {}
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if not text or not text.strip():
        return 0.0

    if engine == "mock":
        silence_wav(out_wav, estimate_duration(text))
        return _wav_duration(out_wav)

    if engine == "android":
        from .android_media import tts_to_wav
        try:
            tts_to_wav(text, out_wav, voice)
        except Exception as e:
            raise NarrationError(f"voice synthesis failed (android): {e}") from e
        return _wav_duration(out_wav)

    exe = ffmpeg_exe()
    tmp = out_wav.with_suffix(".tmp")
    try:
        if engine == "edge":
            import edge_tts
            v = voice.get("name") or "fil-PH-AngeloNeural"
            kwargs = {}
            if voice.get("rate"):
                kwargs["rate"] = voice["rate"]
            async def run():
                c = edge_tts.Communicate(text, v, **kwargs)
                await c.save(str(tmp))
            asyncio.run(run())
        elif engine == "gtts":
            from gtts import gTTS
            gTTS(text=text, lang=voice.get("lang", "tl")).save(str(tmp))
        elif engine == "pyttsx3":
            import pyttsx3
            e = pyttsx3.init()
            if voice.get("rate"):
                e.setProperty("rate", int(voice["rate"]))
            e.save_to_file(text, str(tmp))
            e.runAndWait()
        else:
            raise NarrationError(f"unknown voice engine: {engine}")
        _convert_to_wav(exe, tmp, out_wav)
    except NarrationError:
        raise
    except Exception as e:
        raise NarrationError(
            f"voice synthesis failed ({engine}): {e}\n"
            "Check your internet connection (edge/gtts need it), or run with "
            "--no-audio, or set \"engine\": \"pyttsx3\" for offline."
        ) from e
    finally:
        tmp.unlink(missing_ok=True)
    return _wav_duration(out_wav)


def silence_wav(path, seconds):
    frames = int(round(seconds * RATE))
    write_track(path, [b"\x00" * (frames * 2)])


def write_track(path, chunk_iterable):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPWIDTH)
        w.setframerate(RATE)
        for chunk in chunk_iterable:
            w.writeframes(chunk)


def build_full_track(scene_wavs, scene_frames, out_path, fps):
    """Concatenate scene narration WAVs, padding each to its exact video length."""
    def chunks():
        for wav, frames in zip(scene_wavs, scene_frames):
            target_samples = int(round(frames * RATE / fps))
            target_bytes = target_samples * 2  # 16-bit mono
            if wav is None:
                yield b"\x00" * target_bytes
                continue
            with wave.open(str(wav), "rb") as r:
                data = r.readframes(r.getnframes())
            if len(data) > target_bytes:
                # narration slightly longer than its scene: trim the tail
                data = data[:target_bytes]
            elif len(data) < target_bytes:
                yield data
                yield b"\x00" * (target_bytes - len(data))
                continue
            yield data

    write_track(out_path, chunks())
