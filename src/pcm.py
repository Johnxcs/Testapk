"""16-bit PCM helpers. Uses audioop when the Python build has it, pure Python otherwise."""
import array

try:
    import audioop
except ImportError:      # Python 3.13+ on desktop, or a trimmed Android Python
    audioop = None


def to16(data, width):
    if width == 2:
        return data
    if audioop:
        return audioop.lin2lin(data, width, 2)
    if width == 1:
        return array.array("h", [(b - 128) << 8 for b in data]).tobytes()
    if width == 4:
        a = array.array("i")
        a.frombytes(data)
        return array.array("h", [v >> 16 for v in a]).tobytes()
    raise ValueError(f"unsupported sample width {width}")


def tomono(data, channels=2):
    if channels == 1:
        return data
    if audioop and channels == 2:
        return audioop.tomono(data, 2, 0.5, 0.5)
    a = array.array("h")
    a.frombytes(data)
    n = len(a) // channels
    return array.array("h", [sum(a[i * channels:(i + 1) * channels]) // channels for i in range(n)]).tobytes()


def ratecv(data, rate_in, rate_out):
    if rate_in == rate_out:
        return data
    if audioop:
        return audioop.ratecv(data, 2, 1, rate_in, rate_out, None)[0]
    a = array.array("h")
    a.frombytes(data)
    if len(a) < 2:
        return data
    step = rate_in / rate_out
    n_out = int((len(a) - 1) / step)
    out = array.array("h", bytes(2 * n_out))
    for j in range(n_out):
        pos = j * step
        i = int(pos)
        frac = pos - i
        out[j] = int(a[i] * (1 - frac) + a[i + 1] * frac)
    return out.tobytes()


def mul(data, factor):
    if audioop:
        return audioop.mul(data, 2, factor)
    a = array.array("h")
    a.frombytes(data)
    return array.array("h", [max(-32768, min(32767, int(v * factor))) for v in a]).tobytes()


def add(x, y):
    if audioop:
        return audioop.add(x, y, 2)
    a, b = array.array("h"), array.array("h")
    a.frombytes(x)
    b.frombytes(y)
    n = min(len(a), len(b))
    return array.array("h", [max(-32768, min(32767, a[i] + b[i])) for i in range(n)]).tobytes()
