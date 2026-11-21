"""Build card.pretty: footprints taken from the Raspberry Pi RP2350A minimal design (MIT, see
ref/LICENSE-RPi-minimal.txt) converted to KiCad 9 format, plus footprints drawn from datasheets.

Run with any Python 3: python make_fplib.py
"""
import copy, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import load, find, first, dumps, QStr

PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, 'card.pretty')
REF = os.path.join(HERE, 'ref', 'RPI-RP2350A-MINIMAL_R4-S1.kicad_pcb')
M3D = '${KICAD9_3DMODEL_DIR}/'

# reference designator in the RPi board -> (new name, KiCad 3D model)
RPI = {
    # KiCad ships no QFN-60 model; the 7 x 7 mm QFN-56 body looks the same in a render
    'U1': ('RPi_rp2350a_vias', 'Package_DFN_QFN.3dshapes/QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm.wrl'),
    # L1 and the buzzer below are no longer on the board but stay in the library: KiCad parses the whole
    # library when build_pcb.py loads a footprint, every parsed footprint draws from the seeded UUID
    # generator, and dropping one shifts the UUIDs, the save order and with it the routing.
    'L1': ('RPi_aota-b201610s3r3-101-t', 'Inductor_SMD.3dshapes/L_0805_2012Metric.wrl'),
    'C6': ('RPi_capc1005x50_wide', 'Capacitor_SMD.3dshapes/C_0402_1005Metric.wrl'),
    'C11': ('RPi_capc1005x50', 'Capacitor_SMD.3dshapes/C_0402_1005Metric.wrl'),
    'R6': ('RPi_resc1005x35', 'Resistor_SMD.3dshapes/R_0402_1005Metric.wrl'),
    'X1': ('RPi_xtalcc320x250x80-4', 'Crystal.3dshapes/Crystal_SMD_3225-4Pin_3.2x2.5mm.wrl'),
    'U3': ('RPi_soic127p790x195-8', 'Package_SO.3dshapes/SOIC-8_5.3x5.3mm_P1.27mm.wrl'),
}
DROP = {'uuid', 'net', 'pinfunction', 'pintype', 'unlocked', 'path', 'sheetname', 'sheetfile',
        'units', 'duplicate_pad_numbers_are_jumpers', 'at_fp', 'embedded_fonts'}
HEADER = [['version', '20241229'], ['generator', QStr('pcbnew')], ['generator_version', QStr('9.0')]]


def clean(node):
    if not isinstance(node, list):
        return node
    return [clean(x) for x in node if not (isinstance(x, list) and x and x[0] in DROP)]


def model(path):
    return ['model', QStr(M3D + path), ['offset', ['xyz', '0', '0', '0']],
            ['scale', ['xyz', '1', '1', '1']], ['rotate', ['xyz', '0', '0', '0']]]


def prop(name, value, at, layer, hide=False, size=1.0, thick=0.15):
    p = ['property', QStr(name), QStr(value), ['at'] + [str(v) for v in at], ['layer', QStr(layer)]]
    if hide:
        p.append(['hide', 'yes'])
    p.append(['effects', ['font', ['size', str(size), str(size)], ['thickness', str(thick)]]])
    return p


def from_rpi(fp, name, model3d):
    props = {p[1]: p for p in find(fp, 'property')}
    out = ['footprint', QStr(name)] + copy.deepcopy(HEADER) + [['layer', QStr('F.Cu')]]
    desc = props.get('Description', [None, None, ''])[2] or ''
    out.append(['descr', QStr(f'{desc} (from Raspberry Pi RP2350A minimal design R4, MIT)'.strip())])
    ref = clean(props['Reference'])
    ref[2] = QStr('REF**')
    val = clean(props['Value'])
    val[2] = QStr(name)
    out += [ref, val]
    for key in ('Datasheet', 'Description'):
        if key in props:
            p = clean(props[key])
            if key == 'Datasheet':
                p[2] = QStr('')
            out.append(p)
    for x in fp[2:]:
        if not isinstance(x, list) or not x:
            continue
        if x[0] in ('property', 'layer', 'at', 'model') or x[0] in DROP:
            continue
        out.append(clean(x))
    out.append(model(model3d))
    return out


def rect(layer, x1, y1, x2, y2, w=0.1, fill='no'):
    return ['fp_rect', ['start', str(x1), str(y1)], ['end', str(x2), str(y2)],
            ['stroke', ['width', str(w)], ['type', 'solid']], ['fill', fill], ['layer', QStr(layer)]]


def line(layer, x1, y1, x2, y2, w=0.12):
    return ['fp_line', ['start', str(x1), str(y1)], ['end', str(x2), str(y2)],
            ['stroke', ['width', str(w)], ['type', 'solid']], ['layer', QStr(layer)]]


def smd(num, x, y, w, h, shape='roundrect', rr=0.25):
    p = ['pad', QStr(num), 'smd', shape, ['at', str(x), str(y)], ['size', str(w), str(h)],
         ['layers', QStr('F.Cu'), QStr('F.Mask'), QStr('F.Paste')]]
    if shape == 'roundrect':
        p.append(['roundrect_rratio', str(rr)])
    return p


