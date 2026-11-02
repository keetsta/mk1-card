"""Generate card.kicad_sch, card.kicad_sym and the project library tables from design.py.

Every pin gets a short wire stub ending in a net label (or a power symbol), so the drawing is
regular and the netlist is exactly the one in design.py. UUIDs are derived from names, so the
board can link its footprints to the same symbols on every run.

Run with any Python 3: python gen_sch.py
"""
import os, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design
from design import PARTS, MATRIX_COLS, MATRIX_ROWS, led_ref
from sexp import dumps, QStr
from symlib import get_symbol, pins as sym_pins

PROJ = os.path.dirname(HERE)
NS = uuid.UUID('6f1c0a52-5a0e-4c39-9d4e-0c6a2b7d1e01')
POWER = {'GND': 'power:GND', '+3V3': 'power:+3V3', 'VBUS': 'power:VBUS', '+1V1': 'power:+1V1'}
G = 2.54


def uid(key):
    return QStr(str(uuid.uuid5(NS, key)))


ROOT = uid('root')


def font(size=1.27, hide=False, justify=None, bold=False):
    f = ['font', ['size', str(size), str(size)]]
    if bold:
        f.append(['bold', 'yes'])
    e = ['effects', f]
    if justify:
        e.append(['justify'] + justify.split())
    if hide:
        e.append(['hide', 'yes'])
    return e


def f(v):
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


# ---------------------------------------------------------------- custom symbols
def pin(kind, x, y, ang, name, num, length=G, hidden=False):
    p = ['pin', kind, 'line', ['at', f(x), f(y), f(ang)], ['length', f(length)]]
    if hidden:
        p.append(['hide', 'yes'])
    p += [['name', QStr(name), font()], ['number', QStr(str(num)), font()]]
    return p


def sym_header(name, ref, value, fp, ds, desc, ref_at, val_at):
    return ['symbol', QStr(name), ['pin_names', ['offset', '1.016']], ['exclude_from_sim', 'no'],
            ['in_bom', 'yes'], ['on_board', 'yes'],
            ['property', QStr('Reference'), QStr(ref), ['at', f(ref_at[0]), f(ref_at[1]), '0'], font()],
            ['property', QStr('Value'), QStr(value), ['at', f(val_at[0]), f(val_at[1]), '0'], font()],
            ['property', QStr('Footprint'), QStr(fp), ['at', '0', '0', '0'], font(hide=True)],
            ['property', QStr('Datasheet'), QStr(ds), ['at', '0', '0', '0'], font(hide=True)],
            ['property', QStr('Description'), QStr(desc), ['at', '0', '0', '0'], font(hide=True)]]


def rp2350a_symbol(name='RP2350A'):
    s = sym_header(name, 'U', 'RP2350A', 'card:RPi_rp2350a_vias',
                   'https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf',
                   'Raspberry Pi RP2350A, dual Cortex-M33 / Hazard3, QFN-60, external flash',
                   (0, 46.99), (0, -46.99))
    body = ['symbol', QStr(f'{name}_0_1'),
            ['rectangle', ['start', '-20.32', '40.64'], ['end', '20.32', '-40.64'],
             ['stroke', ['width', '0.254'], ['type', 'default']], ['fill', ['type', 'background']]]]
    pins = []
    for i in range(30):
        pins.append(pin('bidirectional', 22.86, 36.83 - G * i, 180, f'GPIO{i}' + ('_ADC%d' % (i - 26) if i >= 26 else ''),
                        [k for k, v in design.RP2350A_PINS.items() if v.split('_')[0] == f'GPIO{i}'][0]))
    left = [('RUN', 26, 'input', 36.83), ('SWCLK', 24, 'input', 34.29), ('SWDIO', 25, 'bidirectional', 31.75),
            ('XIN', 21, 'input', 26.67), ('XOUT', 22, 'passive', 24.13),
            ('USB_DP', 52, 'bidirectional', 19.05), ('USB_DM', 51, 'bidirectional', 16.51),
            ('QSPI_SS', 60, 'bidirectional', 11.43), ('QSPI_SCLK', 56, 'output', 8.89),
            ('QSPI_SD0', 57, 'bidirectional', 6.35), ('QSPI_SD1', 59, 'bidirectional', 3.81),
            ('QSPI_SD2', 58, 'bidirectional', 1.27), ('QSPI_SD3', 55, 'bidirectional', -1.27),
            ('VREG_LX', 48, 'passive', -6.35), ('VREG_FB', 50, 'input', -8.89),
            ('VREG_VIN', 49, 'power_in', -13.97), ('VREG_AVDD', 46, 'power_in', -16.51)]
    for nm, num, kind, y in left:
        pins.append(pin(kind, -22.86, y, 0, nm, num))
    top = [('IOVDD', 1), ('IOVDD', 11), ('IOVDD', 20), ('IOVDD', 30), ('IOVDD', 38), ('IOVDD', 45),
           ('QSPI_IOVDD', 54), ('USB_OTP_VDD', 53), ('ADC_AVDD', 44), ('DVDD', 6), ('DVDD', 23), ('DVDD', 39)]
    for i, (nm, num) in enumerate(top):
        pins.append(pin('power_in', -13.97 + G * i, 43.18, 270, nm, num))
    pins.append(pin('power_in', -2.54, -43.18, 90, 'VREG_PGND', 47))
    pins.append(pin('power_in', 2.54, -43.18, 90, 'GND', 61))
    s += [body, ['symbol', QStr(f'{name}_1_1')] + pins, ['embedded_fonts', 'no']]
    return s


