"""Color themes. All colors are hex strings; blend() mixes two of them."""
import copy

THEMES = {
    "dark-plus": {
        "bg": "#1e1e1e",          # editor background
        "chrome": "#3c3c3c",      # window title bar
        "chrome_text": "#cccccc",
        "tabbar": "#252526",
        "tab": "#1e1e1e",
        "tab_text": "#e8e8e8",
        "status": "#007acc",
        "status_text": "#ffffff",
        "gutter": "#858585",      # line numbers
        "gutter_active": "#c6c6c6",
        "inactive": "#6b6b6b",
        "fg": "#d4d4d4",
        "cursor": "#aeafad",
        "accent": "#4ec9b0",
        "dot_saved": "#e5c07b",
        "traffic": ["#ff5f57", "#febc2e", "#28c840"],
        "terminal_bg": "#181818",
        "terminal_header": "#2d2d2d",
        "terminal_tab_text": "#eaeaea",
        "terminal_inactive": "#7d7d7d",
        "prompt": "#23d18b",
        "term_out": "#cccccc",
        "tok": {
            "comment": "#6a9955",
            "control": "#c586c0",
            "keyword": "#569cd6",
            "string": "#ce9178",
            "number": "#b5cea8",
            "function": "#dcdcaa",
            "class": "#4ec9b0",
            "decorator": "#dcdcaa",
            "builtin": "#4ec9b0",
            "operator": "#d4d4d4",
            "punctuation": "#d4d4d4",
            "name": "#9cdcfe",
            "error": "#f44747",
        },
    }
}


def get_theme(name):
    return copy.deepcopy(THEMES.get(name, THEMES["dark-plus"]))


def _num(hexs):
    return int(hexs[1:3], 16), int(hexs[3:5], 16), int(hexs[5:7], 16)


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def blend(hex_a, hex_b, t):
    a, b = _num(hex_a), _num(hex_b)
    return _hex(tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3)))
