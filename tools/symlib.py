"""Read symbols from KiCad .kicad_sym libraries, resolving `extends`."""
import copy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import load, find, first, val, QStr

SYMDIR = r'C:\Program Files\KiCad\9.0\share\kicad\symbols'
_cache = {}


def _lib(name):
    if name not in _cache:
        _cache[name] = load(os.path.join(SYMDIR, name + '.kicad_sym'))
    return _cache[name]


def get_symbol(lib_id):
    """Return a flattened symbol node named 'Lib:Name' ready for lib_symbols."""
    lib, name = lib_id.split(':')
    root = _lib(lib)
    syms = {s[1]: s for s in find(root, 'symbol')}
    sym = copy.deepcopy(syms[name])
    ext = first(sym, 'extends')
    if ext is not None:
        parent = copy.deepcopy(syms[ext[1]])
        while first(parent, 'extends') is not None:
            parent = copy.deepcopy(syms[first(parent, 'extends')[1]])
        pname = parent[1]
        child_props = {p[1]: p for p in find(sym, 'property')}
        out = [x for x in parent if not (isinstance(x, list) and x and x[0] == 'property')]
        props = []
        for p in find(parent, 'property'):
            props.append(child_props.pop(p[1], p))
        props += list(child_props.values())
        # insert properties after the header atoms
        head = out[:2]
        rest = out[2:]
        idx = 0
        while idx < len(rest) and not (isinstance(rest[idx], list) and rest[idx][0] == 'symbol'):
            idx += 1
        sym = head + rest[:idx] + props + rest[idx:]
        for sub in find(sym, 'symbol'):
            sub[1] = QStr(sub[1].replace(pname, name, 1))
    sym[1] = QStr(lib_id)
    return sym


def pins(sym):
    """List of (number, name, type, x, y, angle, length, unit) for all pins."""
    out = []
    for sub in find(sym, 'symbol'):
        unit = int(sub[1].rsplit('_', 2)[-2])
        for p in find(sub, 'pin'):
            at = first(p, 'at')
            out.append(dict(num=first(p, 'number')[1], name=first(p, 'name')[1], type=p[1],
                            x=float(at[1]), y=float(at[2]), ang=float(at[3]) if len(at) > 3 else 0.0,
                            length=float(val(p, 'length', default=0)), unit=unit))
    return out


if __name__ == '__main__':
    for lid in sys.argv[1:]:
        s = get_symbol(lid)
        print('==', lid, 'fp=', next((p[2] for p in find(s, 'property') if p[1] == 'Footprint'), ''))
        for p in sorted(pins(s), key=lambda q: (q['unit'], q['num'])):
            print(f"  u{p['unit']} {p['num']:>4} {p['name']:12s} {p['type']:14s} ({p['x']},{p['y']}) a{p['ang']}")