def temt_symbol(name='TEMT6200FX01'):
    # pin numbers follow the LCSC/EasyEDA part C143695 (1 = emitter, 2 = collector) so JLC orients it right
    s = sym_header(name, 'U', 'TEMT6200FX01', 'card:TEMT6200FX01',
                   'https://www.vishay.com/docs/81317/temt6200.pdf',
                   'Vishay ambient light sensor, NPN phototransistor, 0805', (3.81, 2.54), (3.81, -2.54))
    body = ['symbol', QStr(f'{name}_0_1'),
            ['circle', ['center', '0', '0'], ['radius', '2.54'], ['stroke', ['width', '0.254'], ['type', 'default']],
             ['fill', ['type', 'background']]],
            ['polyline', ['pts', ['xy', '-3.81', '3.81'], ['xy', '-2.286', '2.286']],
             ['stroke', ['width', '0.2'], ['type', 'default']], ['fill', ['type', 'none']]],
            ['polyline', ['pts', ['xy', '-3.302', '4.318'], ['xy', '-1.778', '2.794']],
             ['stroke', ['width', '0.2'], ['type', 'default']], ['fill', ['type', 'none']]]]
    pins = [pin('passive', 0, 5.08, 270, 'C', 2), pin('passive', 0, -5.08, 90, 'E', 1)]
    s += [body, ['symbol', QStr(f'{name}_1_1')] + pins, ['embedded_fonts', 'no']]
    return s


CUSTOM = {'card:RP2350A': rp2350a_symbol, 'card:TEMT6200FX01': temt_symbol}


def lib_symbol(lib_id):
    if lib_id in CUSTOM:
        s = CUSTOM[lib_id]()
        s[1] = QStr(lib_id)
        return s
    return get_symbol(lib_id)


# ---------------------------------------------------------------- placement
PLACE = {}


def at(ref, x, y):
    PLACE[ref] = (x, y)


def row(refs, x0, y0, dx=12.7):
    for i, r in enumerate(refs):
        at(r, x0 + dx * i, y0)


# USB and power
at('J1', 50.8, 81.28)
at('U4', 109.22, 68.58)
row(['R11', 'R12'], 86.36, 109.22)
at('U2', 114.3, 124.46)
row(['C1', 'C5', 'C19'], 96.52, 144.78)
# RP2350A core
at('U1', 213.36, 116.84)
row(['C12', 'C13', 'C14', 'C15', 'C16', 'C17', 'C18'], 175.26, 185.42, 10.16)
row(['C8', 'C10', 'C11'], 248.92, 185.42, 10.16)
row(['L1', 'C6', 'C7'], 266.7, 55.88, 12.7)
row(['R3', 'C9'], 266.7, 78.74, 12.7)
at('X1', 274.32, 106.68)
row(['C3', 'C4', 'R2'], 266.7, 124.46, 12.7)
row(['R7', 'R8'], 266.7, 147.32, 12.7)
# flash and button
at('U3', 337.82, 60.96)
row(['C2', 'R10', 'R6'], 322.58, 88.9, 12.7)
at('SW1', 345.44, 104.14)
row(['TP1', 'TP2', 'TP3'], 322.58, 124.46, 15.24)
# LED driver
at('U5', 355.6, 185.42)
row(['R15', 'R13', 'R14'], 322.58, 236.22, 12.7)
row(['C21', 'C22', 'C23', 'C24'], 322.58, 254.0, 12.7)
# EEPROM, light sensor, buzzer
at('U7', 449.58, 63.5)
at('C25', 482.6, 63.5)
at('U6', 444.5, 109.22)
row(['R17', 'R18', 'C26'], 462.28, 116.84, 12.7)
at('BZ1', 452.12, 157.48)
at('D145', 474.98, 157.48)
at('Q1', 452.12, 180.34)
row(['R19', 'R20'], 431.8, 195.58, 12.7)
# LED matrix
MX0, MY0, MDX, MDY = 33.02, 292.1, 22.86, 11.43
for r in range(MATRIX_ROWS):
    for c in range(MATRIX_COLS):
        at(led_ref(r, c), MX0 + MDX * c, MY0 + MDY * r)

