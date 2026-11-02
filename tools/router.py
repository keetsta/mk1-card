"""Small grid router for the MK-1 card (KiCad Python, numpy + PIL).

Routes on F.Cu, In1.Cu and B.Cu with through vias; In2.Cu is the ground plane and is never used for
tracks. Obstacles are rasterised from the board with the clearance already added, so a free cell is a
legal place for a track centre (or a via centre in the via maps).
"""
import heapq, math
import numpy as np
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM
from PIL import Image, ImageDraw

OX, OY = 100.0, 100.0
RES = 0.05                     # mm per cell
X0, Y0, X1, Y1 = -0.5, -0.5, 86.1, 54.5
NX, NY = int(round((X1 - X0) / RES)), int(round((Y1 - Y0) / RES))
LAYERS = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.B_Cu]
LNAME = {pcbnew.F_Cu: 'F', pcbnew.In1_Cu: 'In1', pcbnew.B_Cu: 'B'}
CLR = 0.17                     # router clearance: the 0.15 net class rule plus room for the grid
MARGIN = 0.0                   # cell centres are tested exactly, CLR already carries the slack
HOLE_CLR = 0.33                # copper of other nets around plated and non-plated component holes
EDGE = 0.35                    # copper to board edge
FREE, CONFLICT = -1, -2


def cell(x, y):
    return int(round((y - Y0) / RES)), int(round((x - X0) / RES))


def _chain_cells(chain):
    """SHAPE_LINE_CHAIN -> list of (x, y) in cell units, cell centres sit on integers."""
    return [((ToMM(chain.CPoint(j).x) - OX - X0) / RES, (ToMM(chain.CPoint(j).y) - OY - Y0) / RES)
            for j in range(chain.PointCount())]


def _inside(pts, bx0, by0, bx1, by1):
    """Even-odd test of every cell centre in the box against a closed polygon."""
    py, px = np.mgrid[by0:by1, bx0:bx1].astype(np.float64)
    inside = np.zeros(px.shape, dtype=bool)
    n = len(pts)
    for k in range(n):
        x1, y1 = pts[k]
        x2, y2 = pts[(k + 1) % n]
        if y1 == y2:
            continue
        cond = (y1 > py) != (y2 > py)
        xint = (x2 - x1) * (py - y1) / (y2 - y1) + x1
        inside ^= cond & (px < xint)
    return inside


def circle_poly(cx, cy, r, n=32):
    """Absolute-mm circle as a SHAPE_POLY_SET (cx, cy in board mm)."""
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for i in range(n):
        a = 2 * math.pi * i / n
        ps.Append(FromMM(cx + r * math.cos(a)), FromMM(cy + r * math.sin(a)))
    return ps


