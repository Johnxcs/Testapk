"""Background music: decode any audio file, loop it under the narration, fade in/out."""
import subprocess
import wave
from pathlib import Path

from . import narration, pcm

RATE = 44100


def decode(src, out_wav, seconds):
    """Any audio file -> 44.1 kHz mono 16-bit WAV (at most `seconds` long)."""
    exe = narration.ffmpeg_exe()
    if exe:
        subprocess.run([exe, "-y", "-loglevel", "error", "-i", str(src), "-t", f"{seconds:.2f}",
                        "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(out_wav)],
                       check=True, capture_output=True)
    elif narration.ON_ANDROID:
        from .android_media import decode_audio_to_wav
        decode_audio_to_wav(src, out_wav, seconds)
    else:
        narration._av_to_wav(src, out_wav)


def _fade(data, fade_in, fade_out):
    blk = int(RATE * 0.02) * 2                      # 20 ms blocks
    n = len(data) // blk
    if n < 4:
        return data
    fi, fo = min(n // 2, int(fade_in / 0.02)), min(n // 2, int(fade_out / 0.02))
    out = [data[i * blk:(i + 1) * blk] for i in range(n)] + [data[n * blk:]]
    for i in range(fi):
        out[i] = pcm.mul(out[i], (i + 1) / (fi + 1))
    for i in range(fo):
        out[n - 1 - i] = pcm.mul(out[n - 1 - i], (i + 1) / (fo + 1))
    return b"".join(out)


def mix_into(track_wav, music_src, volume, work_dir):
    """Mix music (looped, faded, at `volume` 0..1) into the finished narration track."""
    track_wav = Path(track_wav)
    with wave.open(str(track_wav), "rb") as r:
        narr = r.readframes(r.getnframes())
    need = len(narr)
    seconds = need / 2 / RATE
    m_wav = Path(work_dir) / "music.wav"
    decode(music_src, m_wav, seconds + 1)
    with wave.open(str(m_wav), "rb") as r:
        music = r.readframes(r.getnframes())
    if not music:
        raise RuntimeError("the music file has no audio")
    music = (music * (need // len(music) + 1))[:need]
    music = pcm.mul(_fade(music, 1.0, 1.5), max(0.0, min(1.0, float(volume))))
    mixed = pcm.add(narr, music)
    with wave.open(str(track_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(mixed)
