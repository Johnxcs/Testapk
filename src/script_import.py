"""Turn pasted notes / a script into scenes (text, bullets, steps, quote, code)."""
import re

BULLET = re.compile(r"^\s*[-*\u2022]\s+(.*)$")
NUMBER = re.compile(r"^\s*\d+[.)]\s+(.*)$")


def _split_sentences(text, max_chars):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, cur = [], ""
    for p in parts:
        if cur and len(cur) + 1 + len(p) > max_chars:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def _blocks(text):
    blocks, cur, code, in_code, lang = [], [], [], False, ""

    def flush():
        if cur:
            blocks.append(("para", list(cur)))
            cur.clear()

    for line in text.replace("\r", "").split("\n"):
        if line.strip().startswith("```"):
            if in_code:
                blocks.append(("code", lang, "\n".join(code)))
                code, in_code = [], False
            else:
                flush()
                in_code, lang = True, line.strip()[3:].strip()
            continue
        if in_code:
            code.append(line)
        elif not line.strip():
            flush()
        else:
            cur.append(line)
    flush()
    if in_code and code:
        blocks.append(("code", lang, "\n".join(code)))
    return blocks


def _say(*parts):
    return ". ".join(p.strip().rstrip(".:") for p in parts if p and str(p).strip()) + "."


def script_to_scenes(text, add_title=True, max_chars=230):
    text = (text or "").strip()
    if not text:
        return []
    blocks = _blocks(text)
    scenes, heading = [], ""

    # the first short plain line becomes the title card
    if add_title and blocks and blocks[0][0] == "para":
        first = blocks[0][1]
        if len(first) == 1 and len(first[0]) <= 60 and not BULLET.match(first[0]) \
                and not NUMBER.match(first[0]) and not first[0].lstrip().startswith(("#", ">")):
            title = first[0].strip()
            scenes.append({"kind": "title", "title": title, "subtitle": "", "narration": title})
            blocks = blocks[1:]
        elif first[0].lstrip().startswith("# ") and len(first) == 1:
            title = first[0].lstrip("# ").strip()
            scenes.append({"kind": "title", "title": title, "subtitle": "", "narration": title})
            blocks = blocks[1:]

    for blk in blocks:
        if blk[0] == "code":
            scenes.append({"kind": "code", "code_mode": "append",
                           "code": blk[2].rstrip("\n") + "\n", "narration": ""})
            continue
        lines = [l for l in blk[1] if l.strip()]
        if not lines:
            continue
        if lines[0].lstrip().startswith("#"):
            heading = lines[0].lstrip("# ").strip()
            lines = lines[1:]
            if not lines:
                continue
        if all(l.lstrip().startswith(">") for l in lines):
            body = [l.lstrip()[1:].strip() for l in lines]
            author = ""
            if len(body) > 1 and re.match(r"^(\u2014|--|-)\s*\S", body[-1]):
                author = re.sub(r"^(\u2014|--|-)\s*", "", body.pop())
            q = " ".join(body)
            scenes.append({"kind": "quote", "text": q, "author": author, "narration": q})
            heading = ""
            continue
        # optional lead-in line before a list ("Steps:")
        lead = ""
        rest = lines
        if len(lines) > 1 and not BULLET.match(lines[0]) and not NUMBER.match(lines[0]) \
                and all(BULLET.match(l) or NUMBER.match(l) for l in lines[1:]):
            lead, rest = lines[0].strip().rstrip(":"), lines[1:]
        if rest and all(BULLET.match(l) for l in rest):
            items = [BULLET.match(l).group(1).strip() for l in rest]
            h = lead or heading
            scenes.append({"kind": "bullets", "heading": h, "items": items,
                           "narration": _say(h, *items)})
            heading = ""
            continue
        if rest and all(NUMBER.match(l) for l in rest):
            items = [NUMBER.match(l).group(1).strip() for l in rest]
            h = lead or heading
            scenes.append({"kind": "steps", "heading": h, "items": items,
                           "narration": _say(h, *[f"Step {i + 1}: {t}" for i, t in enumerate(items)])})
            heading = ""
            continue
        body = " ".join(l.strip() for l in lines)
        for n, chunk in enumerate(_split_sentences(body, max_chars)):
            sc = {"kind": "text", "heading": heading if n == 0 else "", "body": chunk,
                  "narration": _say(heading, chunk) if (n == 0 and heading) else chunk}
            if not sc["heading"]:
                del sc["heading"]
            scenes.append(sc)
        heading = ""
    if add_title and scenes:
        scenes.append({"kind": "title", "title": "Thanks for watching", "subtitle": "",
                       "narration": "Thanks for watching!"})
    return scenes
