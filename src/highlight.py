"""Syntax highlighting via pygments. Falls back to one color if pygments is missing."""
try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name
    import pygments.token as T

    HAVE_PYGMENTS = True
except Exception:  # pragma: no cover
    HAVE_PYGMENTS = False

# Ordered: most specific token types first. `ttype in Token.X` is a subtype test.
_CHECK_ORDER = None  # built lazily once themes provide colors


def _check_list():
    global _CHECK_ORDER
    if _CHECK_ORDER is None:
        _CHECK_ORDER = [
            (T.Comment, "comment"),
            (T.Keyword.Control, "control"),
            (T.Keyword.Namespace, "keyword"),
            (T.Keyword.Constant, "keyword"),
            (T.Keyword, "keyword"),
            (T.Literal.String, "string"),
            (T.Literal.Number, "number"),
            (T.Name.Function, "function"),
            (T.Name.Class, "class"),
            (T.Name.Decorator, "decorator"),
            (T.Name.Builtin, "builtin"),
            (T.Operator.Word, "keyword"),
            (T.Operator, "operator"),
            (T.Punctuation, "punctuation"),
            (T.Error, "error"),
            (T.Name, "name"),
        ]
    return _CHECK_ORDER


def color_for(ttype, tok_colors, default):
    if not HAVE_PYGMENTS:
        return default
    for token_type, key in _check_list():
        if ttype in token_type:
            return tok_colors.get(key, default)
    return default


def highlight_lines(code, language, tok_colors, default):
    """Return a list (one per line) of [(text, color), ...] segments."""
    if not HAVE_PYGMENTS:
        return [[(line, default)] for line in code.split("\n")]
    try:
        lexer = get_lexer_by_name(language or "text")
    except Exception:
        lexer = None
    if lexer is None:
        return [[(line, default)] for line in code.split("\n")]
    n_lines = code.count("\n") + 1
    out = [[] for _ in range(n_lines)]
    li = 0
    try:
        tokens = list(lex(code, lexer))
    except Exception:
        return [[(line, default)] for line in code.split("\n")]
    for ttype, val in tokens:
        parts = val.split("\n")
        for j, part in enumerate(parts):
            if j > 0:
                li += 1
            if part:
                out[li].append((part, color_for(ttype, tok_colors, default)))
    return out
