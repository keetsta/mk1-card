"""Single source of truth for the MK-1 card: parts, values, LCSC codes, nets.

Both gen_sch.py (schematic) and build_pcb.py (board) read this module, so the
schematic and the board cannot drift apart.
"""

# GPIO plan for the RP2350A
GPIO = {
    4: 'SDA',        # I2C0 SDA: IS31FL3731 + AT24C02
    5: 'SCL',        # I2C0 SCL
    8: 'EE_WP',      # AT24C02 write protect, high = protected
    22: 'BUZZ',      # PWM to the buzzer driver
    26: 'LUX',       # ADC0, light sensor
    27: 'LUX_RANGE', # drive low to add 1k in parallel with the 10k load
}

RP2350A_PINS = {
    1: 'IOVDD', 2: 'GPIO0', 3: 'GPIO1', 4: 'GPIO2', 5: 'GPIO3', 6: 'DVDD', 7: 'GPIO4', 8: 'GPIO5',
    9: 'GPIO6', 10: 'GPIO7', 11: 'IOVDD', 12: 'GPIO8', 13: 'GPIO9', 14: 'GPIO10', 15: 'GPIO11',
    16: 'GPIO12', 17: 'GPIO13', 18: 'GPIO14', 19: 'GPIO15', 20: 'IOVDD', 21: 'XIN', 22: 'XOUT',
    23: 'DVDD', 24: 'SWCLK', 25: 'SWDIO', 26: 'RUN', 27: 'GPIO16', 28: 'GPIO17', 29: 'GPIO18',
    30: 'IOVDD', 31: 'GPIO19', 32: 'GPIO20', 33: 'GPIO21', 34: 'GPIO22', 35: 'GPIO23', 36: 'GPIO24',
    37: 'GPIO25', 38: 'IOVDD', 39: 'DVDD', 40: 'GPIO26_ADC0', 41: 'GPIO27_ADC1', 42: 'GPIO28_ADC2',
    43: 'GPIO29_ADC3', 44: 'ADC_AVDD', 45: 'IOVDD', 46: 'VREG_AVDD', 47: 'VREG_PGND', 48: 'VREG_LX',
    49: 'VREG_VIN', 50: 'VREG_FB', 51: 'USB_DM', 52: 'USB_DP', 53: 'USB_OTP_VDD', 54: 'QSPI_IOVDD',
    55: 'QSPI_SD3', 56: 'QSPI_SCLK', 57: 'QSPI_SD0', 58: 'QSPI_SD2', 59: 'QSPI_SD1', 60: 'QSPI_SS',
    61: 'GND',
}


def rp2350_nets():
    fixed = {
        'IOVDD': '+3V3', 'DVDD': '+1V1', 'ADC_AVDD': '+3V3', 'USB_OTP_VDD': '+3V3', 'QSPI_IOVDD': '+3V3',
        'VREG_VIN': '+3V3', 'VREG_AVDD': 'VREG_AVDD', 'VREG_PGND': 'GND', 'VREG_LX': 'VREG_LX',
        'VREG_FB': '+1V1', 'XIN': 'XIN', 'XOUT': 'XOUT', 'SWCLK': 'SWCLK', 'SWDIO': 'SWDIO', 'RUN': None,
        'USB_DM': 'USB_DN_MCU', 'USB_DP': 'USB_DP_MCU', 'QSPI_SS': 'QSPI_SS', 'QSPI_SCLK': 'QSPI_SCLK',
        'QSPI_SD0': 'QSPI_SD0', 'QSPI_SD1': 'QSPI_SD1', 'QSPI_SD2': 'QSPI_SD2', 'QSPI_SD3': 'QSPI_SD3',
        'GND': 'GND',
    }
    nets = {}
    for num, name in RP2350A_PINS.items():
        if name.startswith('GPIO'):
            n = int(name[4:].split('_')[0])
            nets[str(num)] = GPIO.get(n)
        else:
            nets[str(num)] = fixed[name]
    return nets


# LED matrix: 16 columns x 9 rows, IS31FL3731 cross-plexing as in its datasheet figure 1.
# Row r (0..8), column c (0..15). Columns 0..7 belong to matrix A (CA pins), 8..15 to B (CB pins).
# The cathode of every LED in row r sits on pin r+1 of its matrix; the anode of the LED in local
# column j (0..7) sits on pin j+1 when j < r, otherwise on pin j+2. The datasheet calls this LED
# "C(r+1)-(c+1)", which is what the Adafruit/Pimoroni drivers expect for a 16x9 panel.
MATRIX_COLS, MATRIX_ROWS = 16, 9


