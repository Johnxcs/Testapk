"""Copyright helpers for imported music.

What this can and cannot do: it reads the song's tags (title / artist / album / copyright),
spots signs of a commercial release or of a free licence, and can optionally ask the AudD
fingerprint service whether the audio matches a known song. NOTHING here can prove a song is
safe to use. "No match" is not clearance; YouTube/TikTok/Instagram run their own checks.
"""
import json
import re
import subprocess
import uuid
from pathlib import Path

from . import narration

LICENSES = {                       # key -> label shown in the app
    "own": "I made it / I own the rights",
    "licensed": "Royalty-free or licensed for videos",
    "cc": "Creative Commons (credit required)",
    "copyrighted": "Copyrighted \u2014 I'll use it anyway",
    "unsure": "I'm not sure",
}
FREE_SOURCES = "YouTube Audio Library, Pixabay Music, Free Music Archive, Incompetech, Uppbeat"

COMMERCIAL = re.compile(r"(records|recordings|music group|entertainment|universal|sony|warner|\bemi\b|"
                        r"atlantic|columbia|interscope|capitol|rca\b|\u2117|\(p\)|\u00a9|all rights reserved)", re.I)
FREE = re.compile(r"(creative commons|cc[- ]by|cc0|public domain|royalty[- ]free|no copyright|pixabay|"
                  r"incompetech|bensound|free music archive|audio library|kevin macleod|purple planet|uppbeat)", re.I)
OFFICIAL = re.compile(r"official (video|audio|music video|lyric)|\(lyrics?\)|\bft\.|\bfeat\.", re.I)


# ------------------------------------------------------------------ tags
def _syncsafe(b):
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _text(body):
    if not body:
        return ""
    enc, data = body[0], body[1:]
    try:
        if enc == 0:
            s = data.decode("latin-1")
        elif enc == 1:
            s = data.decode("utf-16")
        elif enc == 2:
            s = data.decode("utf-16-be")
        else:
            s = data.decode("utf-8")
    except Exception:
        s = data.decode("latin-1", "replace")
    return s.replace("\x00", " ").strip()


ID3_MAP = {"TIT2": "title", "TPE1": "artist", "TALB": "album", "TCOP": "copyright", "TSRC": "isrc",
           "TPUB": "publisher", "TYER": "year", "TDRC": "year", "TPE2": "album_artist", "TCOM": "composer"}


def _id3v2(b):
    if b[:3] != b"ID3" or len(b) < 10:
        return {}
    ver, flags, size = b[3], b[5], _syncsafe(b[6:10])
    pos, end, tags = 10, min(len(b), 10 + size), {}
    if flags & 0x40 and len(b) >= pos + 4:      # extended header
        pos += (_syncsafe(b[pos:pos + 4]) if ver == 4 else int.from_bytes(b[pos:pos + 4], "big") + 4)
    while pos + 10 <= end:
        fid = b[pos:pos + 4].decode("latin-1")
        if not fid.strip("\x00"):
            break
        fsize = _syncsafe(b[pos + 4:pos + 8]) if ver == 4 else int.from_bytes(b[pos + 4:pos + 8], "big")
        body = b[pos + 10:pos + 10 + fsize]
        pos += 10 + fsize
        if fid in ID3_MAP and ID3_MAP[fid] not in tags:
            t = _text(body)
            if t:
                tags[ID3_MAP[fid]] = t
    return tags


def _id3v1(b):
    t = b[-128:]
    if len(t) == 128 and t[:3] == b"TAG":
        f = lambda a, z: t[a:z].split(b"\x00")[0].decode("latin-1").strip()
        return {k: v for k, v in (("title", f(3, 33)), ("artist", f(33, 63)),
                                  ("album", f(63, 93)), ("year", f(93, 97))) if v}
    return {}


MP4_MAP = {b"\xa9nam": "title", b"\xa9ART": "artist", b"\xa9alb": "album", b"cprt": "copyright",
           b"\xa9day": "year", b"aART": "album_artist", b"\xa9wrt": "composer"}


def _mp4(b):
    i = b.find(b"ilst")
    if i < 4:
        return {}
    end = i - 4 + int.from_bytes(b[i - 4:i], "big")
    pos, tags = i + 4, {}
    while pos + 8 <= min(end, len(b)):
        size = int.from_bytes(b[pos:pos + 4], "big")
        kind = b[pos + 4:pos + 8]
        if size < 8:
            break
        d = b.find(b"data", pos, pos + size)
        if kind in MP4_MAP and d > 0:
            val = b[d + 12:pos + size].decode("utf-8", "replace").strip("\x00 ")
            if val:
                tags[MP4_MAP[kind]] = val
        pos += size
    return tags


