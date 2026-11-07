"""Validate loadflow against PYPOWER using identical MATPOWER case matrices.

Run from the project root: py -3.14 validate.py
Requires: py -3.14 -m pip install PYPOWER
"""
import re
import sys
from pathlib import Path

import numpy as np
from pypower.api import ppoption, runpf
from pypower.idx_bus import BUS_I, VM, VA, PD, QD, GS, BS
from pypower.idx_gen import GEN_BUS, PG, QG, GEN_STATUS
from pypower.idx_brch import F_BUS, T_BUS, BR_STATUS, PF, QF, PT, QT

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from loadflow.matpower_import import load_matpower_case, read_matrix
from loadflow.solver import solve_newton_raphson

DATA = ROOT / 'data'
CASES = ('case14.m', 'case_ieee30.m', 'case57.m', 'case118.m')


def read_ppc(filepath):
    """Read the same numeric matrices as our MATPOWER importer; do not convert pu to ohms."""
    content = Path(filepath).read_text(encoding='utf-8')
    m = re.search(r'mpc\.baseMVA\s*=\s*([0-9.eE+-]+)\s*;', content)
    if m is None:
        raise ValueError('mpc.baseMVA not found')
    return {
        'version': '2',
        'baseMVA': float(m.group(1)),
        'bus': np.asarray(read_matrix(content, 'bus', 13), dtype=float),
        'gen': np.asarray(read_matrix(content, 'gen', 10), dtype=float),
        'branch': np.asarray(read_matrix(content, 'branch', 13), dtype=float),
    }


def max_abs(values):
    return float(max((abs(x) for x in values), default=0.0))


