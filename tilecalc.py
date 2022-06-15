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

def dfloor(a, b):
    return max(1, a // b)

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

def cb(v, w=24, h=0):
    s = ""
    for i in range(63, -1, -1):
        bit = 1 << i
        if v < bit and h < bit:
            if i < w:
                s += " "
            continue
        if i & 1:
            f = "\x1b[48;5;23;"
        else:
            f = "\x1b[48;5;233;"
        if v & bit:
            c = "1"
            if h & bit:
                f += "93;1;4"
            else:
                f += "92"
        else:
            c = "0"
            if h & bit:
                f += "95;1;4"
            else:
                f += "33"
        s += f + "m" + c + "\x1b[m"
    return s

def swizzle(a, b):
    v = 0
    for i in range(32):
        if a & (1 << i):
            v |= 1 << (i*2)
        if b & (1 << i):
            v |= 2 << (i*2)
    return v

def clmul(a, b):
    o = 0
    while a:
        if a & 1:
            o |= b
        a >>= 1
        b <<= 1
    return o

total = 0
failed = 0

# Works for 1-2 levels so far
LEVELS = 3
PRINT_ALL = False

for wsize, w, h, levels, xoffsets in tests:
    # Only do RGBA textures for now
    if wsize != 4:
        continue

    total += 1
    fail_levs = 0

    # L0 dimensions are overall dimensions
    l0_w = w
    l0_h = h

    # Compute tile size.
    # TESTED: Rounds *down* to POT! (Otherwise breaks {33..63}x65)
    l0_t = t = potl(min(64, min(l0_w, l0_h)))

    # First level of <64 tile size textures are aligned to POT size
    if t < 64:
        l0_w = pot(aup(l0_w, t))
        l0_h = pot(aup(l0_h, t))

    # Dimensions in tiles
    l0_tx = dceil(l0_w, t)
    l0_ty = dceil(l0_h, t)
    l0_tc = l0_tx * l0_ty

    # The l1 offset is just the l0 tile count * size, no extra padding
    l1_off = aup(l0_tc * t * t * wsize, cacheline)

    # We always get these right
    assert xoffsets[0] == 0
    assert xoffsets[1] == l1_off

    s = f"\x1b[33m[L0]\x1b[m t={t:2} {w:4}x{h:<4} -> {l0_tx:3}*{l0_ty:<3}={l0_tc:5} "
    off = 0

    extra = ex1 = exsh = 0
    pex = ""

    off = l1_off

    lod_w = l0_w
    lod_h = l0_h

    stx = tx = l0_tx
    sty = ty = l0_ty
    stc = l0_tc
    
    tsize = t * t * wsize
    addx = addy = 0

    for i in range(1, len(xoffsets)):
        
        s += f"\x1b[33m[L{i}]\x1b[m"
        
        # Compute LOD using the usual OpenGL round down formula
        lod_w = max(1, lod_w >> 1)
        lod_h = max(1, lod_h >> 1)
        
        lt = t
        
        # Figure out the tile size
        t = potl(min(64, min(lod_w, lod_h)))
        if t < 64:
            # Round up to POT if tile size is <64
            lod_w = pot(aup(lod_w, t))
            lod_h = pot(aup(lod_h, t))

        if lt != t:
            s += f" \x1b[35mt={t:<2d}\x1b[m "
        else:
            s += "      "

        # Dimensions in tiles of current level
        tx = dceil(lod_w, t)
        ty = dceil(lod_h, t)

        # Size in tiles of current level
        size = tx * ty

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
        delta = (xoff - l1_off) // tsize
        s += f"{f}@{off//tsize:5d}{eq}{xoff//tsize:<5d} ({want:3d}) [l1+{delta:<3d}]\x1b[m"

        # Now compute size of current level to figure out the next offset

        if t == 64:
            # dougall's magic
            s += " A "
            stc //= 4
            addx |= stx & 1
            addy |= sty & 1
            stx = dfloor(stx, 2)
            sty = dfloor(sty, 2)
            size = stc
            if addx:
                size += sty
            if addy:
                size += stx
            if addx & addy:
                size += 1
        else:
            # If the tile size is <64, it's already POT aligned so no funny business
            s += " B "
            add = 0

        # Increment offset
        off += size * tsize
        
        # Offsets are also rounded up to a cacheline
        off = aup(off, cacheline)
        
        s += f"({lod_w:4d}x{lod_h:<4d}:{tx:2d}*{ty:<2d}/{stx:2}*{sty:<2}+{add:<2}={size:4d} "

        #if i >= LEVELS:
            #break

        if t == tx == ty == 1:
            break

    if fail_levs:
        failed += 1
    
    if fail_levs or PRINT_ALL:
        print(s)

print(f"Failed {failed}/{total} tests")
