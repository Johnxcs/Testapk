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


def _variant(**over):
    t = copy.deepcopy(THEMES["dark-plus"])
    tok = over.pop("tok", {})
    t.update(over)
    t["tok"].update(tok)
    return t


THEMES["monokai"] = _variant(
    bg="#272822", chrome="#1e1f1c", tabbar="#1e1f1c", tab="#272822", status="#75715e",
    gutter="#90908a", gutter_active="#f8f8f2", fg="#f8f8f2", cursor="#f8f8f0", accent="#a6e22e",
    terminal_bg="#1e1f1c", terminal_header="#2d2e28", prompt="#a6e22e",
    tok={"comment": "#75715e", "control": "#f92672", "keyword": "#f92672", "string": "#e6db74",
         "number": "#ae81ff", "function": "#a6e22e", "class": "#66d9ef", "builtin": "#66d9ef",
         "name": "#f8f8f2", "decorator": "#a6e22e"})
THEMES["dracula"] = _variant(
    bg="#282a36", chrome="#21222c", tabbar="#21222c", tab="#282a36", status="#6272a4",
    gutter="#6272a4", gutter_active="#f8f8f2", fg="#f8f8f2", cursor="#f8f8f2", accent="#bd93f9",
    terminal_bg="#21222c", terminal_header="#343746", prompt="#50fa7b",
    tok={"comment": "#6272a4", "control": "#ff79c6", "keyword": "#ff79c6", "string": "#f1fa8c",
         "number": "#bd93f9", "function": "#50fa7b", "class": "#8be9fd", "builtin": "#8be9fd",
         "name": "#f8f8f2", "decorator": "#50fa7b"})
THEMES["github-dark"] = _variant(
    bg="#0d1117", chrome="#161b22", tabbar="#161b22", tab="#0d1117", status="#1f6feb",
    gutter="#6e7681", gutter_active="#c9d1d9", fg="#c9d1d9", cursor="#58a6ff", accent="#58a6ff",
    terminal_bg="#010409", terminal_header="#161b22", prompt="#3fb950",
    tok={"comment": "#8b949e", "control": "#ff7b72", "keyword": "#ff7b72", "string": "#a5d6ff",
         "number": "#79c0ff", "function": "#d2a8ff", "class": "#ffa657", "builtin": "#79c0ff",
         "name": "#c9d1d9", "decorator": "#d2a8ff"})
THEMES["one-dark"] = _variant(
    bg="#282c34", chrome="#21252b", tabbar="#21252b", tab="#282c34", status="#528bff",
    gutter="#636d83", gutter_active="#abb2bf", fg="#abb2bf", cursor="#528bff", accent="#61afef",
    terminal_bg="#21252b", terminal_header="#2c313a", prompt="#98c379",
    tok={"comment": "#5c6370", "control": "#c678dd", "keyword": "#c678dd", "string": "#98c379",
         "number": "#d19a66", "function": "#61afef", "class": "#e5c07b", "builtin": "#56b6c2",
         "name": "#e06c75", "decorator": "#61afef"})


def get_theme(name):
    return copy.deepcopy(THEMES.get(name, THEMES["dark-plus"]))


def _num(hexs):
    return int(hexs[1:3], 16), int(hexs[3:5], 16), int(hexs[5:7], 16)


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def blend(hex_a, hex_b, t):
    a, b = _num(hex_a), _num(hex_b)
    return _hex(tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3)))