def led_nets(r, c):
    side = 'CA' if c < 8 else 'CB'
    j = c % 8
    cathode = f'{side}{r + 1}'
    anode = f'{side}{j + 1}' if j < r else f'{side}{j + 2}'
    return cathode, anode


def led_ref(r, c):
    return f'D{r * MATRIX_COLS + c + 1}'


# parts: ref -> dict(value, symbol, footprint, lcsc, nets{pin: net}, group, desc)
# footprints prefixed with "card:" live in card.pretty next to the project.
FP_R0402 = 'Resistor_SMD:R_0402_1005Metric'
FP_C0402 = 'Capacitor_SMD:C_0402_1005Metric'
RPI_R0402 = 'card:RPi_resc1005x35'
RPI_C0402 = 'card:RPi_capc1005x50'
RPI_C0402W = 'card:RPi_capc1005x50_wide'

LCSC = {
    '100n': 'C1525', '4.7u': 'C23733', '15p': 'C1548', '1u': 'C52923', '10u': 'C15850',
    '4.7u_0603': 'C19666',
    '1k': 'C11702', '470': 'C25117', '27': 'C25100', '33': 'C25105', '10k': 'C25744', '5.1k': 'C25905',
    '4.7k': 'C25900', '22k': 'C25768', '2.2k': 'C25879', '33k': 'C25779', '0': 'C17168',
}

PARTS = {}


def part(ref, value, symbol, footprint, lcsc, nets, group, desc=''):
    PARTS[ref] = dict(value=value, symbol=symbol, footprint=footprint, lcsc=lcsc,
                      nets={str(k): v for k, v in nets.items()}, group=group, desc=desc)


def R(ref, value, a, b, group, fp=FP_R0402, desc=''):
    part(ref, value, 'Device:R', fp, LCSC[value], {1: a, 2: b}, group, desc)


def C(ref, value, a, b, group, fp=FP_C0402, lcsc_key=None, desc=''):
    part(ref, value, 'Device:C', fp, LCSC[lcsc_key or value], {1: a, 2: b}, group, desc)


# ---- USB-C and power -------------------------------------------------------
part('J1', 'USB-C', 'Connector:USB_C_Receptacle_USB2.0_16P',
     'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', 'C165948',
     {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'S1': 'GND',
      'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS',
      'A5': 'CC1', 'B5': 'CC2', 'A6': 'USB_DP', 'B6': 'USB_DP', 'A7': 'USB_DN', 'B7': 'USB_DN',
      'A8': None, 'B8': None}, 'usb', 'HRO TYPE-C-31-M-12')
R('R11', '5.1k', 'CC1', 'GND', 'usb', desc='UFP Rd on CC1')
R('R12', '5.1k', 'CC2', 'GND', 'usb', desc='UFP Rd on CC2')
part('U4', 'USBLC6-2SC6', 'Power_Protection:USBLC6-2SC6', 'Package_TO_SOT_SMD:SOT-23-6', 'C7519',
     {1: 'USB_DP', 6: 'USB_DP', 3: 'USB_DN', 4: 'USB_DN', 2: 'GND', 5: 'VBUS'}, 'usb')
part('U2', 'AP2112K-3.3', 'Regulator_Linear:AP2112K-3.3', 'Package_TO_SOT_SMD:SOT-23-5', 'C51118',
     {1: 'VBUS', 3: 'VBUS', 2: 'GND', 4: None, 5: '+3V3'}, 'power')
C('C1', '4.7u', 'VBUS', 'GND', 'power', fp='Capacitor_SMD:C_0603_1608Metric', lcsc_key='4.7u_0603',
  desc='16 V; total VBUS capacitance stays under the 10 uF USB limit')
C('C5', '10u', '+3V3', 'GND', 'power', fp='Capacitor_SMD:C_0805_2012Metric')
C('C19', '10u', '+3V3', 'GND', 'power', fp='Capacitor_SMD:C_0805_2012Metric')

