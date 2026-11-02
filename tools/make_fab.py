"""JLCPCB order files: gerbers + drill (zip), BOM and CPL.

python make_fab.py      (needs kicad-cli from KiCad 9)

The CPL is written in JLC's terms, not KiCad's: see JLC below. The placement preview at JLC is still
the final check for every polarised part (LEDs, U1..U7, Q1, D145, L1 dot, X1, BZ1).
"""
import csv, math, os, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design

PROJ = os.path.dirname(HERE)
CLI = r'C:\Program Files\KiCad\9.0\bin\kicad-cli.exe'
PCB = os.path.join(PROJ, 'card.kicad_pcb')
OUT = os.path.join(PROJ, 'fab')
GERB = os.path.join(OUT, 'gerbers')
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
NOT_PLACED = {'TP1', 'TP2', 'TP3'}

# JLC places its own library footprint (the EasyEDA one behind each LCSC code) at the CPL point, turned by
# the CPL angle; back-side angles are read looking at the back, which makes them 180 - KiCad's angle.
# Per LCSC code: (how far JLC's zero orientation is turned from our footprint, CCW degrees;
# where JLC's footprint origin sits in our footprint, mm, KiCad axes). Measured 2026-11-02 by fitting
# every EasyEDA footprint onto ours. Two-pad polar parts are matched by marking, not by pad number.
JLC = {
    'C42411118': (0, None),          # RP2350A, pin 1 top-left in both
    'C42411119': (180, None),        # AOTA inductor: JLC draws the polarity dot at its pad 2, RPi at pad 1 (+1V1)
    'C191206': (270, None),          # IS31FL3731 QFN-28
    'C97521': (270, None),           # W25Q128 SOIC-8
    'C6203': (270, None),            # AT24C02C SOIC-8
    'C7519': (270, None),            # USBLC6 SOT-23-6
    'C51118': (270, None),           # AP2112K SOT-23-5
    'C20526': (180, None),           # MMBT3904 SOT-23
    'C2128': (0, None),              # 1N4148WS, cathode bar on the left in both
    'C2286': (0, None),              # KT-0603R, cathode on the left in both (JLC numbers it pad 2)
    'C143695': (0, None),            # TEMT6200FX01, emitter on the left in both
    'C94599': (270, None),           # MLT-8530 buzzer
    'C20625731': (0, None),          # ABM8-272-T3 crystal
    'C318884': (0, None),            # TS-1187A button
    'C165948': (0, (0.0, -1.571)),   # USB-C: JLC's origin is 1.571 mm nearer the contact row than KiCad's
}
for _code in ('C1525', 'C1548', 'C25117', 'C15850', 'C19666', 'C23733', 'C52923', 'C11702', 'C17168', 'C25100',
              'C25105', 'C25744', 'C25779', 'C25900', 'C25905'):
    JLC[_code] = (0, None)


def jlc_placement(ref, x, y, rot, bottom):
    """KiCad position (y up, as kicad-cli writes it) and angle -> JLC Mid X, Mid Y, Rotation."""
    lcsc = design.PARTS[ref]['lcsc']
    if lcsc not in JLC:
        raise SystemExit(f'{ref}: no JLC orientation known for {lcsc}, measure it before ordering')
    turn, origin = JLC[lcsc]
    if origin:
        ox, oy = origin
        if bottom:
            oy = -oy  # KiCad keeps back-side footprints mirrored in y
        a = math.radians(rot)
        x += ox * math.cos(a) + oy * math.sin(a)
        y -= -ox * math.sin(a) + oy * math.cos(a)
    angle = ((180 - rot) if bottom else rot) + turn
    return x, y, angle % 360


def run(*args):
    r = subprocess.run([CLI, *args], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stdout + r.stderr)


def main():
    os.makedirs(GERB, exist_ok=True)
    for f in os.listdir(GERB):
        os.remove(os.path.join(GERB, f))
    run('pcb', 'export', 'gerbers', '--layers', LAYERS, '--subtract-soldermask', '-o', GERB + os.sep, PCB)
    run('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm', '--excellon-separate-th',
        '-o', GERB + os.sep, PCB)
    zpath = os.path.join(OUT, 'card-gerbers.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(GERB)):
            z.write(os.path.join(GERB, f), f)

    # BOM: one line per value + footprint + LCSC code
    rows = {}
    for ref, p in design.PARTS.items():
        if ref in NOT_PLACED:
            continue
        key = (p['value'], p['footprint'].split(':')[1], p['lcsc'])
        rows.setdefault(key, []).append(ref)
    natural = lambda r: (''.join(c for c in r if c.isalpha()), int(''.join(c for c in r if c.isdigit()) or 0))
    with open(os.path.join(OUT, 'card-bom.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (value, fp, lcsc), refs in sorted(rows.items(), key=lambda kv: natural(sorted(kv[1], key=natural)[0])):
            w.writerow([value, ','.join(sorted(refs, key=natural)), fp, lcsc])

    # CPL from KiCad's own position export
    pos = os.path.join(OUT, 'card-pos-kicad.csv')
    run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '-o', pos, PCB)
    with open(pos, encoding='utf-8') as fh, open(os.path.join(OUT, 'card-cpl.csv'), 'w', newline='',
                                                 encoding='utf-8') as out:
        w = csv.writer(out)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        n = 0
        for row in csv.DictReader(fh):
            if row['Ref'] in NOT_PLACED:
                continue
            bottom = row['Side'].lower() != 'top'
            x, y, angle = jlc_placement(row['Ref'], float(row['PosX']), float(row['PosY']), float(row['Rot']),
                                        bottom)
            w.writerow([row['Ref'], f'{x:.4f}mm', f'{y:.4f}mm', 'Bottom' if bottom else 'Top', f'{angle:.1f}'])
            n += 1
    os.remove(pos)
    print('gerbers:', zpath)
    print('bom lines:', len(rows), 'placements:', n)


if __name__ == '__main__':
    main()
