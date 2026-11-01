"""Video writer: ffmpeg pipe on desktop, PyAV (no external binary) on Android."""
import subprocess
import wave
from pathlib import Path

from . import narration

RATE = narration.RATE


class _FfmpegWriter:
    def __init__(self, exe, out_mp4, w, h, fps, crf, track, title):
        cmd = [exe, "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-video_size", f"{w}x{h}", "-framerate", str(fps), "-i", "pipe:0"]
        if track:
            cmd += ["-i", str(track)]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        cmd += ["-c:a", "aac", "-b:a", "160k", "-shortest"] if track else ["-an"]
        cmd += ["-metadata", f"title={title}", str(out_mp4)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def write(self, img):
        try:
            self.proc.stdin.write(img.tobytes())
        except BrokenPipeError:
            pass

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.wait()
        err = self.proc.stderr.read().decode("utf8", "replace")
        self.proc.stderr.close()
        if self.proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed (code {self.proc.returncode}):\n{err[-1500:]}")


class _AvWriter:
    """Encodes with PyAV. Tries libx264, then libopenh264, then mpeg4."""

    def __init__(self, out_mp4, w, h, fps, crf, track, title):
        import av
        self.av = av
        self.fps = fps
        if w % 2 or h % 2:
            raise RuntimeError("video width and height must be even numbers")
        self.c = av.open(str(out_mp4), mode="w", options={"movflags": "+faststart"})
        self.v = None
        last = None
        for name in ("libx264", "libopenh264", "mpeg4"):
            try:
                self.v = self.c.add_stream(name, rate=fps)
                break
            except Exception as e:  # codec not compiled in
                last = e
        if self.v is None:
            raise RuntimeError(f"no usable video encoder in this PyAV build: {last}")
        self.v.width, self.v.height, self.v.pix_fmt = w, h, "yuv420p"
        if self.v.codec_context.name == "libx264":
            self.v.options = {"crf": str(crf), "preset": "veryfast"}
        else:
            self.v.bit_rate = 6_000_000
        print(f"  video encoder: {self.v.codec_context.name}")
        self.c.metadata["title"] = title
        self.a = self.wf = None
        self.a_pos = 0
        self.n = 0
        if track:
            self.wf = wave.open(str(track), "rb")
            self.a = self.c.add_stream("aac", rate=RATE)
            try:
                self.a.layout = "mono"
            except Exception:
                pass

    def _feed_audio(self, upto):
        av = self.av
        while self.a_pos < upto:
            n = min(1024, upto - self.a_pos)
            data = self.wf.readframes(n)
            got = len(data) // 2
            if got == 0:                      # track ended early -> silence
                data, got = b"\x00" * (n * 2), n
            fr = av.AudioFrame(format="s16", layout="mono", samples=got)
            fr.planes[0].update(data)
            fr.sample_rate = RATE
            fr.pts = self.a_pos
            for pkt in self.a.encode(fr):
                self.c.mux(pkt)
            self.a_pos += got

    def write(self, img):
        fr = self.av.VideoFrame.from_image(img)
        fr.pts = self.n
        for pkt in self.v.encode(fr):
            self.c.mux(pkt)
        self.n += 1
        if self.a is not None:
            self._feed_audio(int(round(self.n * RATE / self.fps)))

    def close(self):
        try:
            for pkt in self.v.encode(None):
                self.c.mux(pkt)
            if self.a is not None:
                for pkt in self.a.encode(None):
                    self.c.mux(pkt)
        finally:
            self.c.close()
            if self.wf:
                self.wf.close()


def open_writer(out_mp4, w, h, fps, crf, track, title):
    exe = narration.ffmpeg_exe()
    if exe:
        return _FfmpegWriter(exe, out_mp4, w, h, fps, crf, track, title)
    if narration.ON_ANDROID:
        from .android_media import AndroidWriter
        return AndroidWriter(out_mp4, w, h, fps, crf, track, title)
    return _AvWriter(out_mp4, w, h, fps, crf, track, title)
