"""四維八德 — the one logo.

Four chain links woven into a diamond (four directions, everything linked), blue on a light tile.
Every size, from the 16 px icon to the 1024 px artwork, is rendered from this single drawing.

    python make_logo.py <folder>          -> <folder>/logo.svg
"""
import math, sys

S = 1024
C = S / 2

# one link = stadium-shaped ring along the top side of a square (before the 45° turn).  Links are long
# enough that each one passes right through its neighbour: four clean crossings per corner, woven
# over / under / under / over, and every link end comes out past the next link.
D = 200          # distance from centre to the link's centre line
H = 170          # outer height
T = 62           # ring thickness
L = 2 * (D + H) + 30   # outer length
GAP = 20         # visible gap at every crossing
SCALE = 0.80     # glyph size on the tile


def P(x, y, k):
    """Point of link k (k = 0 top, 1 right, 2 bottom, 3 left), turned 45° into a diamond and scaled."""
    a = math.radians(90 * k + 45)
    xr, yr = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    return C + xr * SCALE, C + yr * SCALE


def f(v): return f'{v:.2f}'


def stadium(k, cx, cy, length, height):
    """Closed stadium outline (horizontal in the link's own frame) as an SVG path for link k."""
    r = height / 2
    a = cx - length / 2 + r; b = cx + length / 2 - r
    pts = [P(a, cy - r, k), P(b, cy - r, k), P(b, cy + r, k), P(a, cy + r, k)]
    rr = f(r * SCALE)
    return (f'M{f(pts[0][0])},{f(pts[0][1])} L{f(pts[1][0])},{f(pts[1][1])} '
            f'A{rr},{rr} 0 0 1 {f(pts[2][0])},{f(pts[2][1])} L{f(pts[3][0])},{f(pts[3][1])} '
            f'A{rr},{rr} 0 0 1 {f(pts[0][0])},{f(pts[0][1])} Z')


def ring(k, grow=0.0):
    """Link k as a filled ring (outer stadium minus hole), optionally grown by `grow` for gap masks."""
    outer = stadium(k, 0, -D, L + 2 * grow, H + 2 * grow)
    inner = stadium(k, 0, -D, L - 2 * T + 2 * grow * -1, H - 2 * T - 2 * grow)
    return outer + ' ' + inner


def crossings(k):
    """The four stroke crossings between link k and link k+1, in link k's frame, with who is on top."""
    yt, yb = -D - H / 2 + T / 2, -D + H / 2 - T / 2        # link k's two long strokes
    xl, xr = D - H / 2 + T / 2, D + H / 2 - T / 2          # link k+1's two long strokes
    return [(xl, yt, 'k'), (xr, yt, 'next'), (xl, yb, 'next'), (xr, yb, 'k')]


def square(k, x, y, h):
    pts = [P(x - h, y - h, k), P(x + h, y - h, k), P(x + h, y + h, k), P(x - h, y + h, k)]
    return 'M' + ' L'.join(f'{f(a)},{f(b)}' for a, b in pts) + ' Z'


_uid = [0]


def glyph(fill='url(#linkFill)'):
    """Each link is masked where a neighbour passes over it, so every gap shows the real background."""
    _uid[0] += 1; u = _uid[0]
    out = ['<defs>']
    h = T / 2 + GAP + 3
    for k in range(4):
        nxt, prv = (k + 1) % 4, (k - 1) % 4
        cut = ''
        n = 0
        # crossings with the next link where the next link is on top (link k's own frame)
        for x, y, top in crossings(k):
            if top == 'next':
                cut += (f'<clipPath id="z{u}_{k}_{n}"><path d="{square(k, x, y, h)}"/></clipPath>'
                        f'<g clip-path="url(#z{u}_{k}_{n})"><path d="{ring(nxt, GAP)}" fill="#000" fill-rule="evenodd"/></g>'); n += 1
        # crossings with the previous link where the previous link is on top (previous link's frame)
        for x, y, top in crossings(prv):
            if top == 'k':
                cut += (f'<clipPath id="z{u}_{k}_{n}"><path d="{square(prv, x, y, h)}"/></clipPath>'
                        f'<g clip-path="url(#z{u}_{k}_{n})"><path d="{ring(prv, GAP)}" fill="#000" fill-rule="evenodd"/></g>'); n += 1
        out.append(f'<mask id="m{u}_{k}" x="-0.1" y="-0.1" width="1.2" height="1.2">'
                   f'<rect width="{S}" height="{S}" fill="#fff"/>{cut}</mask>')
    out.append('</defs>')
    for k in range(4):
        out.append(f'<path d="{ring(k)}" fill="{fill}" fill-rule="evenodd" mask="url(#m{u}_{k})"/>')
    return ''.join(out)


DEFS = '''<defs>
  <linearGradient id="tileFill" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset="0.6" stop-color="#F2F6FF"/><stop offset="1" stop-color="#DFE7FF"/>
  </linearGradient>
  <linearGradient id="linkFill" gradientUnits="userSpaceOnUse" x1="250" y1="200" x2="780" y2="840">
    <stop offset="0" stop-color="#38C3FF"/><stop offset="0.45" stop-color="#2D84FF"/><stop offset="1" stop-color="#3D55F5"/>
  </linearGradient>
  <linearGradient id="rim" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#C3D0F7"/>
  </linearGradient>
</defs>'''




def svg(body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{S}" height="{S}" viewBox="0 0 {S} {S}">{DEFS}{body}</svg>'



def logo():
    """Four woven links, bold enough to stay sharp from 16 px to 1024 px."""
    body = (f'<rect x="24" y="24" width="976" height="976" rx="228" fill="url(#tileFill)"/>'
            f'<rect x="27" y="27" width="970" height="970" rx="225" fill="none" stroke="url(#rim)" stroke-width="6"/>'
            + glyph())
    return svg(body)



if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    for name, data in (('logo.svg', logo()),):
        with open(f'{out}/{name}', 'w', encoding='utf-8') as fh: fh.write(data)
    print('ok')