# ---- RP2350A core: copied from the Raspberry Pi RP2350A minimal design R4 ----
part('U1', 'RP2350A', 'card:RP2350A', 'card:RPi_rp2350a_vias', 'C42411118', rp2350_nets(), 'mcu')
part('L1', '3.3u', 'Device:L', 'card:RPi_aota-b201610s3r3-101-t', 'C42411119',
     {1: '+1V1', 2: 'VREG_LX'}, 'mcu', 'Abracon AOTA-B201610S3R3-101-T, polarity marked, dot = pin 1')
C('C6', '4.7u', '+3V3', 'GND', 'mcu', fp=RPI_C0402W, desc='regulator CIN')
C('C7', '4.7u', '+1V1', 'GND', 'mcu', fp=RPI_C0402W, desc='regulator COUT')
C('C9', '4.7u', 'VREG_AVDD', 'GND', 'mcu', fp=RPI_C0402)
R('R3', '33', '+3V3', 'VREG_AVDD', 'mcu', fp=RPI_R0402)
for ref in ('C8', 'C11'):
    C(ref, '100n', '+1V1', 'GND', 'mcu', fp=RPI_C0402)
# RP2350 datasheet 6.3.8.1 asks for a second 4.7 uF on DVDD at pin 23; it takes the 100 nF's place
C('C10', '4.7u', '+1V1', 'GND', 'mcu', fp=RPI_C0402)
for ref in ('C12', 'C13', 'C14', 'C15', 'C16', 'C17', 'C18'):
    C(ref, '100n', '+3V3', 'GND', 'mcu', fp=RPI_C0402)
part('X1', '12MHz', 'Device:Crystal_GND24', 'card:RPi_xtalcc320x250x80-4', 'C20625731',
     {1: 'XIN', 3: 'XOUT_R', 2: 'GND', 4: 'GND'}, 'mcu', 'Abracon ABM8-272-T3, 10 pF load')
C('C3', '15p', 'XIN', 'GND', 'mcu', fp=RPI_C0402)
C('C4', '15p', 'XOUT_R', 'GND', 'mcu', fp=RPI_C0402)
R('R2', '1k', 'XOUT', 'XOUT_R', 'mcu', fp=RPI_R0402)
R('R7', '27', 'USB_DP', 'USB_DP_MCU', 'mcu', fp=RPI_R0402)
R('R8', '27', 'USB_DN', 'USB_DN_MCU', 'mcu', fp=RPI_R0402)
part('U3', 'W25Q128JVSIQ', 'Memory_Flash:W25Q128JVS', 'card:RPi_soic127p790x195-8', 'C97521',
     {1: 'FLASH_SS', 2: 'QSPI_SD1', 3: 'QSPI_SD2', 4: 'GND', 5: 'QSPI_SD0', 6: 'QSPI_SCLK',
      7: 'QSPI_SD3', 8: '+3V3'}, 'mcu')
C('C2', '100n', '+3V3', 'GND', 'mcu', fp=RPI_C0402)
R('R10', '0', 'QSPI_SS', 'FLASH_SS', 'mcu', fp=RPI_R0402)
R('R6', '1k', 'QSPI_SS', 'BOOT', 'mcu', fp=RPI_R0402, desc='BOOTSEL strap, button pulls QSPI_SS low')
part('SW1', 'TS-1187A-B-A-B', 'Switch:SW_Push', 'Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A', 'C318884',
     {1: 'BOOT', 2: 'GND'}, 'mcu', 'the only button: BOOTSEL at power-up, user input at runtime')
