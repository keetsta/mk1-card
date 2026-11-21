"""Write card.kicad_pro: JLCPCB 4-layer design rules and net classes.

Values follow https://jlcpcb.com/capabilities/pcb-capabilities (4 layers, 1 oz): 0.09 mm track/space,
0.2 mm via hole to track, vias with a 0.25 mm hole and >= 0.45 mm pad at no extra cost, 0.3 mm copper
to edge here (JLC allows 0.2), silkscreen >= 0.15 mm lines and 1.0 mm text.
"""
import json, os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def netclass(name, clearance, track, via_d, via_drill):
    return {
        'name': name, 'clearance': clearance, 'track_width': track, 'via_diameter': via_d, 'via_drill': via_drill,
        'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'diff_pair_width': 0.2, 'diff_pair_gap': 0.25,
        'diff_pair_via_gap': 0.25, 'wire_width': 6, 'bus_width': 12, 'line_style': 0,
        # unset; KiCad reads an empty string as opaque black
        'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)',
        'priority': 2147483647 if name == 'Default' else 0,
    }


# KiCad's schematic and ERC defaults, as eeschema writes them. Saving a new board in build_pcb.py drops
# these sections, so they are written here rather than kept from the file.
ERC_PIN_MAP = [
    [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2],
    [0, 2, 0, 1, 0, 0, 1, 0, 2, 2, 2, 2],
    [0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 2],
    [0, 1, 0, 0, 0, 0, 1, 1, 2, 1, 1, 2],
    [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2],
    [1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 2],
    [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 2],
    [0, 2, 1, 2, 0, 0, 1, 0, 2, 2, 2, 2],
    [0, 2, 0, 1, 0, 0, 1, 0, 2, 0, 0, 2],
    [0, 2, 1, 1, 0, 0, 1, 0, 2, 0, 0, 2],
    [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
]
ERC_SEVERITY = {
    'error': 'bus_definition_conflict bus_entry_needed bus_to_bus_conflict bus_to_net_conflict different_unit_footprint '
             'different_unit_net duplicate_reference duplicate_sheet_names extra_units hier_label_mismatch '
             'label_dangling missing_power_pin pin_not_connected pin_not_driven power_pin_not_driven unannotated '
             'undefined_netclass unit_value_mismatch unresolved_variable wire_dangling',
    'warning': 'endpoint_off_grid footprint_link_issues global_label_dangling label_multiple_wires lib_symbol_issues '
               'lib_symbol_mismatch missing_bidi_pin missing_input_pin missing_unit multiple_net_names '
               'net_not_bus_member no_connect_connected no_connect_dangling pin_to_pin same_local_global_label '
               'similar_label_and_power similar_labels similar_power unconnected_wire_endpoint',
    'ignore': 'footprint_filter four_way_junction simulation_model_issue single_global_label',
}


def bom_field(label, name, group_by):
    return {'group_by': group_by, 'label': label, 'name': name, 'show': True}


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
    'erc': {
        'erc_exclusions': [],
        'meta': {'version': 0},
        'pin_map': ERC_PIN_MAP,
        'rule_severities': {rule: sev for sev, rules in ERC_SEVERITY.items() for rule in rules.split()},
    },
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
    'schematic': {
        'annotate_start_num': 0,
        'bom_export_filename': '${PROJECTNAME}.csv',
        'bom_fmt_presets': [],
        'bom_fmt_settings': {'field_delimiter': ',', 'keep_line_breaks': False, 'keep_tabs': False, 'name': 'CSV',
                             'ref_delimiter': ',', 'ref_range_delimiter': '', 'string_delimiter': '"'},
        'bom_presets': [],
        'bom_settings': {
            'exclude_dnp': False,
            'fields_ordered': [
                bom_field('Reference', 'Reference', False), bom_field('Qty', '${QUANTITY}', False),
                bom_field('Value', 'Value', True), bom_field('DNP', '${DNP}', True),
                bom_field('Exclude from BOM', '${EXCLUDE_FROM_BOM}', True),
                bom_field('Exclude from Board', '${EXCLUDE_FROM_BOARD}', True),
                bom_field('Footprint', 'Footprint', True), bom_field('Datasheet', 'Datasheet', False),
            ],
            'filter_string': '', 'group_symbols': True, 'include_excluded_from_bom': True,
            'name': 'Default Editing', 'sort_asc': True, 'sort_field': 'Reference',
        },
        'connection_grid_size': 50.0,
        'drawing': {
            'dashed_lines_dash_length_ratio': 12.0, 'dashed_lines_gap_length_ratio': 3.0,
            'default_line_thickness': 6.0, 'default_text_size': 50.0, 'field_names': [],
            'intersheets_ref_own_page': False, 'intersheets_ref_prefix': '', 'intersheets_ref_short': False,
            'intersheets_ref_show': False, 'intersheets_ref_suffix': '', 'junction_size_choice': 3,
            'label_size_ratio': 0.375, 'operating_point_overlay_i_precision': 3,
            'operating_point_overlay_i_range': '~A', 'operating_point_overlay_v_precision': 3,
            'operating_point_overlay_v_range': '~V', 'overbar_offset_ratio': 1.23, 'pin_symbol_size': 25.0,
            'text_offset_ratio': 0.15,
        },
        'legacy_lib_dir': '',
        'legacy_lib_list': [],
        'meta': {'version': 1},
        'net_format_name': '',
        'page_layout_descr_file': '',
        'plot_directory': '',
        'space_save_all_events': True,
        'spice_current_sheet_as_root': False,
        'spice_external_command': 'spice "%I"',
        'spice_model_current_sheet_as_root': True,
        'spice_save_all_currents': False,
        'spice_save_all_dissipations': False,
        'spice_save_all_voltages': False,
        'subpart_first_id': 65,
        'subpart_id_separator': 0,
    },
    'sheets': [],
    'text_variables': {},
}


def merge(into, new):
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(into.get(key), dict):
            merge(into[key], value)
        else:
            into[key] = value
    return into


# KiCad fills the project with its own defaults whenever it saves the board or opens the schematic.
# Keeping those and only setting our values (with KiCad's sorted keys) means neither a build nor
# opening the project in KiCad changes the file.
PRO = os.path.join(PROJ, 'card.kicad_pro')
current = {}
if os.path.exists(PRO):
    with open(PRO, encoding='utf-8') as f:
        current = json.load(f)
with open(PRO, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(merge(current, pro), f, indent=2, sort_keys=True)
    f.write('\n')

# JLC: 0.2 mm from a via hole to copper is fine, component holes want 0.28 (0.35 recommended)
DRU = '''(version 1)
(rule "JLC component holes to copper"
	(constraint hole_clearance (min 0.3mm))
	(condition "A.Type == 'Pad' && (A.Pad_Type == 'Through-hole' || A.Pad_Type == 'NPTH, mechanical')"))
'''
with open(os.path.join(PROJ, 'card.kicad_dru'), 'w', encoding='utf-8', newline='\n') as f:
    f.write(DRU)
print('wrote card.kicad_pro and card.kicad_dru')
