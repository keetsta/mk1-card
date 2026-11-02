"""Turn the card's lettering into polygons (front-view millimetres) for build_pcb.py.

Inter Tight (SIL OFL) is instanced at the weights used in the approved render, kerned from its GPOS
table and tracked like the canvas render (letterSpacing in mm). Output: text.json next to this file.

python make_text.py <InterTight[wght].ttf>
"""
import json, math, os, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.basePen import BasePen

HERE = os.path.dirname(os.path.abspath(__file__))
W = 85.6

# layer, text, weight, size mm, x, baseline y, tracking mm, align, mirror (back side, given in back-view x)
# Silk ink closes gaps under ~0.15 mm and drops strokes under 0.15 mm. Small text stays at weight >= 500 and
# 2 mm (horizontal strokes ~0.18 mm) and is tracked out so neighbouring letters keep >= 0.17 mm between them;
# Inter Tight at zero tracking leaves 0.05..0.15 mm there. The big name is tracked so tight that every pair
# after the k fuses outright: at -1.1 some pairs fused and others kept 0.03..0.13 mm hairlines that print ragged.
ITEMS = [
    ('F.SilkS', 'keetsta', 800, 23.5, 2.6, 55.6, -1.3, 'left', False),
    ('F.SilkS', 'keetsta.me', 450, 2.1, 10.6, 9.6, 0.12, 'left', False),
    ('B.SilkS', 'shell over usb-c', 500, 2.0, 6.0, 41.4, 0.12, 'left', True),
    ('B.SilkS', 'keetsta.me/mk1', 700, 3.4, 6.0, 45.6, 0.08, 'left', True),
    ('B.SilkS', 'software engineer', 600, 2.0, 6.0, 49.4, 0.12, 'left', True),
    ('B.SilkS', 'keetsta@icloud.com', 500, 2.0, 6.0, 52.3, 0.12, 'left', True),
    ('B.SilkS', 't.me/keetsta', 500, 2.0, 30.0, 49.4, 0.12, 'left', True),
    ('B.SilkS', 'github.com/keetsta', 500, 2.0, 30.0, 52.3, 0.12, 'left', True),
    ('B.SilkS', 'swclk', 500, 1.8, W - 18.6, 52.3, 0.08, 'center', True),
    ('B.SilkS', 'swdio', 500, 1.8, W - 24.1, 52.3, 0.08, 'center', True),
    ('B.SilkS', 'gnd', 500, 1.8, W - 29.6, 52.3, 0.08, 'center', True),
    ('B.SilkS', 'U7', 600, 1.8, W - 37.0, 37.9, 0.08, 'center', True),
]


class FlatPen(BasePen):
    def __init__(self, glyphset, steps=10):
        super().__init__(glyphset)
        self.contours, self.cur, self.steps = [], [], steps

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                             mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.cur.append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
                             mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def pair_kerning(font):
    """{(left glyph, right glyph): x advance adjustment} from the GPOS 'kern' feature."""
    gpos = font['GPOS'].table
    lookups = set()
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == 'kern':
            lookups.update(fr.Feature.LookupListIndex)
    order = font.getGlyphOrder()
    kern = {}

    def subtables(lk):
        for st in lk.SubTable:
            if lk.LookupType == 9:
                yield st.ExtSubTable
            else:
                yield st

    for li in sorted(lookups):
        lk = gpos.LookupList.Lookup[li]
        for st in subtables(lk):
            if getattr(st, 'LookupType', 2) != 2 and lk.LookupType != 2:
                continue
            cov = st.Coverage.glyphs
            if st.Format == 1:
                for g1, ps in zip(cov, st.PairSet):
                    for pvr in ps.PairValueRecord:
                        v = getattr(pvr.Value1, 'XAdvance', 0) if pvr.Value1 else 0
                        kern.setdefault((g1, pvr.SecondGlyph), v)
            elif st.Format == 2:
                c1 = st.ClassDef1.classDefs if st.ClassDef1 else {}
                c2 = st.ClassDef2.classDefs if st.ClassDef2 else {}
                st._c1, st._c2 = c1, c2
                kern.setdefault(('__class__', id(st)), st)
    return kern


def kern_value(kern, g1, g2):
    v = kern.get((g1, g2))
    if v is not None:
        return v
    for key, st in kern.items():
        if key[0] != '__class__':
            continue
        if g1 not in st.Coverage.glyphs:
            continue
        a = st._c1.get(g1, 0)
        b = st._c2.get(g2, 0)
        rec = st.Class1Record[a].Class2Record[b]
        val = getattr(rec.Value1, 'XAdvance', 0) if rec.Value1 else 0
        if val:
            return val
    return 0


def area(c):
    return 0.5 * sum(c[i][0] * c[(i + 1) % len(c)][1] - c[(i + 1) % len(c)][0] * c[i][1] for i in range(len(c)))


def inside(pt, poly):
    x, y = pt
    res = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            res = not res
    return res


def render(fontpath, text, weight, size, x0, base, track, align):
    font = TTFont(fontpath)
    font = instancer.instantiateVariableFont(font, {'wght': weight})
    upm = font['head'].unitsPerEm
    s = size / upm
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    hmtx = font['hmtx']
    kern = pair_kerning(font)
    names = [cmap[ord(ch)] for ch in text]
    pens, pen_x = [], 0.0
    for i, g in enumerate(names):
        pens.append(pen_x)
        adv = hmtx[g][0] * s
        if i + 1 < len(names):
            adv += kern_value(kern, g, names[i + 1]) * s
        pen_x += adv + track
    width = pen_x - track
    if align == 'center':
        x0 -= width / 2
    polys = []
    for g, px in zip(names, pens):
        pen = FlatPen(gs, steps=12 if size > 5 else 6)
        gs[g].draw(pen)
        contours = [[(x0 + px + x * s, base - y * s) for x, y in c] for c in pen.contours]
        # TrueType fills by the non-zero rule: outer contours run clockwise, counters run the other way,
        # and a variable font keeps overlapping parts (stem and bar of a "t") as separate contours.
        # So: union of one direction minus union of the other. With y flipped, outers get area > 0.
        polys.append({'add': [c for c in contours if area(c) > 0],
                      'sub': [c for c in contours if area(c) < 0]})
    return polys, width


def main():
    fontpath = sys.argv[1]
    out = []
    for layer, text, weight, size, x, base, track, align, mirror in ITEMS:
        polys, width = render(fontpath, text, weight, size, x, base, track, align)
        if mirror:
            polys = [{k: [[(W - px, py) for px, py in c] for c in p[k]] for k in ('add', 'sub')} for p in polys]
        out.append({'layer': layer, 'text': text, 'polys': polys})
        print(f'{text!r}: {len(polys)} shapes, width {width:.2f} mm')
    with open(os.path.join(HERE, 'text.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f)


if __name__ == '__main__':
    main()