part('TP1', 'SWCLK', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm', '', {1: 'SWCLK'}, 'mcu')
part('TP2', 'SWDIO', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm', '', {1: 'SWDIO'}, 'mcu')
part('TP3', 'GND', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm', '', {1: 'GND'}, 'mcu')

# ---- LED matrix driver -------------------------------------------------------
# SDB tied to VCC: after power-up the chip sits in software shutdown with every LED off, so the
# firmware decides when the matrix lights. INTB (auto-play interrupt) is not used.
is31 = {1: 'CA9', 2: 'VBUS', 3: 'VBUS', 4: None, 5: 'GND', 6: 'LED_REXT',
        16: 'LED_CFILT', 17: 'LED_IN', 18: 'GND', 19: 'SDA', 20: 'SCL', 29: 'GND'}
for k in range(1, 10):
    is31[6 + k] = f'CB{k}'          # pins 7..15
for k in range(1, 9):
    is31[20 + k] = f'CA{k}'         # pins 21..28
part('U5', 'IS31FL3731', 'Driver_LED:IS31FL3731-QF', 'Package_DFN_QFN:QFN-28-1EP_4x4mm_P0.4mm_EP2.4x2.4mm_ThermalVias',
     'C191206', is31, 'led', 'VCC from VBUS keeps LED current out of the 3.3 V LDO')
R('R15', '33k', 'LED_REXT', 'GND', 'led', desc='ILED avg = 64.7/REXT = 1.96 mA, all 144 on = 0.28 A')
R('R13', '4.7k', 'SDA', '+3V3', 'led')
R('R14', '4.7k', 'SCL', '+3V3', 'led')
C('C21', '1u', 'VBUS', 'GND', 'led')
C('C22', '100n', 'VBUS', 'GND', 'led')
C('C23', '100n', 'LED_CFILT', 'GND', 'led')
C('C24', '100n', 'LED_IN', 'GND', 'led', desc='audio input unused, AC-grounded')
for r in range(MATRIX_ROWS):
    for c in range(MATRIX_COLS):
        k, a = led_nets(r, c)
        part(led_ref(r, c), 'red', 'Device:LED', 'card:LED_0603_KT', 'C2286', {1: k, 2: a}, 'matrix')

# ---- EEPROM "black box" --------------------------------------------------------
part('U7', 'AT24C02C-SSHM-T', 'Memory_EEPROM:AT24CS02-SSHM', 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm', 'C6203',
     {1: 'GND', 2: 'GND', 3: 'GND', 4: 'GND', 5: 'SDA', 6: 'SCL', 7: 'EE_WP', 8: '+3V3'}, 'misc',
     'I2C 0x50, the black box of the story')
C('C25', '100n', '+3V3', 'GND', 'misc')

# ---- light sensor ----------------------------------------------------------------
part('U6', 'TEMT6200FX01', 'card:TEMT6200FX01', 'card:TEMT6200FX01', 'C143695', {1: 'LUX', 2: '+3V3'}, 'misc',
     'Vishay phototransistor, 23 uA at 100 lx typ; pad 1 = emitter as in the JLC/EasyEDA footprint')
R('R17', '10k', 'LUX', 'GND', 'misc', desc='saturates near 1400 lx (typ part)')
R('R18', '1k', 'LUX', 'LUX_RANGE', 'misc', desc='LUX_RANGE low: 0.9 k load, up to ~15000 lx')
C('C26', '100n', 'LUX', 'GND', 'misc')

# ---- buzzer ------------------------------------------------------------------------
part('BZ1', 'MLT-8530', 'Device:Buzzer', 'card:Buzzer_MLT-8530', 'C94599', {1: '+3V3', 2: 'BUZZ_N'}, 'misc',
     '16 ohm magnetic, 2.7 kHz, rated 2.5..4.5 V so it runs from 3.3 V; PWM only, never DC')
part('Q1', 'MMBT3904', 'Transistor_BJT:MMBT3904', 'Package_TO_SOT_SMD:SOT-23', 'C20526',
     {1: 'BUZZ_B', 2: 'GND', 3: 'BUZZ_N'}, 'misc')
part('D145', '1N4148WS', 'Diode:1N4148WS', 'Diode_SMD:D_SOD-323', 'C2128', {1: '+3V3', 2: 'BUZZ_N'}, 'misc')
R('R19', '470', 'BUZZ', 'BUZZ_B', 'misc',
  desc='~4.7 mA base current saturates Q1 at the ~120 mA coil peak even at hFE min (30)')
R('R20', '10k', 'BUZZ_B', 'GND', 'misc')


def all_nets():
    nets = {}
    for ref, p in PARTS.items():
        for pin, net in p['nets'].items():
            if net:
                nets.setdefault(net, []).append((ref, pin))
    return nets


if __name__ == '__main__':
    nets = all_nets()
    print(len(PARTS), 'parts,', len(nets), 'nets')
    for n in sorted(nets):
        if len(nets[n]) < 2:
            print('SINGLE-PIN NET', n, nets[n])
    for n in sorted(nets, key=lambda k: -len(nets[k]))[:12]:
        print(f'{n:12s} {len(nets[n])}')
