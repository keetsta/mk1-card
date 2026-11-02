"""Write card.kicad_pro: JLCPCB 4-layer design rules and net classes.

Values follow https://jlcpcb.com/capabilities/pcb-capabilities (4 layers, 1 oz): 0.09 mm track/space,
0.2 mm via hole to track, vias with a 0.25 mm hole and >= 0.45 mm pad at no extra cost, 0.3 mm copper
to edge here (JLC allows 0.2), silkscreen >= 0.15 mm lines and 1.0 mm text.
"""
import json, os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def netclass(name, clearance, track, via_d, via_drill, color=''):
    return {
        'name': name, 'clearance': clearance, 'track_width': track, 'via_diameter': via_d, 'via_drill': via_drill,
        'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'diff_pair_width': 0.2, 'diff_pair_gap': 0.25,
        'diff_pair_via_gap': 0.25, 'wire_width': 6, 'bus_width': 12, 'line_style': 0, 'pcb_color': color,
        'schematic_color': 'rgba(0, 0, 0, 0.000)', 'priority': 2147483647 if name == 'Default' else 0,
        'tuning_profile': '',
    }


pro = {
    'board': {
        'design_settings': {
            'defaults': {
                'apply_defaults_to_fp_fields': False, 'apply_defaults_to_fp_shapes': False,
                'apply_defaults_to_fp_text': False,
                'board_outline_line_width': 0.1, 'copper_line_width': 0.2, 'copper_text_size_h': 1.5,
                'copper_text_size_v': 1.5, 'copper_text_thickness': 0.3, 'courtyard_line_width': 0.05,
                'fab_line_width': 0.1, 'fab_text_size_h': 1.0, 'fab_text_size_v': 1.0, 'fab_text_thickness': 0.15,
                'other_line_width': 0.1, 'silk_line_width': 0.15, 'silk_text_size_h': 1.0, 'silk_text_size_v': 1.0,
                'silk_text_thickness': 0.15,
                'pads': {'drill': 0.0, 'height': 1.0, 'width': 1.0},
                'zones': {'min_clearance': 0.2},
            },
            'diff_pair_dimensions': [],
            'drc_exclusions': [],
            'meta': {'version': 2},
            'rule_severities': {
                'lib_footprint_issues': 'ignore', 'lib_footprint_mismatch': 'ignore',
                'silk_overlap': 'ignore', 'silk_edge_clearance': 'warning', 'silk_over_copper': 'warning',
                'text_height': 'warning', 'text_thickness': 'warning', 'footprint_type_mismatch': 'ignore',
                'npth_inside_courtyard': 'ignore', 'pth_inside_courtyard': 'ignore',
                'too_many_vias': 'ignore', 'via_dangling': 'warning', 'track_dangling': 'warning',
                'isolated_copper': 'warning', 'starved_thermal': 'warning', 'clearance': 'error',
                'courtyards_overlap': 'error', 'hole_clearance': 'error', 'copper_edge_clearance': 'error',
                'unconnected_items': 'error', 'shorting_items': 'error', 'tracks_crossing': 'error',
                'solder_mask_bridge': 'error', 'missing_courtyard': 'ignore', 'malformed_courtyard': 'warning',
            },
            'rules': {
                'max_error': 0.005, 'min_clearance': 0.1, 'min_connection': 0.0,
                'min_copper_edge_clearance': 0.3, 'min_groove_width': 0.0, 'min_hole_clearance': 0.2,
                'min_hole_to_hole': 0.25, 'min_microvia_diameter': 0.2, 'min_microvia_drill': 0.1,
                'min_resolved_spokes': 1, 'min_silk_clearance': 0.0, 'min_text_height': 1.0,
                'min_text_thickness': 0.15, 'min_through_hole_diameter': 0.2, 'min_track_width': 0.12,
                'min_via_annular_width': 0.09, 'min_via_diameter': 0.45, 'solder_mask_to_copper_clearance': 0.0,
                'use_height_for_length_calcs': True,
            },
            'teardrop_options': [{'td_onpthpad': True, 'td_onroundshapesonly': False, 'td_onsmdpad': True,
                                  'td_ontrackend': False, 'td_onvia': True}],
            'track_widths': [0.0, 0.15, 0.2, 0.3, 0.4, 0.5],
            'via_dimensions': [{'diameter': 0.0, 'drill': 0.0}, {'diameter': 0.45, 'drill': 0.25},
                               {'diameter': 0.5, 'drill': 0.25}, {'diameter': 0.6, 'drill': 0.3}],
            'zones_allow_external_fillets': False,
        },
        'ipc2581': {'dist': '', 'distpn': '', 'internal_id': '', 'mfg': '', 'mpn': ''},
        'layer_pairs': [],
        'layer_presets': [],
        'viewports': [],
    },
    'boards': [],
    'cvpcb': {'equivalence_files': []},
    'libraries': {'pinned_footprint_libs': [], 'pinned_symbol_libs': []},
    'meta': {'filename': 'card.kicad_pro', 'version': 3},
    'net_settings': {
        'classes': [
            netclass('Default', 0.15, 0.2, 0.5, 0.25),
            netclass('Power', 0.14, 0.4, 0.6, 0.3),
        ],
        'meta': {'version': 4},
        'net_colors': None,
        'netclass_assignments': None,
        'netclass_patterns': [{'netclass': 'Power', 'pattern': n} for n in ('VBUS', '+3V3', 'GND', '+1V1')],
    },
    'pcbnew': {'last_paths': {}, 'page_layout_descr_file': ''},
    'schematic': {'legacy_lib_dir': '', 'legacy_lib_list': []},
    'sheets': [],
    'text_variables': {},
}

with open(os.path.join(PROJ, 'card.kicad_pro'), 'w', encoding='utf-8', newline='\n') as f:
    json.dump(pro, f, indent=2)

# JLC: 0.2 mm from a via hole to copper is fine, component holes want 0.28 (0.35 recommended)
DRU = '''(version 1)
(rule "JLC component holes to copper"
	(constraint hole_clearance (min 0.3mm))
	(condition "A.Type == 'Pad' && (A.Pad_Type == 'Through-hole' || A.Pad_Type == 'NPTH, mechanical')"))
'''
with open(os.path.join(PROJ, 'card.kicad_dru'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(DRU)
print('wrote card.kicad_pro and card.kicad_dru')