def _ffmpeg_meta(path):
    exe = narration.ffmpeg_exe()
    if not exe:
        return {}
    try:
        out = subprocess.run([exe, "-v", "error", "-i", str(path), "-f", "ffmetadata", "-"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return {}
    tags = {}
    for line in out.splitlines():
        if "=" in line and not line.startswith(";"):
            k, v = line.split("=", 1)
            k = k.strip().lower()
            k = {"date": "year", "label": "publisher", "album_artist": "album_artist"}.get(k, k)
            if v.strip():
                tags.setdefault(k, v.strip())
    return tags


def _android_meta(path):
    try:
        from jnius import autoclass
        r = autoclass("android.media.MediaMetadataRetriever")()
        r.setDataSource(str(path))
        keys = {7: "title", 2: "artist", 1: "album", 13: "album_artist", 4: "composer", 8: "year"}
        tags = {}
        for code, name in keys.items():
            v = r.extractMetadata(code)
            if v:
                tags[name] = str(v)
        r.release()
        return tags
    except Exception:
        return {}


def read_tags(path):
    """Best-effort tags from the file itself (mp3 ID3, m4a atoms, else ffmpeg / Android)."""
    path = Path(path)
    try:
        data = path.read_bytes()[:24 * 1024 * 1024]
    except Exception:
        return {}
    tags = _id3v2(data) or {}
    tags = {**_id3v1(data), **tags}
    if not tags and (b"ftyp" in data[:64]):
        tags = _mp4(data)
    if not tags:
        tags = _ffmpeg_meta(path) or (_android_meta(path) if narration.ON_ANDROID else {})
    return tags


# ------------------------------------------------------------------ verdict
def assess(tags, filename=""):
    """-> {'risk': likely|possible|free_hint|unknown, 'reasons': [...], 'credit': str}"""
    reasons, score = [], 0
    blob = " ".join(str(v) for v in tags.values()) + " " + filename
    if FREE.search(blob):
        reasons.append("The tags or file name mention a free / Creative Commons licence.")
        credit = f"Music: {tags.get('title', Path(filename).stem)}" + (f" by {tags['artist']}" if tags.get("artist") else "")
        return {"risk": "free_hint", "reasons": reasons, "credit": credit}
    if tags.get("artist") and tags.get("title"):
        score += 2
        reasons.append("It has an artist and a title tag, like a released song.")
    if tags.get("album"):
        score += 2
        reasons.append("It has an album tag.")
    if COMMERCIAL.search(" ".join(str(tags.get(k, "")) for k in ("copyright", "publisher", "album"))):
        score += 3
        reasons.append("The copyright / label tag names a music company.")
    if tags.get("isrc"):
        score += 2
        reasons.append("It has an ISRC code, which commercial releases carry.")
    stem = Path(filename).stem
    if OFFICIAL.search(stem):
        score += 4
        reasons.append("The file name looks like a downloaded commercial song.")
    elif re.match(r"^[^-]{2,}\s-\s[^-]{2,}", stem):
        score += 1
        reasons.append("The file name looks like “Artist - Title”.")
    risk = "likely" if score >= 4 else "possible" if score >= 2 else "unknown"
    if risk == "unknown":
        reasons.append("No tags found. That does not mean the song is free to use.")
    credit = f"Music: {tags.get('title', stem)}" + (f" by {tags['artist']}" if tags.get("artist") else "")
    return {"risk": risk, "reasons": reasons, "credit": credit}


# ------------------------------------------------------------------ online fingerprint (AudD)
def _multipart(fields, file_field, filename, file_bytes, boundary):
    out = bytearray()
    for k, v in fields.items():
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n").encode()
    out += file_bytes + f"\r\n--{boundary}--\r\n".encode()
    return bytes(out)


def _post(url, body, boundary, timeout=40):
    if narration.ON_ANDROID:                      # system HTTPS stack: no OpenSSL needed
        from jnius import autoclass, cast
        conn = cast("java.net.HttpURLConnection", autoclass("java.net.URL")(url).openConnection())
        conn.setRequestMethod("POST")
        conn.setDoOutput(True)
        conn.setConnectTimeout(timeout * 1000)
        conn.setReadTimeout(timeout * 1000)
        conn.setRequestProperty("Content-Type", f"multipart/form-data; boundary={boundary}")
        conn.setFixedLengthStreamingMode(len(body))
        out = conn.getOutputStream()
        try:
            out.write(body)
        except Exception:
            out.write(bytearray(body))
        out.flush()
        out.close()
        stream = conn.getInputStream() if conn.getResponseCode() < 400 else conn.getErrorStream()
        sc = autoclass("java.util.Scanner")(stream, "UTF-8")
        sc.useDelimiter("\\A")
        return str(sc.next()) if sc.hasNext() else ""
    import urllib.request
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def excerpt_wav(src, out_wav, start=4.0, length=20.0):
    """~20 s of the song as WAV for the fingerprint check."""
    import wave
    from . import music
    tmp = Path(out_wav).with_suffix(".full.wav")
    music.decode(src, tmp, start + length + 1)
    with wave.open(str(tmp), "rb") as r:
        rate = r.getframerate()
        r.setpos(min(r.getnframes() - 1, int(start * rate)))
        data = r.readframes(int(length * rate))
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)
    tmp.unlink(missing_ok=True)


def audd_lookup(wav_path, token):
    """-> None (no match) or {'artist','title','album','label','release_date'}. Raises on errors."""
    boundary = "----codereels" + uuid.uuid4().hex
    body = _multipart({"api_token": token}, "file", "excerpt.wav", Path(wav_path).read_bytes(), boundary)
    raw = _post("https://api.audd.io/", body, boundary)
    try:
        data = json.loads(raw)
    except Exception:
        raise RuntimeError("the check service sent an unreadable answer")
    if data.get("status") != "success":
        err = (data.get("error") or {}).get("error_message") or "the check service refused the request"
        raise RuntimeError(err)
    res = data.get("result")
    if not res:
        return None
    return {k: str(res.get(k) or "") for k in ("artist", "title", "album", "label", "release_date")}


def online_check(src, token, work_dir):
    wav = Path(work_dir) / "copyright_check.wav"
    excerpt_wav(src, wav)
    try:
        return audd_lookup(wav, token)
    finally:
        wav.unlink(missing_ok=True)