def compare_case(filename):
    print(f'\n{"=" * 55}\nVALIDATING {filename}\n{"=" * 55}')
    path = DATA / filename
    ppc = read_ppc(path)
    network = load_matpower_case(path)

    # Preserve PV/slack voltage setpoints and set PQ initial voltages to 1 pu.
    for bus in network.buses:
        bus.voltage_angle_rad = 0.0
        if bus.bus_type == 'PQ':
            bus.voltage_mag_pu = 1.0

    # Use unconstrained reactive power in both implementations for the same AC PF problem.
    for gen in network.generators:
        gen.q_min_mvar = -1e6
        gen.q_max_mvar = 1e6

    ours = solve_newton_raphson(network, tolerance=1e-9, max_iterations=30)
    if not ours['converged']:
        print('OUR SOLVER: NOT CONVERGED')
        return False

    opts = ppoption(PF_ALG=1, PF_TOL=1e-10, PF_MAX_IT=30,
                    ENFORCE_Q_LIMS=False, VERBOSE=0, OUT_ALL=0)
    ref, success = runpf(ppc, opts)
    if not success:
        print('PYPOWER: NOT CONVERGED')
        return False

    ours_by_bus = {int(bus.bus_id): i for i, bus in enumerate(network.buses)}
    ref_by_bus = {int(row[BUS_I]): row for row in ref['bus']}
    if set(ours_by_bus) != set(ref_by_bus):
        raise ValueError('Bus IDs differ between the two solvers')

    # Identify the slack bus
    slack_bus = next(
        bus for bus in network.buses
        if bus.bus_type == 'Slack'
    )

    slack_id = int(slack_bus.bus_id)
    slack_idx = ours_by_bus[slack_id]

    # Slack angles in degrees
    our_slack_angle = np.rad2deg(
        ours['voltage_angle'][slack_idx]
    )

    ref_slack_angle = ref_by_bus[slack_id][VA]

    print("Our slack angle:", our_slack_angle)
    print("PYPOWER slack angle:", ref_slack_angle)

    # Compare voltages and relative angles
    vm_errors, va_errors = [], []

    for bid, i in ours_by_bus.items():
        r = ref_by_bus[bid]

        vm_errors.append(
            ours['voltage_mag'][i] - r[VM]
        )

        our_angle = np.rad2deg(ours['voltage_angle'][i])
        ref_angle = r[VA]

        our_relative = our_angle - our_slack_angle
        ref_relative = ref_angle - ref_slack_angle

        va_errors.append(our_relative - ref_relative)
        
    # Generator results are aggregated by bus in our project.
    our_gens = {int(row['bus_id']): row for row in ours['generator_outputs']}
    ref_gens = {}
    for g in ref['gen']:
        if g[GEN_STATUS] <= 0:
            continue
        bid = int(g[GEN_BUS])
        agg = ref_gens.setdefault(bid, [0.0, 0.0])
        agg[0] += float(g[PG])
        agg[1] += float(g[QG])
    gen_errors = []
    missing_gens = []
    for bid, pq in ref_gens.items():
        if bid not in our_gens:
            missing_gens.append(bid)
            continue
        gen_errors.extend([our_gens[bid]['P_generation_mw'] - pq[0],
                           our_gens[bid]['Q_generation_mvar'] - pq[1]])

    # The project outputs all lines first, then transformers, while
    # PYPOWER preserves MATPOWER branch-row order. Match by endpoints.
    # For parallel circuits, match the best remaining candidate by complex flows.
    ref_active = [b for b in ref['branch'] if b[BR_STATUS] > 0]
    remaining = list(ours['branch_flows'])
    branch_errors = []
    unmatched = []
    for row_index, b in enumerate(ref_active):
        f, t = int(b[F_BUS]), int(b[T_BUS])
        candidates = []
        for k, o in enumerate(remaining):
            direct = (int(o['from_bus']), int(o['to_bus'])) == (f, t)
            reverse = (int(o['from_bus']), int(o['to_bus'])) == (t, f)
            if direct or reverse:
                vals = ([o['P_from_mw'], o['Q_from_mvar'], o['P_to_mw'], o['Q_to_mvar']]
                        if direct else [o['P_to_mw'], o['Q_to_mvar'], o['P_from_mw'], o['Q_from_mvar']])
                err = max_abs(np.asarray(vals) - b[[PF, QF, PT, QT]])
                candidates.append((err, k, vals))
        if not candidates:
            unmatched.append(f'reference row {row_index}: {f}->{t}')
            continue
        _, k, vals = min(candidates, key=lambda x: x[0])
        branch_errors.extend(np.asarray(vals) - b[[PF, QF, PT, QT]])
        remaining.pop(k)
    if remaining:
        unmatched.extend(f'extra project branch {o["from_bus"]}->{o["to_bus"]}' for o in remaining)

    # Total losses: branch terminal injections + shunt absorption at solved V^2.
    p_branch = sum(float(b[PF] + b[PT]) for b in ref_active)
    q_branch = sum(float(b[QF] + b[QT]) for b in ref_active)
    p_shunt = sum(float(row[GS] * row[VM]**2) for row in ref['bus'])
    q_shunt = sum(float(-row[BS] * row[VM]**2) for row in ref['bus'])
    p_loss_ref = p_branch + p_shunt
    q_loss_ref = q_branch + q_shunt
    p_loss_err = abs(ours['system_summary']['P_loss_mw'] - p_loss_ref)
    q_loss_err = abs(ours['system_summary']['Q_loss_mvar'] - q_loss_ref)

    errors = {
        'Voltage magnitude (pu)': max_abs(vm_errors),
        'Voltage angle (deg)': max_abs(va_errors),
        'Generator output (MW/MVAr)': max_abs(gen_errors),
        'Branch flow (MW/MVAr)': max_abs(branch_errors),
        'Active loss (MW)': p_loss_err,
        'Reactive loss (MVAr)': q_loss_err,
    }
    checks = {
        'Voltage magnitude': errors['Voltage magnitude (pu)'] <= 1e-4,
        'Voltage angle': errors['Voltage angle (deg)'] <= .01,
        'Generator output': errors['Generator output (MW/MVAr)'] <= .01 and not missing_gens,
        'Branch flow': errors['Branch flow (MW/MVAr)'] <= .01 and not unmatched,
        'Active loss': p_loss_err <= .001 * max(abs(p_loss_ref), 1.0),
        'Reactive loss': q_loss_err <= .001 * max(abs(q_loss_ref), 1.0),
    }
    print(f'Our solver iterations: {ours["iterations"]}')
    print('MAXIMUM ABSOLUTE ERRORS')
    for label, value in errors.items():
        print(f'  {label}: {value:.9e}')
    if missing_gens:
        print('Missing generator buses:', missing_gens)
    if unmatched:
        print('Unmatched branches:', unmatched[:10])
    print('VALIDATION CHECKS')
    for label, ok in checks.items():
        print(f'  {label}: {"PASS" if ok else "FAIL"}')
    passed = all(checks.values())
    print('OVERALL:', 'PASS' if passed else 'CHECK REQUIRED')
    return passed


if __name__ == '__main__':
    all_ok = True
    for filename in CASES:
        try:
            all_ok = compare_case(filename) and all_ok
        except Exception as exc:
            import traceback
            print(f'VALIDATION ERROR for {filename}: {exc}')
            traceback.print_exc()
            all_ok = False
    sys.exit(0 if all_ok else 1)
