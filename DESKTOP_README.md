# coding-video-maker 🎬

Generate **videos about coding** in the **YouTube Shorts format (vertical 9:16)**:
a fake code editor where your code is typed out character-by-character (typewriter
effect), **with an AI voice-over** narrating every step. No closed captions; the
voice-over carries the explanation.

Everything is driven by small JSON files — one file = one video topic. You can add, edit
or delete topics freely in the `topics/` folder; every generated video goes into its own
folder under `output/<topic-id>/`.

```
┌──────────────────────────────┐
│ ● ● ●  Main.java — Title     │
├──────────────────────────────┤
│ Main.java •                  │   ← tab bar
├──────┬───────────────────────┤
│    1 │ int a = 10;           │   ← the editor fills the whole vertical frame
│    2 │ int b = 3;            │     (1080×1920, no side margins)
│    3 │ ...                   │
│      │                       │
├──────┴───────────────────────┤
│TERMINAL OUTPUT PROBLEM PORTS │   ← terminal panel
│ $ java Main.java             │
├──────────────────────────────┤
│ Main.java   Ln 3, Col 1      │   ← status bar
└──────────────────────────────┘
```

## What you get per topic

```
output/<topic-id>/
├── video.mp4                  ← the final video (code editor + voice-over)
├── transcript.txt             ← scene timings, code shown, and narration text
├── preview_final_frame.png    ← last frame as an image (quick check)
└── audio/
    ├── narration_00.wav ...   ← per-scene voice-over clips
    └── full_track.wav         ← the complete audio track used in the video
```

## Setup

```bash
pip install -r requirements.txt
```

- **ffmpeg**: usually installed via `pip install imageio-ffmpeg` (in requirements).
  If it's missing, install it with your OS package manager — the project prints
  instructions if it can't find it.
- **Voice-over** needs internet (Microsoft Edge voices via `edge-tts`, or Google via
  `gTTS`). No internet? Use `--no-audio` for a silent test render, or set
  `"engine": "pyttsx3"` in `config.json` for an offline (robotic) voice.
- **Font**: any monospace font. If none is found, drop any `.ttf` into the `fonts/`
  folder or set `"font": "/path/to/font.ttf"` in `config.json`.
  (Debian/Ubuntu: `sudo apt install fonts-dejavu-core`)

## Usage

```bash
python main.py list                 # show topics in topics/
python main.py render hello_world   # render one topic
python main.py render all           # render every topic
python main.py new my-topic         # create a new editable topic file
```

Useful flags: `--fps 15` (faster draft renders), `--no-audio` (no TTS / no internet),
`--out DIR` (different output folder).

## ✏️ Changing a topic (your main request)

Everything about a video lives in **one JSON file inside `topics/`**. Open any file there
and change what you like, then `python main.py render <topic-id>` — the output folder
`output/<topic-id>/` is named after the file and is refreshed/kept per topic, so your old
files for other topics stay untouched.

```jsonc
{
  "title": "Python Functions in 60 Seconds",   // big text on title cards
  "description": "...",                         // shown in transcript.txt
  "filename": "main.py",                        // tab/file name in the editor
  "language": "python",                         // syntax highlighting (python, javascript, go, ...)
  "fps": 30,                                    // overrides config.json
  "resolution": [1080, 1920],                   // vertical = YouTube Shorts
  "layout": "shorts",                           // "shorts" or "editor" (classic 16:9)
  "progress_bar": true,                         // scene progress segments on top
  "handle": "@yourhandle",                      // brand text, top-left
  "voice": { "engine": "auto",                  // auto | edge | gtts | pyttsx3
             "name": "fil-PH-BlessicaNeural",   // Filipino accent; alt: "fil-PH-AngeloNeural" (male)
             "lang": "tl" },                    // gTTS fallback: "tl" = Tagalog
  "scenes": [ ... ]                             // the video story, in order
}
```

### Scene types

| kind | what it does |
|---|---|
| `"title"` | Intro/outro card — big centered text typed out |
| `"code"`  | Code editor scene — the code is **typed character by character** while narrating |
| `"run"`   | The program runs: a **TERMINAL panel** at the bottom types the `$ command` and output lines |
| `"wait"`  | Pause — nothing new is typed, cursor blinks (great for explaining what's on screen) |

```jsonc
{
  "kind": "code",
  "code_mode": "append",       // "append" = keep previous code, "replace" = clear editor
  "code": "def greet(name):\n    return f\"Hello, {name}!\"\n",
  "narration": "A function starts with the def keyword..."
}
```

Typing speed is automatic: each scene's code is typed across the narration clip for that
scene, so **code and voice always stay in sync**. No narration and no `wait` duration?
Then typing runs at a natural fixed speed (`base_typing_cps`).

## Global settings (`config.json`)

| setting | default | meaning |
|---|---|---|
| `output_dir` | `"output"` | where render folders are created |
| `fps` / `resolution` | 30 / 1080×1920 | video format — vertical 9:16 for YouTube Shorts |
| `layout` | `"shorts"` | `"shorts"` = vertical full-bleed editor; `"editor"` = classic full-screen 16:9 editor |
| `font_size` | 34 | code text size (mobile readability) |
| `handle` | `""` | e.g. `"@yourhandle"` rendered top-left on every frame |
| `cursor` | `"bar"` | or `"block"` for the classic typewriter block cursor |
| `typing_speed` | 1.0 | multiplier (1.3 = faster typing) |
| `typing_delay` | 0.35 | pause before typing starts in a scene (s) |
| `narration_coverage` | 0.85 | how much of the narration the typing spans |
| `voice` | `fil-PH-AngeloNeural` | Filipino-accent Taglish voice-over (male); female alt: `fil-PH-BlessicaNeural` |

Topic files override all of these individually.

## Troubleshooting

| problem | fix |
|---|---|
| `ffmpeg not found` | `pip install imageio-ffmpeg`, or install ffmpeg (`sudo apt install ffmpeg`, `brew install ffmpeg`) |
| `voice synthesis failed` | no internet → use `--no-audio`, or `"engine": "pyttsx3"` |
| Syntax highlighting off | make sure `pygments` is installed and `"language"` matches (e.g. `javascript`) |
| Windows path issues | run from inside the project folder |

## Ideas to extend

- Typing/keyboard sound effects under the narration
- Post-run result pane showing `Hello, World!` output
- Cursor styles/themes via `theme.py` (it's one dictionary)
- `--start-from-scene N` for quick previews
- Export report-style papers from `transcript.txt`
