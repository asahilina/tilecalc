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

def align_up(v, a=16384):
    return (v + a - 1) & ~(a - 1)

def div_ceil(a, b):
    return (a + b - 1) // b

def pot_ceil(v):
    p = 1
    while p < v:
        p *= 2
    return p

def pot_floor(v):
    p = 1
    while p < v:
        p *= 2
    if p > v:
        p //= 2
    return p

def compute_offsets(w, h, psize, max_lod=1000):
    CACHELINE = 0x80
    offsets = []
    off = 0

    for lod in range(max_lod):
        offsets.append(off)

        # Figure out the tile size
        t = pot_floor(min(64, min(w, h)))

        # Round up to POT if tile size is <64
        if t < 64:
            w = pot_ceil(align_up(w, t))
            h = pot_ceil(align_up(h, t))

        # Dimensions in tiles of current level
        tx = div_ceil(w, t)
        ty = div_ceil(h, t)
        area = tx * ty

        # Initialize offset computation variables
        if lod == 0:
            sarea = area    # area for offset computation purposes
            stx = tx        # X tiles for offset computation purposes
            sty = ty        # Y tiles for offset computation purposes
            addx = False    # X inexact, add padding
            addy = False    # Y inexact, add padding

        # Size of one tile in bytes
        tsize = t * t * psize

        # Now compute size of current level to figure out the next offset
        if t == 64:
            size = sarea        # Base area
            if addx:
                size += sty     # Pad X (with Y tiles) if needed
            if addy:
                size += stx     # Pad y (with X tiles) if needed
            if addx & addy:
                size += 1       # Add the corner tile if both X&Y are padded
        else:            
            size = area         # For tile size < 64, it's just the tile count

        # Increment offset
        off = align_up(off + size * tsize, CACHELINE)
        
        # Advance size accumulators for next LOD
        if t == 64:
            addx |= stx & 1     # Set the X pad flag if we drop a bit
            addy |= sty & 1     # Set the Y pad flag if we drop a bit
            stx = stx >> 1      # Halve X
            sty = sty >> 1      # Halve Y
            sarea >>= 2         # Quarter area

        # Compute next dimensions using the usual OpenGL round down formula
        w = max(1, w >> 1)
        h = max(1, h >> 1)

        if w == h == 1:
            break

    return offsets

for psize, w, h, levels, xoffsets in tests:
    for i, (a,b) in enumerate(zip(compute_offsets(w, h, psize), xoffsets)):
        assert a == b
