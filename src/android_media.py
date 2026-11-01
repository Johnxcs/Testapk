"""Android-native media (pyjnius): TextToSpeech -> WAV and MediaCodec H.264/AAC -> MP4.

No compiled third-party libraries are needed; everything uses the phone's own codecs.
"""
import threading
import time
import wave
from pathlib import Path

RATE = 44100
_tts = None
_keep = []
_done = {}


def _cls(name):
    from jnius import autoclass
    return autoclass(name)


def _activity():
    return _cls("org.kivy.android.PythonActivity").mActivity


# ------------------------------ text to speech ------------------------------
def _get_tts(tags):
    global _tts
    if _tts is not None:
        return _tts
    from jnius import PythonJavaClass, java_method

    ready, status = threading.Event(), {}

    class OnInit(PythonJavaClass):
        __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
        __javacontext__ = "app"

        @java_method("(I)V")
        def onInit(self, st):
            status["v"] = st
            ready.set()

    class OnDone(PythonJavaClass):
        __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnUtteranceCompletedListener"]
        __javacontext__ = "app"

        @java_method("(Ljava/lang/String;)V")
        def onUtteranceCompleted(self, uid):
            ev = _done.get(str(uid))
            if ev:
                ev.set()

    init, done = OnInit(), OnDone()
    _keep.extend([init, done])
    tts = _cls("android.speech.tts.TextToSpeech")(_activity(), init)
    if not ready.wait(20) or status.get("v") != 0:
        raise RuntimeError("Phone text-to-speech isn't available. Install or enable "
                           "'Speech Recognition & Synthesis from Google' in Android settings.")
    tts.setOnUtteranceCompletedListener(done)
    Locale = _cls("java.util.Locale")
    for i, tag in enumerate(tags):
        loc = Locale.forLanguageTag(tag)
        if tts.isLanguageAvailable(loc) >= 0:
            tts.setLanguage(loc)
            if i > 0:
                print(f"  (voice for {tags[0]} not installed; using {tag})")
            break
    else:
        raise RuntimeError("No usable text-to-speech voice found on this phone.")
    _tts = tts
    return tts


def _normalize_wav(src, dst):
    import audioop
    with wave.open(str(src), "rb") as r:
        ch, sw, rate, n = r.getnchannels(), r.getsampwidth(), r.getframerate(), r.getnframes()
        data = r.readframes(n)
    if sw != 2:
        data = audioop.lin2lin(data, sw, 2)
    if ch == 2:
        data = audioop.tomono(data, 2, 0.5, 0.5)
    if rate != RATE:
        data, _ = audioop.ratecv(data, 2, 1, rate, RATE, None)
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)


def tts_to_wav(text, out_wav, voice=None):
    from jnius import cast
    voice = voice or {}
    tts = _get_tts([voice.get("locale") or "fil-PH", "tl-PH", "en-US"])
    uid = f"u{time.time_ns()}"
    ev = threading.Event()
    _done[uid] = ev
    raw = Path(out_wav).with_suffix(".raw.wav")
    raw.unlink(missing_ok=True)
    cs = cast("java.lang.CharSequence", _cls("java.lang.String")(text))
    rc = tts.synthesizeToFile(cs, None, _cls("java.io.File")(str(raw)), uid)
    if rc != 0:
        raise RuntimeError("text-to-speech refused the request")
    ev.wait(120)
    _done.pop(uid, None)
    if not raw.is_file() or raw.stat().st_size < 100:
        raise RuntimeError("text-to-speech produced no audio")
    time.sleep(0.2)
    _normalize_wav(raw, out_wav)
    raw.unlink(missing_ok=True)


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
