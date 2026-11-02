"""Android-native media (pyjnius): TextToSpeech -> WAV and MediaCodec H.264/AAC -> MP4.

No compiled third-party libraries are needed; everything uses the phone's own codecs.
"""
import threading
import time
import wave
from pathlib import Path

RATE = 44100
_keep = []
_done = {}


def _cls(name):
    from jnius import autoclass
    return autoclass(name)


def _activity():
    return _cls("org.kivy.android.PythonActivity").mActivity


# ------------------------------ text to speech ------------------------------
_engines = {}
_done_listener = None
_announced = set()


def _make_done_listener():
    global _done_listener
    if _done_listener is None:
        from jnius import PythonJavaClass, java_method

        class OnDone(PythonJavaClass):
            # also fires when synthesis fails, so we always check the output file afterwards
            __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnUtteranceCompletedListener"]
            __javacontext__ = "app"

            @java_method("(Ljava/lang/String;)V")
            def onUtteranceCompleted(self, uid):
                ev = _done.get(str(uid))
                if ev:
                    ev.set()

        _done_listener = OnDone()
    return _done_listener


def _open_engine(pkg):
    """TextToSpeech instance for an engine package (None = phone default), or None."""
    if pkg in _engines:
        return _engines[pkg]
    from jnius import PythonJavaClass, java_method

    ready, status = threading.Event(), {}

    class OnInit(PythonJavaClass):
        __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
        __javacontext__ = "app"

        @java_method("(I)V")
        def onInit(self, st):
            status["v"] = st
            ready.set()

    init = OnInit()
    _keep.append(init)
    TTS = _cls("android.speech.tts.TextToSpeech")
    try:
        tts = TTS(_activity(), init, pkg) if pkg else TTS(_activity(), init)
    except Exception:
        _engines[pkg] = None
        return None
    if not ready.wait(20) or status.get("v") != 0:
        try:
            tts.shutdown()
        except Exception:
            pass
        _engines[pkg] = None
        return None
    tts.setOnUtteranceCompletedListener(_make_done_listener())
    _engines[pkg] = tts
    return tts


def _read_wav(path):
    """Tolerant WAV reader (engines often write streaming headers with bad sizes)."""
    import struct
    b = Path(path).read_bytes()
    if b[:4] != b"RIFF":
        raise RuntimeError("not a WAV file")
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(b):
        cid = b[pos:pos + 4]
        size = int.from_bytes(b[pos + 4:pos + 8], "little")
        if cid == b"fmt ":
            _, ch, rate, _, _, bits = struct.unpack("<HHIIHH", b[pos + 8:pos + 24])
            fmt = (ch, bits // 8, rate)
        elif cid == b"data":
            start = pos + 8
            end = start + size if 0 < size <= len(b) - start else len(b)
            data = b[start:end]
            break
        pos += 8 + size + (size & 1)
    if fmt is None or not data:
        raise RuntimeError("WAV has no audio data")
    return fmt[0], fmt[1], fmt[2], data


def _normalize_wav(src, dst):
    from . import pcm
    ch, sw, rate, data = _read_wav(src)
    data = pcm.ratecv(pcm.tomono(pcm.to16(data, sw), ch), rate, RATE)
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)


def _voice_obj(tts, name):
    from jnius import cast
    for o in tts.getVoices().toArray():
        v = cast("android.speech.tts.Voice", o)
        if str(v.getName()) == name:
            return v
    return None


def list_voices():
    """Installed phone voices: [{'name','tag','lang','network'}] sorted by language."""
    from jnius import cast
    out = []
    for pkg in ("com.google.android.tts", None):
        tts = _open_engine(pkg)
        if tts is None:
            continue
        try:
            for o in tts.getVoices().toArray():
                v = cast("android.speech.tts.Voice", o)
                loc = v.getLocale()
                out.append({"name": str(v.getName()), "tag": str(loc.toLanguageTag()),
                            "lang": str(loc.getDisplayName()),
                            "network": bool(v.isNetworkConnectionRequired())})
        except Exception:
            continue
        if out:
            break
    return sorted(out, key=lambda v: (v["lang"], v["name"]))


