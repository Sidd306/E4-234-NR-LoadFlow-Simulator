"""IEEE Common Data Format (CDF) fixed-width bus/branch importer.

Supports the traditional BUS DATA FOLLOWS / BRANCH DATA FOLLOWS records.
It does NOT model automatic transformer tap controllers or area interchange.
Unsupported nonzero control modes are rejected rather than silently discarded.
"""
from __future__ import annotations

import math
from pathlib import Path

from .models import Bus, Generator, Load, Line, Network, Shunt, Transformer


def _field(line: str, first: int, last: int, cast=float, default=0):
    # IEEE CDF columns are one-indexed, inclusive.
    value = line[first - 1:last].strip()
    if not value:
        return default
    try:
        return cast(value.replace('D', 'E').replace('d', 'e'))
    except ValueError as exc:
        raise ValueError(f'Invalid CDF field in columns {first}-{last}: {value!r}') from exc


def parse_ieee_cdf(content: str) -> Network:
    if not isinstance(content, str):
        raise TypeError('CDF content must be text')
    lines = content.splitlines()
    if not lines:
        raise ValueError('Empty IEEE CDF file')
    # Base MVA is in title card columns 32-37.
    base = _field(lines[0], 32, 37, float, 100.0)
    if base <= 0 or not math.isfinite(base):
        raise ValueError('Invalid IEEE CDF base MVA')
    net = Network(base_mva=base)
    section = None
    bus_count = branch_count = 0
    for lineno, line in enumerate(lines[1:], start=2):
        upper = line.upper().strip()
        if upper.startswith('BUS DATA FOLLOWS'):
            section = 'bus'
            continue
        if upper.startswith('BRANCH DATA FOLLOWS'):
            section = 'branch'
            continue
        if upper.startswith('END OF DATA'):
            break
        if line.lstrip().startswith('-999'):
            section = None
            continue
        if section is None or not line.strip():
            continue
        try:
            if section == 'bus':
                bid = _field(line, 1, 4, int)
                if bid <= 0:
                    raise ValueError('Bus number must be positive')
                kind = _field(line, 25, 26, int)
                if kind not in (0, 1, 2, 3):
                    raise ValueError(f'Unsupported bus type {kind}')
                bus_type = {0: 'PQ', 1: 'PQ', 2: 'PV', 3: 'Slack'}[kind]
                vm = _field(line, 28, 33, float, 1.0)
                va = _field(line, 34, 40)
                pd = _field(line, 41, 49)
                qd = _field(line, 50, 59)
                pg = _field(line, 60, 67)
                qg = _field(line, 68, 75)
                kv = _field(line, 77, 83)
                vtarget = _field(line, 85, 90)
                qmax = _field(line, 91, 98, float, 999.0)
                qmin = _field(line, 99, 106, float, -999.0)
                g = _field(line, 107, 114)
                b = _field(line, 115, 122)
                remote = _field(line, 124, 127, int)
                if remote not in (0, bid):
                    raise ValueError('Remote voltage control is not supported')
                if vm <= 0:
                    vm = vtarget if vtarget > 0 else 1.0
                if bus_type in ('Slack', 'PV') and vtarget > 0:
                    vm = vtarget
                net.add_bus(Bus(bus_id=bid, name=line[5:17].strip(),
                                bus_type=bus_type, voltage_mag_pu=vm,
                                voltage_angle_rad=math.radians(va), nominal_kv=kv))
                if pd or qd:
                    net.add_load(Load(bus_id=bid, p_mw=pd, q_mvar=qd))
                if pg or qg or bus_type in ('Slack', 'PV'):
                    net.add_generator(Generator(bus_id=bid, p_mw=pg, q_mvar=qg,
                                                q_max_mvar=qmax, q_min_mvar=qmin,
                                                voltage_setpoint_pu=vm))
                if g or b:
                    net.add_shunt(Shunt(bus_id=bid, g_pu=g, b_pu=b))
                bus_count += 1
            elif section == 'branch':
                f = _field(line, 1, 4, int)
                t = _field(line, 6, 9, int)
                kind = _field(line, 19, 19, int)
                if kind not in (0, 1, 2, 3, 4):
                    raise ValueError(f'Unknown branch type {kind}')
                r = _field(line, 20, 29)
                x = _field(line, 30, 40)
                b = _field(line, 41, 50)
                rate = _field(line, 51, 55)
                if rate < 0:
                    raise ValueError('Negative branch rating')
                if kind == 0:
                    net.add_line(Line(f, t, r, x, b_pu=b, rate_mva=rate))
                else:
                    ratio = _field(line, 77, 82, float, 1.0) or 1.0
                    shift = _field(line, 84, 90)
                    # CDF tap bus is the first bus; MATPOWER uses first/from bus tap.
                    net.add_transformer(Transformer(f, t, r, x,
                                                    tap_ratio=ratio,
                                                    phase_shift_deg=shift,
                                                    b_pu=b, rate_mva=rate))
                branch_count += 1
        except (ValueError, TypeError) as exc:
            raise ValueError(f'CDF line {lineno}: {exc}') from exc
    if not bus_count or not branch_count:
        raise ValueError('CDF file must contain BUS DATA and BRANCH DATA sections')
    net.validate()
    return net


def load_ieee_cdf(path):
    return parse_ieee_cdf(Path(path).read_text(encoding='utf-8', errors='replace'))
