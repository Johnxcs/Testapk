"""Load, validate and create topic definition files (topics/*.json)."""
import json
import re
from pathlib import Path

TOPICS_DIR = Path(__file__).resolve().parent.parent / "topics"

TEMPLATE = {
    "_how_to": "Edit this file freely — it is your video. Any *.json file in topics/ "
               "is a topic; its file name (without .json) is the topic id used by "
               "`python main.py render <id>`. Output goes to output/<id>/.",
    "title": "Your topic in 60 seconds",
    "description": "One line shown in the transcript.",
    "filename": "main.py",
    "language": "python",
    "fps": 30,
    "resolution": [1080, 1920],
    "handle": "",
    "voice": {"engine": "auto"},
    "scenes": [
        {"kind": "title", "title": "Your Topic", "subtitle": "idea -> code -> output",
         "narration": "In this clip we build something small and useful, step by step."},
        {"kind": "code", "code_mode": "replace",
         "code": "# write your code below\n\ndef run():\n    return 42\n",
         "narration": "Every program starts with a small function."},
        {"kind": "code", "code_mode": "append",
         "code": "\n\nrun()\n",
         "narration": "Then we call it, and watch the result appear."},
        {"kind": "run", "narration": "Now let's run it and see the output live.",
         "terminal": "$ python main.py\n42"},
        {"kind": "wait", "narration": "That is the whole idea."},
        {"kind": "title", "title": "Thanks for watching", "subtitle": "stay curious",
         "narration": "Thanks for watching. Stay curious and keep coding."},
    ],
}


def list_topics(topics_dir=TOPICS_DIR):
    d = Path(topics_dir)
    return sorted(p.stem for p in d.glob("*.json"))


def sanitize_id(name):
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_-]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        raise SystemExit("Invalid topic name.")
    return name


def topic_path(topic_id, topics_dir=TOPICS_DIR):
    p = Path(topics_dir) / f"{sanitize_id(topic_id)}.json"
    if not p.is_file():
        raise SystemExit(
            f"Topic '{topic_id}' not found (looked for {p}).\n"
            "Run `python main.py list` to see available topics, or "
            "`python main.py new <name>` to create one."
        )
    return p


def load(topic_id, topics_dir=TOPICS_DIR):
    p = topic_path(topic_id, topics_dir)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"{p} is not valid JSON: {e}")
    if not isinstance(data.get("scenes"), list) or not data["scenes"]:
        raise SystemExit(f"{p}: add a \"scenes\" list with at least one scene.")
    return p, data


def create(topic_id, topics_dir=TOPICS_DIR):
    Path(topics_dir).mkdir(exist_ok=True)
    p = Path(topics_dir) / f"{sanitize_id(topic_id)}.json"
    if p.exists():
        raise SystemExit(f"Topic already exists: {p}")
    p.write_text(json.dumps(TEMPLATE, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return p