def speak_sample(text, voice=None):
    """Play a short sample on the speaker (for the voice picker)."""
    from jnius import cast
    voice = voice or {}
    for pkg in ("com.google.android.tts", None):
        tts = _open_engine(pkg)
        if tts is None:
            continue
        v = _voice_obj(tts, voice["voice_name"]) if voice.get("voice_name") else None
        if v is not None:
            tts.setVoice(v)
        elif voice.get("locale"):
            tts.setLanguage(_cls("java.util.Locale").forLanguageTag(voice["locale"]))
        tts.setSpeechRate(float(voice.get("speech_rate") or 1.0))
        cs = cast("java.lang.CharSequence", _cls("java.lang.String")(text))
        tts.speak(cs, 0, None, "sample")
        return True
    return False


def _try_synth(tts, tag, text, raw, voice_name=None, rate=None):
    from jnius import cast
    if tag == "@voice":
        v = _voice_obj(tts, voice_name)
        if v is None:
            return False, "chosen voice not installed"
        tts.setVoice(v)
    else:
        loc = _cls("java.util.Locale").forLanguageTag(tag)
        if tts.isLanguageAvailable(loc) < 0:
            return False, "language not installed"
        tts.setLanguage(loc)
    tts.setSpeechRate(float(rate or 1.0))
    raw.unlink(missing_ok=True)
    uid = f"u{time.time_ns()}"
    ev = threading.Event()
    _done[uid] = ev
    cs = cast("java.lang.CharSequence", _cls("java.lang.String")(text))
    rc = tts.synthesizeToFile(cs, None, _cls("java.io.File")(str(raw)), uid)
    if rc != 0:
        _done.pop(uid, None)
        return False, "request rejected"
    ev.wait(90)
    _done.pop(uid, None)
    time.sleep(0.3)
    if raw.is_file() and raw.stat().st_size > 200:
        return True, ""
    return False, "engine wrote no audio"


def tts_to_wav(text, out_wav, voice=None):
    voice = voice or {}
    tags = []
    for t in (voice.get("locale"), "fil-PH", "tl-PH", "en-US", "en-GB"):
        if t and t not in tags:
            tags.append(t)
    if voice.get("voice_name"):
        tags.insert(0, "@voice")
    rate = voice.get("speech_rate")
    raw = Path(out_wav).with_suffix(".raw.wav")
    tried = []
    for pkg in ("com.google.android.tts", None):
        tts = _open_engine(pkg)
        if tts is None:
            tried.append(f"{pkg or 'default engine'}: not available")
            continue
        for tag in tags:
            ok, why = _try_synth(tts, tag, text, raw, voice.get("voice_name"), rate)
            if ok:
                _normalize_wav(raw, out_wav)
                raw.unlink(missing_ok=True)
                key = (pkg, tag)
                if key not in _announced:
                    _announced.add(key)
                    print(f"  voice: {tag} ({pkg or 'default engine'})")
                return
            tried.append(f"{(pkg or 'default').split('.')[-1]}/{tag}: {why}")
    raise RuntimeError("no phone voice produced audio. Tried: " + "; ".join(tried) +
                       ". Install 'Speech Recognition & Synthesis from Google' and download "
                       "a voice in Settings > Text-to-speech output.")