TEXTS = [
    ('USB-C, protection, 3.3 V', 25.4, 45.72),
    ('RP2350A core: copied from the Raspberry Pi RP2350A minimal design R4', 165.1, 45.72),
    ('flash, BOOTSEL button, SWD pads', 312.42, 45.72),
    ('LED matrix driver, VCC from VBUS', 312.42, 147.32),
    ('EEPROM U7, black box', 419.1, 45.72),
    ('light sensor', 419.1, 96.52),
    ('buzzer', 419.1, 144.78),
    ('LED matrix 16 x 9: cathodes on the row pin, as in IS31FL3731 datasheet figure 1', 25.4, 279.4),
]
NOTES = [
    ('button = BOOTSEL: held at power-up -> UF2 mode; read at runtime from QSPI_SS (flash access paused)', 312.42, 116.84),
    ('ILED avg = 64.7 / REXT = 1.96 mA per LED; 144 LEDs at full PWM ~ 0.28 A from VBUS', 312.42, 271.78),
    ('LUX_RANGE: hi-Z = 10k load (indoor), drive low = 0.9k load (bright); keep its input buffer off', 419.1, 132.08),
    ('buzzer: PWM only; DC on the transistor would put 0.3 A through the coil', 419.1, 213.36),
]


# ---------------------------------------------------------------- emit
class Sheet:
    def __init__(self):
        self.items = []
        self.pwr_n = 0
        self.flg_n = 0

    def wire(self, a, b, key):
        self.items.append(['wire', ['pts', ['xy', f(a[0]), f(a[1])], ['xy', f(b[0]), f(b[1])]],
                           ['stroke', ['width', '0'], ['type', 'default']], ['uuid', uid('w:' + key)]])

    def label(self, net, p, out, key):
        ang = {'left': 180, 'right': 0, 'up': 90, 'down': 270}[out]
        just = 'left bottom' if ang in (0, 90) else 'right bottom'
        self.items.append(['label', QStr(net), ['at', f(p[0]), f(p[1]), str(ang)], ['fields_autoplaced', 'yes'],
                           font(justify=just), ['uuid', uid('l:' + key)]])

    def noconn(self, p, key):
        self.items.append(['no_connect', ['at', f(p[0]), f(p[1])], ['uuid', uid('nc:' + key)]])

    def text(self, s, x, y, size=2.54, bold=True):
        self.items.append(['text', QStr(s), ['exclude_from_sim', 'no'], ['at', f(x), f(y), '0'],
                           font(size=size, justify='left bottom', bold=bold), ['uuid', uid('t:' + s)]])

    def symbol(self, lib_id, ref, value, x, y, rot=0, fp='', lcsc='', desc='', pin_nums=(), hide_ref=False,
               in_bom=True, on_board=True):
        props = [
            ['property', QStr('Reference'), QStr(ref), ['at', f(x + 2.54), f(y - 1.27), '0'],
             font(hide=hide_ref, justify='left')],
            ['property', QStr('Value'), QStr(value), ['at', f(x + 2.54), f(y + 1.27), '0'], font(justify='left')],
            ['property', QStr('Footprint'), QStr(fp), ['at', f(x), f(y), '0'], font(hide=True)],
            ['property', QStr('Datasheet'), QStr(''), ['at', f(x), f(y), '0'], font(hide=True)],
            ['property', QStr('Description'), QStr(desc), ['at', f(x), f(y), '0'], font(hide=True)],
        ]
        if lcsc:
            props.append(['property', QStr('LCSC'), QStr(lcsc), ['at', f(x), f(y), '0'], font(hide=True)])
        node = ['symbol', ['lib_id', QStr(lib_id)], ['at', f(x), f(y), str(rot)], ['unit', '1'],
                ['exclude_from_sim', 'no'], ['in_bom', 'yes' if in_bom else 'no'],
                ['on_board', 'yes' if on_board else 'no'], ['dnp', 'no'], ['uuid', uid('s:' + ref)]]
        node += props
        for n in pin_nums:
            node.append(['pin', QStr(n), ['uuid', uid(f'p:{ref}:{n}')]])
        node.append(['instances', ['project', QStr('card'),
                                   ['path', QStr('/' + ROOT), ['reference', QStr(ref)], ['unit', '1']]]])
        self.items.append(node)

    def power(self, net, p, out, key):
        rot = {'down': 0, 'up': 180, 'right': 90, 'left': 270} if net == 'GND' else \
              {'up': 0, 'down': 180, 'left': 90, 'right': 270}
        self.pwr_n += 1
        ref = f'#PWR{self.pwr_n:03d}'
        self.symbol(POWER[net], ref, net, p[0], p[1], rot[out], pin_nums=('1',), hide_ref=True, in_bom=False,
                    on_board=False)

    def flag(self, net, x, y):
        self.flg_n += 1
        ref = f'#FLG{self.flg_n:02d}'
        self.symbol('power:PWR_FLAG', ref, 'PWR_FLAG', x, y, 0, pin_nums=('1',), hide_ref=True, in_bom=False,
                    on_board=False)
        end = (x, y + G)
        self.wire((x, y), end, 'flag:' + net)
        if net in POWER:
            self.power(net, end, 'down', 'flag:' + net)
        else:
            self.label(net, end, 'down', 'flag:' + net)


