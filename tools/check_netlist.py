"""Compare the netlist KiCad derives from card.kicad_sch with design.py.

python check_netlist.py <netlist.net>   (kicad-cli sch export netlist --format kicadsexpr)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import load, find, first, val
import design

net = load(sys.argv[1])
got = {}
for n in find(first(net, 'nets'), 'net'):
    name = val(n, 'name')
    for node in find(n, 'node'):
        got[(val(node, 'ref'), val(node, 'pin'))] = name.lstrip('/')

bad = 0
for ref, p in design.PARTS.items():
    for pin, want in p['nets'].items():
        have = got.get((ref, pin))
        if want is None:
            if have and not have.startswith('unconnected-'):
                print('expected NC', ref, pin, 'got', have); bad += 1
        elif have != want:
            print('MISMATCH', ref, pin, 'want', want, 'got', have); bad += 1
comps = {val(c, 'ref') for c in find(first(net, 'components'), 'comp')}
missing = set(design.PARTS) - comps
extra = {c for c in comps - set(design.PARTS) if not c.startswith('#')}
print('components in netlist:', len(comps), 'missing:', sorted(missing), 'extra:', sorted(extra))
print('pin mismatches:', bad)
sys.exit(1 if bad or missing or extra else 0)