# ----------------------------- audio decoding (for background music) -----------------------------
def decode_audio_to_wav(src, out_wav, max_seconds=None):
    """Decode mp3/m4a/ogg/flac... with MediaCodec -> 44.1 kHz mono WAV. PCM never passes
    through Python while decoding: Java writes it straight to a temp file."""
    from . import pcm
    Extractor = _cls("android.media.MediaExtractor")
    MediaCodec = _cls("android.media.MediaCodec")
    ex = Extractor()
    ex.setDataSource(str(src))
    fmt = mime = None
    for i in range(ex.getTrackCount()):
        f = ex.getTrackFormat(i)
        m = str(f.getString("mime") or "")
        if m.startswith("audio/"):
            ex.selectTrack(i)
            fmt, mime = f, m
            break
    if fmt is None:
        raise RuntimeError("no audio track in that file")
    rate, chans = fmt.getInteger("sample-rate"), fmt.getInteger("channel-count")
    dec = MediaCodec.createDecoderByType(mime)
    dec.configure(fmt, None, None, 0)
    dec.start()
    raw = Path(out_wav).with_suffix(".pcm")
    fos = _cls("java.io.FileOutputStream")(str(raw))
    ch = fos.getChannel()
    info = _cls("android.media.MediaCodec$BufferInfo")()
    limit = int(max_seconds * rate * chans * 2) if max_seconds else None
    in_done = out_done = False
    written, t0 = 0, time.time()
    while not out_done and time.time() - t0 < 240:
        if not in_done:
            i = dec.dequeueInputBuffer(10000)
            if i >= 0:
                buf = dec.getInputBuffer(i)
                n = ex.readSampleData(buf, 0)
                if n < 0:
                    dec.queueInputBuffer(i, 0, 0, 0, 4)
                    in_done = True
                else:
                    dec.queueInputBuffer(i, 0, n, ex.getSampleTime(), 0)
                    ex.advance()
        o = dec.dequeueOutputBuffer(info, 10000)
        if o == -2:
            f2 = dec.getOutputFormat()
            rate, chans = f2.getInteger("sample-rate"), f2.getInteger("channel-count")
        elif o >= 0:
            if info.size > 0:
                ob = dec.getOutputBuffer(o)
                ob.position(info.offset)
                ob.limit(info.offset + info.size)
                ch.write(ob)
                written += info.size
            dec.releaseOutputBuffer(o, False)
            if (info.flags & 4) or (limit and written >= limit):
                out_done = True
    ch.close()
    fos.close()
    dec.stop()
    dec.release()
    ex.release()
    raw_pcm = raw.read_bytes()
    raw.unlink(missing_ok=True)
    mono = pcm.ratecv(pcm.tomono(raw_pcm, chans), rate, RATE)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(mono)


# ----------------------------- MediaCodec encoders -----------------------------
class _Encoder:
    """One MediaCodec + one MediaMuxer (single track). Drains encoded samples to the file."""

    def __init__(self, codec, out_path, fps=None):
        self.c = codec
        self.mux = _cls("android.media.MediaMuxer")(str(out_path), 0)  # MPEG_4
        self.info = _cls("android.media.MediaCodec$BufferInfo")()
        self.track, self.n, self.fps, self.eos = -1, 0, fps, False

    def drain(self, wait_us=0):
        while not self.eos:
            i = self.c.dequeueOutputBuffer(self.info, wait_us)
            if i == -1:               # INFO_TRY_AGAIN_LATER
                return
            if i == -2:               # INFO_OUTPUT_FORMAT_CHANGED
                self.track = self.mux.addTrack(self.c.getOutputFormat())
                self.mux.start()
                continue
            if i < 0:
                continue
            buf = self.c.getOutputBuffer(i)
            size, flags = self.info.size, self.info.flags
            if flags & 2:             # codec config, already in the track format
                size = 0
            if size > 0 and self.track >= 0:
                if self.fps:          # video: exact timestamps, independent of render speed
                    self.info.presentationTimeUs = int(self.n * 1000000 / self.fps)
                off = self.info.offset
                buf.position(off)
                buf.limit(off + size)
                self.mux.writeSampleData(self.track, buf, self.info)
                self.n += 1
            self.c.releaseOutputBuffer(i, False)
            if flags & 4:             # END_OF_STREAM
                self.eos = True

    def finish(self, timeout=60):
        t0 = time.time()
        while not self.eos and time.time() - t0 < timeout:
            self.drain(10000)
        self.c.stop()
        self.c.release()
        if self.track >= 0:
            self.mux.stop()
        self.mux.release()


def _encode_audio(wav_path, out_path):
    MediaFormat = _cls("android.media.MediaFormat")
    MediaCodec = _cls("android.media.MediaCodec")
    fmt = MediaFormat.createAudioFormat("audio/mp4a-latm", RATE, 1)
    fmt.setInteger("aac-profile", 2)          # AAC-LC
    fmt.setInteger("bitrate", 128000)
    fmt.setInteger("max-input-size", 16384)
    c = MediaCodec.createEncoderByType("audio/mp4a-latm")
    c.configure(fmt, None, None, 1)
    c.start()
    enc = _Encoder(c, out_path)

    def input_buffer():
        while True:
            idx = c.dequeueInputBuffer(10000)
            if idx >= 0:
                return idx
            enc.drain(0)

    pos = 0
    with wave.open(str(wav_path), "rb") as w:
        while True:
            data = w.readframes(4096)
            if not data:
                break
            idx = input_buffer()
            ib = c.getInputBuffer(idx)
            ib.clear()
            ib.put(data)
            c.queueInputBuffer(idx, 0, len(data), int(pos * 1000000 / RATE), 0)
            pos += len(data) // 2
            enc.drain(0)
    idx = input_buffer()
    c.queueInputBuffer(idx, 0, 0, int(pos * 1000000 / RATE), 4)   # EOS
    enc.finish()