def base(name, descr, ref_y, val_y, attr='smd'):
    return (['footprint', QStr(name)] + copy.deepcopy(HEADER) + [['layer', QStr('F.Cu')],
            ['descr', QStr(descr)],
            prop('Reference', 'REF**', (0, ref_y, 0), 'F.SilkS'),
            prop('Value', name, (0, val_y, 0), 'F.Fab'),
            prop('Datasheet', '', (0, 0, 0), 'F.Fab', hide=True),
            prop('Description', descr, (0, 0, 0), 'F.Fab', hide=True),
            ['attr', attr]])


def led_0603_kt():
    # KENTO 0603 red (LCSC C2286): body 1.6 x 0.8, suggested pads 0.7 long with a 0.7 gap.
    # Pads are kept 0.8 wide so a 2.4 mm matrix pitch leaves 0.3 mm between neighbours.
    fp = base('LED_0603_KT', 'KENTO 0603 LED, datasheet land pattern, pad 1 = cathode (K)', -1.0, 1.0)
    fp += [smd('1', -0.7, 0, 0.7, 0.8), smd('2', 0.7, 0, 0.7, 0.8),
           rect('F.Fab', -0.8, -0.4, 0.8, 0.4),
           line('F.Fab', -0.45, -0.4, -0.45, 0.4, 0.1),
           # cathode mark under the body, hidden once the LED is mounted
           line('F.SilkS', -0.1, -0.22, -0.1, 0.22, 0.15),
           rect('F.CrtYd', -1.15, -0.55, 1.15, 0.55, 0.05),
           model('LED_SMD.3dshapes/LED_0603_1608Metric.wrl')]
    return fp


def temt6200():
    # Vishay TEMT6200FX01 (LCSC C143695): body 2.0 x 1.25, recommended pads 1.0 x 1.45 with a 0.6 gap.
    # Pad 1 = emitter, pad 2 = collector, the numbering of the EasyEDA footprint JLC places from.
    fp = base('TEMT6200FX01', 'Vishay TEMT6200FX01 ambient light sensor 0805, pad 1 = emitter, pad 2 = collector',
              -1.4, 1.4)
    fp += [smd('1', -0.8, 0, 1.0, 1.45, 'rect'), smd('2', 0.8, 0, 1.0, 1.45, 'rect'),
           rect('F.Fab', -1.0, -0.625, 1.0, 0.625),
           line('F.Fab', -0.7, -0.625, -0.7, 0.625, 0.1),
           # emitter-side mark under the body, hidden once the sensor is mounted
           line('F.SilkS', -0.05, -0.35, -0.05, 0.35, 0.15),
           rect('F.CrtYd', -1.55, -0.98, 1.55, 0.98, 0.05),
           model('LED_SMD.3dshapes/LED_0805_2012Metric.wrl')]
    return fp

def buzzer_mlt8530():
    # Huaneng MLT-8530: 8.5 x 8.5 body, four 2.3 x 2.3 pads with a 4.8 mm gap, + top-left,
    # - bottom-left, two dummy pads on the right (datasheet 5.2 soldering pattern, top view).
    fp = base('Buzzer_MLT-8530', 'Huaneng MLT-8530 SMD magnetic buzzer, pad 1 = +, pad 2 = -', -5.4, 5.4)
    c = 3.55
    fp += [smd('1', -c, -c, 2.3, 2.3, 'rect'), smd('2', -c, c, 2.3, 2.3, 'rect'),
           smd('', c, -c, 2.3, 2.3, 'rect'), smd('', c, c, 2.3, 2.3, 'rect'),
           rect('F.Fab', -4.25, -4.25, 4.25, 4.25),
           line('F.SilkS', -2.2, -4.4, 2.2, -4.4), line('F.SilkS', -2.2, 4.4, 2.2, 4.4),
           line('F.SilkS', -4.4, -2.2, -4.4, 2.2), line('F.SilkS', 4.4, -2.2, 4.4, 2.2),
           line('F.SilkS', -5.6, -3.55, -4.9, -3.55), line('F.SilkS', -5.25, -3.9, -5.25, -3.2),
           rect('F.CrtYd', -5.9, -4.95, 4.95, 4.95, 0.05),
           model('Buzzer_Beeper.3dshapes/PUIAudio_SMT_0825_S_4_R.wrl')]
    return fp


def write(fp):
    path = os.path.join(OUT, fp[1] + '.kicad_mod')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(dumps(fp) + '\n')
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    pcb = load(REF)
    by_ref = {}
    for fp in find(pcb, 'footprint'):
        ref = next((p[2] for p in find(fp, 'property') if p[1] == 'Reference'), None)
        by_ref[ref] = fp
    for ref, (name, m3d) in RPI.items():
        fp = by_ref[ref]
        at = first(fp, 'at')
        assert len(at) < 4 or float(at[3]) == 0, f'{ref} must be unrotated in the reference'
        print(write(from_rpi(fp, name, m3d)))
    for fp in (led_0603_kt(), temt6200(), buzzer_mlt8530()):
        print(write(fp))


if __name__ == '__main__':
    main()