OUTDIR = {0: 'left', 180: 'right', 90: 'down', 270: 'up'}
STEP = {'left': (-G, 0), 'right': (G, 0), 'up': (0, -G), 'down': (0, G)}


def build():
    sh = Sheet()
    used_libs = set()
    symcache = {}
    for ref, p in PARTS.items():
        lib_id = p['symbol']
        if lib_id not in symcache:
            symcache[lib_id] = lib_symbol(lib_id)
        sym = symcache[lib_id]
        used_libs.add(lib_id)
        x, y = PLACE[ref]
        plist = sym_pins(sym)
        nums = sorted({q['num'] for q in plist}, key=lambda s: (len(s), s))
        sh.symbol(lib_id, ref, p['value'], x, y, 0, fp=p['footprint'], lcsc=p['lcsc'], desc=p['desc'],
                  pin_nums=nums, in_bom=not ref.startswith('TP'))
        # group stacked pins by connection point
        points = {}
        for q in plist:
            pt = (round(x + q['x'], 4), round(y - q['y'], 4))
            points.setdefault(pt, []).append(q)
        for pt, qs in points.items():
            nets = {p['nets'].get(q['num']) for q in qs}
            assert len(nets) == 1, (ref, [q['num'] for q in qs], nets)
            net = nets.pop()
            key = f"{ref}:{qs[0]['num']}"
            if not net:
                sh.noconn(pt, key)
                continue
            out = OUTDIR[int(qs[0]['ang']) % 360]
            end = (pt[0] + STEP[out][0], pt[1] + STEP[out][1])
            sh.wire(pt, end, key)
            if net in POWER:
                sh.power(net, end, out, key)
                used_libs.add(POWER[net])
            else:
                sh.label(net, end, out, key)
    for net, x, y in (('VBUS', 30.48, 25.4), ('GND', 40.64, 25.4), ('+1V1', 50.8, 25.4), ('VREG_AVDD', 60.96, 25.4)):
        sh.flag(net, x, y)
    used_libs.add('power:PWR_FLAG')
    for s, x, y in TEXTS:
        sh.text(s, x, y)
    for s, x, y in NOTES:
        sh.text(s, x, y, size=1.524, bold=False)

    libs = []
    for lid in sorted(used_libs):
        libs.append(symcache.get(lid) or lib_symbol(lid))
    doc = ['kicad_sch', ['version', '20250114'], ['generator', QStr('eeschema')], ['generator_version', QStr('9.0')],
           ['uuid', ROOT], ['paper', QStr('A2')],
           ['title_block', ['title', QStr('keetsta MK-1 business card')], ['date', QStr('2026-11-02')],
            ['rev', QStr('1')], ['company', QStr('github.com/keetsta')],
            ['comment', '1', QStr('generated by tools/gen_sch.py from tools/design.py; edit the script, not this file')]],
           ['lib_symbols'] + libs] + sh.items + [
           ['sheet_instances', ['path', QStr('/'), ['page', QStr('1')]]], ['embedded_fonts', 'no']]
    with open(os.path.join(PROJ, 'card.kicad_sch'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(dumps(doc) + '\n')

    lib = ['kicad_symbol_lib', ['version', '20241209'], ['generator', QStr('kicad_symbol_editor')],
           ['generator_version', QStr('9.0')], rp2350a_symbol(), temt_symbol()]
    with open(os.path.join(PROJ, 'card.kicad_sym'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(dumps(lib) + '\n')
    with open(os.path.join(PROJ, 'sym-lib-table'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n\t(lib (name "card")(type "KiCad")(uri "${KIPRJMOD}/card.kicad_sym")'
                 '(options "")(descr "MK-1 custom symbols"))\n)\n')
    with open(os.path.join(PROJ, 'fp-lib-table'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "card")(type "KiCad")(uri "${KIPRJMOD}/card.pretty")'
                 '(options "")(descr "MK-1 footprints"))\n)\n')
    print('symbols:', len([i for i in sh.items if i[0] == 'symbol']), 'labels:',
          len([i for i in sh.items if i[0] == 'label']))


def symbol_uuid(ref):
    return str(uuid.uuid5(NS, 's:' + ref))


if __name__ == '__main__':
    build()