def _merge(video_path, audio_path, out_path):
    Extractor = _cls("android.media.MediaExtractor")
    Muxer = _cls("android.media.MediaMuxer")
    Info = _cls("android.media.MediaCodec$BufferInfo")
    ev, ea = Extractor(), Extractor()
    ev.setDataSource(str(video_path))
    ea.setDataSource(str(audio_path))
    ev.selectTrack(0)
    ea.selectTrack(0)
    mux = Muxer(str(out_path), 0)
    tv = mux.addTrack(ev.getTrackFormat(0))
    ta = mux.addTrack(ea.getTrackFormat(0))
    mux.start()
    buf = _cls("java.nio.ByteBuffer").allocateDirect(1 << 20)
    info = Info()
    while True:
        tsv, tsa = ev.getSampleTime(), ea.getSampleTime()
        if tsv < 0 and tsa < 0:
            break
        ex, tr = (ev, tv) if (tsa < 0 or (tsv >= 0 and tsv <= tsa)) else (ea, ta)
        n = ex.readSampleData(buf, 0)
        if n < 0:
            break
        info.set(0, n, ex.getSampleTime(), ex.getSampleFlags())
        mux.writeSampleData(tr, buf, info)
        ex.advance()
    mux.stop()
    mux.release()
    ev.release()
    ea.release()


class AndroidWriter:
    """Same interface as the other writers: write(PIL image) ... close()."""

    def __init__(self, out_mp4, w, h, fps, crf, track, title):
        MediaFormat = _cls("android.media.MediaFormat")
        MediaCodec = _cls("android.media.MediaCodec")
        self.out = Path(out_mp4)
        self.tmp_v = self.out.with_suffix(".video.mp4")
        self.tmp_a = self.out.with_suffix(".audio.m4a")
        self.track = track
        self.w, self.h = w, h
        fmt = MediaFormat.createVideoFormat("video/avc", w, h)
        fmt.setInteger("color-format", 0x7F000789)     # COLOR_FormatSurface
        fmt.setInteger("bitrate", 8000000)
        fmt.setInteger("frame-rate", int(fps))
        fmt.setInteger("i-frame-interval", 1)
        vc = MediaCodec.createEncoderByType("video/avc")
        vc.configure(fmt, None, None, 1)               # CONFIGURE_FLAG_ENCODE
        self.vc = vc
        self.surface = vc.createInputSurface()
        vc.start()
        self.enc = _Encoder(vc, self.tmp_v, fps=fps)
        self.bitmap = _cls("android.graphics.Bitmap").createBitmap(
            w, h, _cls("android.graphics.Bitmap$Config").ARGB_8888)
        self.wrap = _cls("java.nio.ByteBuffer").wrap
        print("  video encoder: Android MediaCodec (H.264)")

    def write(self, img):
        data = img.convert("RGBA").tobytes()
        try:
            buf = self.wrap(data)
        except Exception:
            buf = self.wrap(bytearray(data))
        self.bitmap.copyPixelsFromBuffer(buf)
        canvas = self.surface.lockHardwareCanvas()
        canvas.drawBitmap(self.bitmap, 0.0, 0.0, None)
        self.surface.unlockCanvasAndPost(canvas)
        self.enc.drain(0)

    def close(self):
        self.vc.signalEndOfInputStream()
        self.enc.finish()
        if self.track:
            _encode_audio(self.track, self.tmp_a)
            _merge(self.tmp_v, self.tmp_a, self.out)
            self.tmp_v.unlink(missing_ok=True)
            self.tmp_a.unlink(missing_ok=True)
        else:
            self.out.unlink(missing_ok=True)
            self.tmp_v.rename(self.out)
