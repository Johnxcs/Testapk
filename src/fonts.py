"""Locate a monospace font across platforms. users can drop any .ttf into fonts/."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = PROJECT_ROOT / "fonts"

_CANDIDATES = {
    "linux": [
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/ttf/jetbrains-mono/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/system/fonts/DroidSansMono.ttf",     # Android
        "/system/fonts/CutiveMono.ttf",
    ],
    "darwin": [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/Library/Fonts/Courier New.ttf",
    ],
    "windows": [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/lucon.ttf",
        "C:/Windows/Fonts/cour.ttf",
    ],
}


def find_font(configured=""):
    """Return a path to a monospace font or None."""
    # 1. explicit config / topic override
    if configured:
        p = Path(configured)
        if p.is_file():
            return str(p)
        print(f"WARNING: configured font not found: {configured}")
    # 2. any font dropped into the project fonts/ folder
    if FONTS_DIR.is_dir():
        for pattern in ("*.ttf", "*.otf", "*.ttc"):
            for p in sorted(FONTS_DIR.glob(pattern)):
                return str(p)
    # 3. well-known system fonts
    for cand in _CANDIDATES.get(sys.platform, _CANDIDATES["linux"]):
        p = Path(cand)
        if p.is_file():
            return str(p)
    return None


FONT_HINT = (
    "No monospace font found.\n"
    "  - drop any .ttf/.otf file into the project 'fonts/' folder, or\n"
    "  - set \"font\": \"/path/to/font.ttf\" in config.json.\n"
    "On Debian/Ubuntu:  sudo apt install fonts-dejavu-core"
)