def clusters(items):
    """Group same-net copper items into connected clusters (geometry based)."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    shapes = []
    for it in items:
        per = {}
        for l in LAYERS + [pcbnew.In2_Cu]:
            if not it.IsOnLayer(l):
                continue
            if it.GetClass() == 'ZONE':
                per[l] = it.GetFilledPolysList(l)
            else:
                per[l] = it.GetEffectiveShape(l)
        shapes.append(per)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if find(i) == find(j):
                continue
            for l, si in shapes[i].items():
                sj = shapes[j].get(l)
                if sj is None:
                    continue
                if items[i].GetClass() == 'ZONE' and items[j].GetClass() == 'ZONE':
                    hit = si.Collide(sj.Outline(0), 0) if sj.OutlineCount() else False
                elif items[j].GetClass() == 'ZONE':
                    hit = sj.Collide(si, 0)
                else:
                    hit = si.Collide(sj, 0)
                if hit:
                    parent[find(i)] = find(j)
                    break
    groups = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(items[i])
    return list(groups.values())


def pos(iy, ix):
    return X0 + ix * RES, Y0 + iy * RES


class Maps:
    """Per-layer net-occupancy grids inflated for one track width or for vias."""

    def __init__(self, board, inflate, hole_inflate=None):
        self.board = board
        self.inflate = inflate
        self.occ = {l: np.full((NY, NX), FREE, dtype=np.int32) for l in LAYERS}
        self.holes = np.full((NY, NX), FREE, dtype=np.int32) if hole_inflate is not None else None
        self.hole_inflate = hole_inflate

    def _stamp(self, arr, ps, net):
        """Mark the cells whose centres lie inside the polygon set (holes respected)."""
        for i in range(ps.OutlineCount()):
            outer = _chain_cells(ps.Outline(i))
            if len(outer) < 3:
                continue
            xs = [p[0] for p in outer]; ys = [p[1] for p in outer]
            bx0, by0 = max(0, int(math.floor(min(xs)))), max(0, int(math.floor(min(ys))))
            bx1, by1 = min(NX, int(math.ceil(max(xs))) + 1), min(NY, int(math.ceil(max(ys))) + 1)
            if bx1 <= bx0 or by1 <= by0:
                continue
            m = _inside(outer, bx0, by0, bx1, by1)
            for h in range(ps.HoleCount(i)):
                hole = _chain_cells(ps.Hole(i, h))
                if len(hole) >= 3:
                    m &= ~_inside(hole, bx0, by0, bx1, by1)
            if not m.any():
                continue
            sub = arr[by0:by1, bx0:bx1]
            cur = sub[m]
            sub[m] = np.where((cur == FREE) | (cur == net), net, CONFLICT)

    def add_item(self, item, layers=None):
        net = item.GetNetCode() if hasattr(item, 'GetNetCode') else 0
        if net == 0:
            net = -3          # unconnected copper: blocks everybody
        extra = 0.0
        if item.GetClass() == 'PAD' and item.HasHole():
            extra = max(0.0, HOLE_CLR - CLR)   # JLC keeps component holes 0.28..0.35 mm from copper
        infl = FromMM(self.inflate + extra)
        for l in (layers or LAYERS):
            if not item.IsOnLayer(l):
                continue
            ps = pcbnew.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(ps, l, infl, FromMM(0.005), pcbnew.ERROR_OUTSIDE)
            self._stamp(self.occ[l], ps, net)
        if self.holes is not None:
            self.add_hole(item)

    def add_hole(self, item):
        r = 0
        if item.GetClass() == 'PCB_VIA':
            r = item.GetDrillValue() / 2e6
            c = item.GetPosition()
        elif item.GetClass() == 'PAD' and item.HasHole():
            ds = item.GetDrillSize()
            r = max(ds.x, ds.y) / 2e6
            c = item.GetPosition()
        else:
            return
        ps = pcbnew.SHAPE_POLY_SET()
        if item.GetClass() == 'PAD':
            item.TransformHoleToPolygon(ps, FromMM(self.hole_inflate), FromMM(0.005), pcbnew.ERROR_OUTSIDE)
        else:
            ps = circle_poly(ToMM(c.x), ToMM(c.y), r + self.hole_inflate)
        self._stamp(self.holes, ps, -3)

    def add_poly(self, layer, ps, net):
        ps2 = pcbnew.SHAPE_POLY_SET(ps)
        ps2.Inflate(FromMM(self.inflate), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, FromMM(0.005))
        self._stamp(self.occ[layer], ps2, net)

    def block(self, layer, ps):
        self._stamp(self.occ[layer], ps, -3)


def edge_mask():
    """Cells closer than EDGE to the card outline (rounded rectangle 85.6 x 54, r 2.6)."""
    ys, xs = np.mgrid[0:NY, 0:NX]
    x = X0 + xs * RES; y = Y0 + ys * RES
    W, H, R = 85.6, 54.0, 2.6
    cx = np.clip(x, R, W - R); cy = np.clip(y, R, H - R)
    inside_core = (x >= 0) & (x <= W) & (y >= 0) & (y <= H)
    d_corner = R - np.hypot(x - cx, y - cy)
    d_edge = np.minimum.reduce([x, W - x, y, H - y])
    in_corner = (np.abs(x - cx) > 1e-9) & (np.abs(y - cy) > 1e-9)
    dist = np.where(in_corner, d_corner, d_edge)
    return ~inside_core | (dist < EDGE)


class Router:
    def __init__(self, board, net_of, widths, via=(0.45, 0.25), log=print):
        self.board = board
        self.net_of = net_of          # name -> NETINFO_ITEM
        self.log = log
        self.via_d, self.via_drill = via
        self.widths = sorted(set(widths))
        self.track_maps = {w: Maps(board, CLR + w / 2 + MARGIN) for w in self.widths}
        self.via_maps = Maps(board, CLR + self.via_d / 2 + MARGIN, hole_inflate=0.25 + self.via_drill / 2 + MARGIN)
        self.edge = edge_mask()
        self.keepout = {l: np.zeros((NY, NX), dtype=bool) for l in LAYERS}
        self.via_keepout = np.zeros((NY, NX), dtype=bool)
        self.cost = {pcbnew.F_Cu: 3.0, pcbnew.In1_Cu: 1.0, pcbnew.B_Cu: 1.25}
        self.via_cost = 1.6           # mm of track
        self.rebuild()

    # ------------------------------------------------------------------ obstacles
    def rebuild(self):
        b = self.board
        items = []
        for fp in b.GetFootprints():
            items += list(fp.Pads())
        items += list(b.GetTracks())
        for m in list(self.track_maps.values()) + [self.via_maps]:
            for l in LAYERS:
                m.occ[l].fill(FREE)
            if m.holes is not None:
                m.holes.fill(FREE)
            for it in items:
                m.add_item(it)
        for z in b.Zones():
            if z.GetIsRuleArea():
                continue
            if z.GetZoneName().startswith('core'):
                for l in LAYERS:
                    if z.IsOnLayer(l):
                        for m in list(self.track_maps.values()) + [self.via_maps]:
                            m.add_poly(l, z.GetFilledPolysList(l), z.GetNetCode())

    def add_items(self, items):
        for it in items:
            for m in list(self.track_maps.values()) + [self.via_maps]:
                m.add_item(it)

    def keep_out(self, layer, x0, y0, x1, y1):
        a = cell(x0, y0); b = cell(x1, y1)
        self.keepout[layer][a[0]:b[0], a[1]:b[1]] = True

    def keep_out_vias(self, x0, y0, x1, y1):
        a = cell(x0, y0); b = cell(x1, y1)
        self.via_keepout[a[0]:b[0], a[1]:b[1]] = True

    # ------------------------------------------------------------------ search
    def route(self, net, sources, targets, width, window, allow_front=None, block=None, soft=None,
              max_nodes=2_500_000):
        """A* from any source cell to any target cell. sources/targets: {layer: bool mask}.
        block: cells a layer may not use; soft: cells a layer may use at four times the cost."""
        nc = self.net_of[net].GetNetCode()
        tm = self.track_maps[width]
        vm = self.via_maps
        (wy0, wx0), (wy1, wx1) = cell(window[0], window[1]), cell(window[2], window[3])
        wy0, wx0 = max(wy0, 0), max(wx0, 0)
        wy1, wx1 = min(wy1, NY - 1), min(wx1, NX - 1)
        sl = (slice(wy0, wy1 + 1), slice(wx0, wx1 + 1))
        free = {}
        for l in LAYERS:
            o = tm.occ[l][sl]
            f = ((o == FREE) | (o == nc)) & ~self.edge[sl] & ~self.keepout[l][sl]
            if l == pcbnew.F_Cu:
                f &= allow_front[sl] if allow_front is not None else False
            if block and l in block:
                f &= ~block[l][sl]
            free[l] = f
        vfree = np.ones_like(free[LAYERS[0]])
        for l in LAYERS:
            o = vm.occ[l][sl]
            vfree &= (o == FREE) | (o == nc)
        vfree &= (vm.holes[sl] == FREE) & ~self.edge[sl] & ~self.via_keepout[sl]
        src = {l: sources[l][sl] & free[l] if l in sources else None for l in LAYERS}
        dst = {l: targets[l][sl] & free[l] if l in targets else None for l in LAYERS}
        # source/target cells may sit inside a pad where the inflated pad itself is "own net": fine.
        tgt_pts = []
        for li, l in enumerate(LAYERS):
            if dst[l] is not None:
                ys, xs = np.nonzero(dst[l])
                tgt_pts += list(zip(ys.tolist(), xs.tolist()))
        if not tgt_pts:
            return None
        ty = np.array([p[0] for p in tgt_pts]); tx = np.array([p[1] for p in tgt_pts])
        tminy, tmaxy, tminx, tmaxx = ty.min(), ty.max(), tx.min(), tx.max()

        def h(y, x):
            dy = max(tminy - y, 0, y - tmaxy); dx = max(tminx - x, 0, x - tmaxx)
            return (max(dx, dy) + 0.414 * min(dx, dy)) * RES

        H, Wd = wy1 - wy0 + 1, wx1 - wx0 + 1
        nl = len(LAYERS)
        g = np.full((nl, H, Wd), np.inf, dtype=np.float32)
        prev = np.full((nl, H, Wd), -1, dtype=np.int64)
        isdst = np.zeros((nl, H, Wd), dtype=bool)
        freea = np.stack([free[l] for l in LAYERS])
        for li, l in enumerate(LAYERS):
            if dst[l] is not None:
                isdst[li] = dst[l]
        heap = []
        for li, l in enumerate(LAYERS):
            if src[l] is None:
                continue
            ys, xs = np.nonzero(src[l])
            for y, x in zip(ys.tolist(), xs.tolist()):
                g[li, y, x] = 0.0
                heapq.heappush(heap, (h(y, x), 0.0, li, y, x))
        steps = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                 (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
        cm = np.empty((nl, H, Wd), dtype=np.float32)
        for li, l in enumerate(LAYERS):
            cm[li] = self.cost[l] * RES
            if soft and l in soft:
                cm[li][soft[l][sl]] *= 4.0
        n = 0
        end = None
        while heap:
            f, gc, li, y, x = heapq.heappop(heap)
            if gc > g[li, y, x]:
                continue
            if isdst[li, y, x]:
                end = (li, y, x)
                break
            n += 1
            if n > max_nodes:
                break
            for dy, dx, c in steps:
                yy, xx = y + dy, x + dx
                if yy < 0 or xx < 0 or yy >= H or xx >= Wd or not freea[li, yy, xx]:
                    continue
                if dy and dx and not (freea[li, y, xx] and freea[li, yy, x]):
                    continue
                ng = gc + c * float(cm[li, yy, xx])
                if ng < g[li, yy, xx]:
                    g[li, yy, xx] = ng
                    prev[li, yy, xx] = (li * H + y) * Wd + x
                    heapq.heappush(heap, (ng + h(yy, xx), ng, li, yy, xx))
            if vfree[y, x]:
                for lj in range(nl):
                    if lj == li or not freea[lj, y, x]:
                        continue
                    ng = gc + self.via_cost
                    if ng < g[lj, y, x]:
                        g[lj, y, x] = ng
                        prev[lj, y, x] = (li * H + y) * Wd + x
                        heapq.heappush(heap, (ng + h(y, x), ng, lj, y, x))
        if end is None:
            return None
        path = []
        cur = end
        while True:
            li, y, x = cur
            path.append((LAYERS[li], y + wy0, x + wx0))
            p = prev[li, y, x]
            if p < 0:
                break
            pl, rem = divmod(int(p), H * Wd)
            py, px = divmod(rem, Wd)
            cur = (pl, py, px)
        path.reverse()
        return path

    # ------------------------------------------------------------------ geometry
    def _segment_free(self, net, layer, a, b, width):
        """True if the straight centre line a->b (cells) stays on free cells for this net."""
        nc = self.net_of[net].GetNetCode()
        occ = self.track_maps[width].occ[layer]
        (y0, x0), (y1, x1) = a, b
        k = 2 * max(abs(y1 - y0), abs(x1 - x0))
        for i in range(k + 1):
            yy = int(round(y0 + (y1 - y0) * i / max(k, 1)))
            xx = int(round(x0 + (x1 - x0) * i / max(k, 1)))
            o = occ[yy, xx]
            if (o != FREE and o != nc) or self.edge[yy, xx] or self.keepout[layer][yy, xx]:
                return False
        return True

    def simplify(self, net, path, width):
        """Split by layer, keep corners, then pull strings along 0/45/90 degree lines."""
        runs = []
        cur = [path[0]]
        for p in path[1:]:
            if p[0] != cur[-1][0]:
                runs.append(cur); cur = [p]
            else:
                cur.append(p)
        runs.append(cur)
        out = []
        for run in runs:
            layer = run[0][0]
            pts = [(y, x) for _, y, x in run]
            keep = [pts[0]]
            i = 0
            while i < len(pts) - 1:
                j = len(pts) - 1
                while j > i + 1:
                    dy, dx = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
                    octo = dy == 0 or dx == 0 or abs(dy) == abs(dx)
                    if octo and self._segment_free(net, layer, pts[i], pts[j], width):
                        break
                    j -= 1
                keep.append(pts[j])
                i = j
            out.append((layer, keep))
        return out

    def split_at(self, net, layer, x, y):
        """If (x, y) lies inside an existing track of the net (not at its end), cut that track there,
        so a later stub cleanup can never take away the part that leads to the junction."""
        nc = self.net_of[net].GetNetCode()
        p = VECTOR2I(FromMM(OX + x), FromMM(OY + y))
        for t in list(self.board.GetTracks()):
            if t.GetClass() != 'PCB_TRACK' or t.GetNetCode() != nc or t.GetLayer() != layer:
                continue
            s, e = t.GetStart(), t.GetEnd()
            if not t.HitTest(p, 0):
                continue
            if math.hypot(s.x - p.x, s.y - p.y) < FromMM(0.05) or math.hypot(e.x - p.x, e.y - p.y) < FromMM(0.05):
                continue
            # project onto the centre line so both halves stay collinear
            dx, dy = e.x - s.x, e.y - s.y
            u = ((p.x - s.x) * dx + (p.y - s.y) * dy) / float(dx * dx + dy * dy)
            q = VECTOR2I(int(s.x + u * dx), int(s.y + u * dy))
            t2 = pcbnew.PCB_TRACK(self.board)
            t2.SetStart(q); t2.SetEnd(e); t2.SetWidth(t.GetWidth()); t2.SetLayer(layer); t2.SetNet(t.GetNet())
            t.SetEnd(q)
            self.board.Add(t2)
            return (ToMM(q.x) - OX, ToMM(q.y) - OY)
        return None

    def commit(self, net, runs, width, start_anchor=None, end_anchor=None):
        b = self.board
        ni = self.net_of[net]
        items = []
        # paths that start or end in the middle of an existing track join it at a real vertex
        if start_anchor is None:
            l0, (y0, x0) = runs[0][0], runs[0][1][0]
            start_anchor = self.split_at(net, l0, *pos(y0, x0))
        if end_anchor is None:
            l1, (y1, x1) = runs[-1][0], runs[-1][1][-1]
            end_anchor = self.split_at(net, l1, *pos(y1, x1))
        for k, (layer, pts) in enumerate(runs):
            xy = [pos(y, x) for y, x in pts]
            if k == 0 and start_anchor is not None:
                xy = [start_anchor] + xy
            if k == len(runs) - 1 and end_anchor is not None:
                xy = xy + [end_anchor]
            for a, c in zip(xy, xy[1:]):
                if abs(a[0] - c[0]) < 1e-6 and abs(a[1] - c[1]) < 1e-6:
                    continue
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(VECTOR2I(FromMM(OX + a[0]), FromMM(OY + a[1])))
                t.SetEnd(VECTOR2I(FromMM(OX + c[0]), FromMM(OY + c[1])))
                t.SetWidth(FromMM(width)); t.SetLayer(layer); t.SetNet(ni)
                b.Add(t); items.append(t)
            if k < len(runs) - 1:
                y, x = runs[k + 1][1][0]
                vx, vy = pos(y, x)
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(VECTOR2I(FromMM(OX + vx), FromMM(OY + vy)))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetWidth(FromMM(self.via_d)); v.SetDrill(FromMM(self.via_drill))
                v.SetNet(ni)
                b.Add(v); items.append(v)
        self.add_items(items)
        return items

    # ------------------------------------------------------------------ copper masks
    def copper_mask(self, items, layer, shrink=0.0):
        """Cells covered by the given items on a layer (track centre allowed there)."""
        m = Maps.__new__(Maps)
        arr = np.full((NY, NX), FREE, dtype=np.int32)
        m.occ = {layer: arr}
        for it in items:
            if not it.IsOnLayer(layer):
                continue
            ps = pcbnew.SHAPE_POLY_SET()
            if it.GetClass() == 'ZONE':
                ps = pcbnew.SHAPE_POLY_SET(it.GetFilledPolysList(layer))
                if shrink:
                    ps.Inflate(-FromMM(shrink), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, FromMM(0.005))
            else:
                it.TransformShapeToPolygon(ps, layer, -FromMM(shrink) if shrink else 0, FromMM(0.005),
                                           pcbnew.ERROR_INSIDE)
            Maps._stamp(m, arr, ps, 1)
        return arr == 1
