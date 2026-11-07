"""Export supported E4234 networks to MATPOWER v2 case matrices.

Intentionally rejects non-PQ loads: silently writing a ZIP load as constant
power would change the model. Import/roundtrip is supported by the project's
matpower_import.load_matpower_case function.
"""
import math
import re
from pathlib import Path


def _matrix(rows):
    return '\n'.join('    ' + ' '.join(f'{float(v):.15g}' for v in row) + ';' for row in rows)


def network_to_matpower(network, case_name='case_export'):
    network.validate()
    if not re.fullmatch(r'[A-Za-z]\w*', case_name):
        raise ValueError('MATPOWER case name must be a MATLAB identifier')
    if any(ld.status and ld.model != 'PQ' for ld in network.loads):
        raise ValueError('MATPOWER export supports constant-PQ loads only; convert ZIP/Z loads explicitly first')

    rows_bus = []
    buses = sorted(network.buses, key=lambda b: b.bus_id)
    for bus in buses:
        pg_load = sum(l.p_mw for l in network.loads if l.status and l.bus_id == bus.bus_id)
        qg_load = sum(l.q_mvar for l in network.loads if l.status and l.bus_id == bus.bus_id)
        gs = sum(sh.g_pu * network.base_mva for sh in network.shunts if sh.status and sh.bus_id == bus.bus_id)
        bs = sum(sh.b_pu * network.base_mva for sh in network.shunts if sh.status and sh.bus_id == bus.bus_id)
        rows_bus.append([bus.bus_id, {'PQ':1, 'PV':2, 'Slack':3}[bus.bus_type],
                         pg_load, qg_load, gs, bs, 1, bus.voltage_mag_pu,
                         math.degrees(bus.voltage_angle_rad), bus.nominal_kv,
                         1, bus.vmax_pu, bus.vmin_pu])

    rows_gen = []
    for g in network.generators:
        # MATPOWER gen columns: bus Pg Qg Qmax Qmin Vg mBase status Pmax Pmin
        # followed by unused columns through index 20.
        rows_gen.append([g.bus_id, g.p_mw, g.q_mvar, g.q_max_mvar,
                         g.q_min_mvar, g.voltage_setpoint_pu, network.base_mva,
                         int(g.status), max(g.p_mw, 0.0), min(g.p_mw, 0.0)] + [0] * 11)
    slack_buses = {b.bus_id for b in buses if b.bus_type == 'Slack'}
    for b in buses:
        if b.bus_id in slack_buses and not any(g.status and g.bus_id == b.bus_id for g in network.generators):
            # Export the implicit external grid explicitly for MATPOWER.
            rows_gen.append([b.bus_id, 0, 0, 99999, -99999, b.voltage_mag_pu,
                             network.base_mva, 1, 99999, -99999] + [0] * 11)
    if not rows_gen:
        raise ValueError('MATPOWER requires at least one generator or external grid')
    rows_branch = []
    for line in network.lines:
        rows_branch.append([line.from_bus, line.to_bus, line.r_pu, line.x_pu,
                            line.b_pu, line.rate_mva, 0, 0, 0, 0,
                            int(line.status), -360, 360])
    for tr in network.transformers:
        # MATPOWER stores the off-nominal complex tap on the from terminal.
        # Reverse bus orientation for a to-side tap without changing its physics.
        export_from, export_to = ((tr.from_bus, tr.to_bus)
                                 if tr.tap_side == 'from'
                                 else (tr.to_bus, tr.from_bus))
        rows_branch.append([export_from, export_to, tr.r_pu, tr.x_pu,
                            tr.b_pu, tr.rate_mva, 0, 0, tr.tap_ratio,
                            tr.phase_shift_deg, int(tr.status), -360, 360])

    return (f'function mpc = {case_name}\n'
            "% MATPOWER version 2 case, exported by E4234 Load Flow\n"
            "mpc.version = '2';\n"
            f'mpc.baseMVA = {network.base_mva:.15g};\n'
            'mpc.bus = [\n' + _matrix(rows_bus) + '\n];\n'
            'mpc.gen = [\n' + _matrix(rows_gen) + '\n];\n'
            'mpc.branch = [\n' + _matrix(rows_branch) + '\n];\n')


def save_matpower_case(path, network):
    path = Path(path)
    path.write_text(network_to_matpower(network, path.stem), encoding='utf-8')
