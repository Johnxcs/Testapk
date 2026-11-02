"""Command line interface: list / new / render."""
import argparse
import sys
from pathlib import Path

from . import topics
from .config import load_config


def cmd_list(cfg, args):
    ids = topics.list_topics(args.topics_dir)
    if not ids:
        print("No topics yet. Create one with:  python main.py new my-topic")
        return 0
    print("Available topics (edit any file in topics/ to change the video):\n")
    for tid in ids:
        try:
            p, data = topics.load(tid, args.topics_dir)
            title = data.get("title", "?")
            n = len(data.get("scenes", []))
            print(f"  {tid:<24} {title}  ({n} scenes)")
        except SystemExit:
            print(f"  {tid:<24} <invalid json — fix it before rendering>")
    return 0


def cmd_new(cfg, args):
    p = topics.create(args.name, args.topics_dir)
    print(f"Created {p}\n")
    print("Open it, edit title / narration / code scenes, then render:")
    print(f"  python main.py render {p.stem}")
    return 0


def cmd_render(cfg, args):
    from .video import render_topic

    overrides = {"fps": args.fps, "out": args.out, "no_audio": args.no_audio,
                 "captions": args.captions}
    if args.music:
        overrides["music"] = {"path": args.music, "volume": args.music_volume}
    ids = topics.list_topics(args.topics_dir) if args.topic == "all" else [args.topic]
    if not ids:
        print("No topics found. Add one with:  python main.py new my-topic")
        return 1
    outputs = []
    for tid in ids:
        outputs.append(render_topic(tid, cfg, overrides))
    print("\nDone:")
    for o in outputs:
        print(f"  {o}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="main.py",
        description="Generate coding videos: typewriter code editor + voice-over.",
        epilog="Output per topic: output/<topic-id>/ video.mp4, transcript.txt, audio/, "
               "preview_final_frame.png")
    p.add_argument("--config", default="config.json", help="path to config.json")
    p.add_argument("--topics-dir", default="topics", help="folder with topic JSON files")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list available topics").set_defaults(func=cmd_list)

    sp = sub.add_parser("new", help="create a new editable topic file")
    sp.add_argument("name", help="topic id, e.g. 'javascript-loops'")
    sp.set_defaults(func=cmd_new)

    rp = sub.add_parser("render", help="render a topic (or 'all') to a video")
    rp.add_argument("topic", help="topic id, or 'all'")
    rp.add_argument("--fps", type=int, default=None, help="override fps")
    rp.add_argument("--out", default=None, help="override output directory")
    rp.add_argument("--captions", action="store_true", help="burn narration captions into the video")
    rp.add_argument("--music", default=None, help="background music file (mp3/m4a/wav...)")
    rp.add_argument("--music-volume", type=float, default=0.15, help="music volume 0..1 (default 0.15)")
    rp.add_argument("--no-audio", action="store_true",
                    help="skip TTS (silence + fast, no internet needed)")
    rp.set_defaults(func=cmd_render)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    try:
        return args.func(cfg, args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
