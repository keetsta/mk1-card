"""BOM to send to an assembly house for a stock and price check: fab/card-bom-rfq.xlsx.

python make_bom.py [boards]      (needs openpyxl; run after make_fab.py, which writes the CPL it reads sides from)

One line per manufacturer part, with MPN, manufacturer, LCSC code and whether a substitute is allowed.
Quantities are plain numbers, not formulas: openpyxl stores no computed values, and mail previews
would show formula cells empty.
"""
import csv, os, sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design

PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, 'fab', 'card-bom-rfq.xlsx')
CPL = os.path.join(PROJ, 'fab', 'card-cpl.csv')

BOARD = [
    ('Project', 'MK-1 business card (keetsta)'),
    ('PCB', '85.6 x 54 mm, 4 layers, 1.0 mm, ENIG, white solder mask, black silkscreen'),
    ('Panel', 'single board with 5 mm rails on both long sides (85.6 x 64 mm)'),
    ('Assembly', 'double-sided SMT; top: LEDs, USB-C, button, light sensor; bottom: everything else'),
    ('Not placed', 'TP1, TP2, TP3 are bare test pads, no parts'),
    ('Request', 'please confirm stock, lead time and price per line; offer substitutes only where allowed'),
]
HEAD = ['#', 'Designators', 'Qty / board', 'Qty total', 'Side', 'Description', 'Manufacturer', 'MPN',
        'LCSC #', 'Substitute allowed', 'Notes']
WIDTH = [4, 30, 11, 10, 8, 46, 22, 26, 11, 44, 40]
NOTES = {
    'C42411119': 'limited stock worldwide, please reserve',
    'C25100': 'any 27 ohm 0402 is fine, no need for a full reel',
}


def natural(ref):
    return ''.join(c for c in ref if c.isalpha()), int(''.join(c for c in ref if c.isdigit()) or 0)


def refs_text(refs):
    """D1..D144 instead of 144 designators; short lists stay as they are."""
    refs = sorted(refs, key=natural)
    pre = {natural(r)[0] for r in refs}
    nums = [natural(r)[1] for r in refs]
    if len(refs) > 6 and len(pre) == 1 and nums == list(range(nums[0], nums[-1] + 1)):
        p = pre.pop()
        return f'{p}{nums[0]}-{p}{nums[-1]}'
    return ', '.join(refs)


def main():
    boards = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    with open(CPL, encoding='utf-8') as fh:
        side = {row['Designator']: row['Layer'] for row in csv.DictReader(fh)}

    lines = {}
    for ref, p in design.PARTS.items():
        if not p['lcsc']:
            continue
        if p['lcsc'] not in design.SOURCING:
            raise SystemExit(f'{ref}: {p["lcsc"]} has no SOURCING entry in design.py')
        lines.setdefault(p['lcsc'], []).append(ref)
    missing = [r for refs in lines.values() for r in refs if r not in side]
    if missing:
        raise SystemExit(f'not in {CPL}: {missing}; run make_fab.py first')
    order = sorted(lines.items(), key=lambda kv: natural(sorted(kv[1], key=natural)[0]))

    wb = Workbook()
    ws = wb.active
    ws.title = 'BOM'
    bold = Font(bold=True)
    thin = Side(style='thin', color='BBBBBB')
    grid = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical='top')

    ws['A1'] = 'MK-1 business card: bill of materials'
    ws['A1'].font = Font(bold=True, size=14)
    for i, (k, v) in enumerate(BOARD, start=2):
        ws.cell(i, 1, k).font = bold
        ws.cell(i, 3, v)
    qrow = len(BOARD) + 2
    ws.cell(qrow, 1, 'Boards').font = bold
    ws.cell(qrow, 3, boards).font = bold
    ws.cell(qrow, 3).alignment = Alignment(horizontal='left')

    top = qrow + 2
    for c, h in enumerate(HEAD, start=1):
        cell = ws.cell(top, c, h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='222222')
        cell.alignment = wrap
        cell.border = grid
    for n, (lcsc, refs) in enumerate(order, start=1):
        mfr, mpn, desc, sub = design.SOURCING[lcsc]
        sides = {side[r] for r in refs}
        r = top + n
        row = [n, refs_text(refs), len(refs), len(refs) * boards, '/'.join(sorted(sides)), desc, mfr, mpn, lcsc,
               sub, NOTES.get(lcsc, '')]
        for c, v in enumerate(row, start=1):
            cell = ws.cell(r, c, v)
            cell.alignment = wrap
            cell.border = grid
    end = top + len(order)
    ws.cell(end + 1, 2, 'Total').font = bold
    per_board = sum(len(v) for v in lines.values())
    ws.cell(end + 1, 3, per_board).font = bold
    ws.cell(end + 1, 4, per_board * boards).font = bold
    ws.cell(end + 1, 6, f'{len(order)} unique parts')

    for i, w in enumerate(WIDTH, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    ws.freeze_panes = ws.cell(top + 1, 3)
    ws.auto_filter.ref = f'A{top}:{ws.cell(end, len(HEAD)).coordinate}'
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    wb.save(OUT)
    print(OUT, '|', len(order), 'lines,', per_board, 'placements per board,', boards, 'boards')


if __name__ == '__main__':
    main()
