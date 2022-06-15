import sys

PIPE_FORMAT_R8G8B8A8_UNORM = 4
PIPE_FORMAT_R8_UNORM = 1

testfiles = [
    "all.txt"
]
d = "".join(open(f).read() for f in testfiles)
d = d.replace("PIPE_FORMAT_R8G8B8A8_UNORM", str(PIPE_FORMAT_R8G8B8A8_UNORM))
d = d.replace("PIPE_FORMAT_R8_UNORM", str(PIPE_FORMAT_R8_UNORM))
d = d.replace("{", "[").replace("}", "]")
tests = eval("[" + d + "]")

def aup(v, a=16384):
    return (v + a - 1) & ~(a - 1)

def dceil(a, b):
    return (a + b - 1) // b

def pot(v):
    p = 1
    while p < v:
        p *= 2
    return p

def potl(v):
    p = 1
    while p < v:
        p *= 2
    if p > v:
        p //= 2
    return p

def log2(v):
    i = 0
    while (1<<i) < v:
        i += 1
    return i

cacheline = 0x80

t_fail = 0
t_fail_lev = 0

log = ""

def p(s):
    global log
    log += s + "\n"

total = 0
failed = 0

LEVELS = 100
PRINT_ALL = True

for wsize, w, h, levels, xoffsets in tests:
    total += 1
    fail_levs = 0

    lod_w = w
    lod_h = h

    off = 0
    lt = None

    s = f"[{w:4}x{h:<4}] "

    for i in range(len(xoffsets)):
        s += f"\x1b[33m[L{i}]\x1b[m"

        # Figure out the tile size
        t = potl(min(64, min(lod_w, lod_h)))

        # Round up to POT if tile size is <64
        if t < 64:
            lod_w = pot(aup(lod_w, t))
            lod_h = pot(aup(lod_h, t))

        if lt != t:
            s += f" \x1b[35mt={t:<2d}\x1b[m "
        else:
            s += "      "

        lt = t

        # Dimensions in tiles of current level
        tx = dceil(lod_w, t)
        ty = dceil(lod_h, t)
        area = tx * ty

        # Initialize offset computation variables
        if i == 0:
            sarea = area    # area for offset computation purposes
            stx = tx        # X tiles for offset computation purposes
            sty = ty        # Y tiles for offset computation purposes
            addx = False    # X inexact, add padding
            addy = False    # Y inexact, add padding

        # Size of one tile in bytes
        tsize = t * t * wsize

        # Expected offset/size
        xoff = xoffsets[i]
        xsize = 1 if i == (len(xoffsets) - 1) or tx == ty == t == 1 else xoffsets[i+1] - xoff

        assert (xoff - off) % tsize == 0

        # How far off we are in tiles
        want = (xoff - off) // tsize

        if want != 0:
            fail_levs += 1

        eq = "==" if off == xoff else "!="
        f = "\x1b[32m" if want==0 else "\x1b[31m"
        s += f"{f}@{off//tsize:5d}{eq}{xoff//tsize:<5d} ({want:3d}) \x1b[m"

        # Now compute size of current level to figure out the next offset
        if t == 64:
            # (dougall's magic)
            extra = 0
            if addx:
                extra += sty    # Pad X (with Y tiles) if needed
            if addy:
                extra += stx    # Pad y (with X tiles) if needed
            if addx & addy:
                extra += 1      # Add the corner tile if both X&Y are padded

            # Compute size as shifted down area + extra padding
            size = sarea + extra
        else:
            # For tile size < 64, it's just the tile count
            size = area

        # Increment offset
        off += size * tsize

        # Offsets are also rounded up to a cacheline
        off = aup(off, cacheline)

        if t == 64:
            s += f"({lod_w:4d}x{lod_h:<4d}:{tx:3d}*{ty:<3d}/{stx:3}*{sty:<3}+{extra:<2}={size:4d} "
        else:
            s += f"({lod_w:4d}x{lod_h:<4d}:{tx:3d}*{ty:<3d}={size:4d}) "

        # Advance size accumulators for next LOD
        if t == 64:
            addx |= stx & 1     # Set the X pad flag if we drop a bit
            addy |= sty & 1     # Set the Y pad flag if we drop a bit
            stx = stx >> 1      # Halve X
            sty = sty >> 1      # Halve Y
            sarea >>= 2         # Quarter area

        # Compute LOD using the usual OpenGL round down formula
        lod_w = max(1, lod_w >> 1)
        lod_h = max(1, lod_h >> 1)

        if i >= LEVELS:
            break

        if t == tx == ty == 1:
            break

    if fail_levs:
        failed += 1

    if fail_levs or PRINT_ALL:
        print(s)

print(f"Failed {failed}/{total} tests")
