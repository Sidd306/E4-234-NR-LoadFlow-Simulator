
import re
import math
from pathlib import Path

from loadflow.models import (
    Network, Bus, Generator, Load, Line, Transformer, Shunt
)


def read_matrix(content, name, min_columns):
    pattern = rf"mpc\.{name}\s*=\s*\[(.*?)\];"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        raise ValueError(f"Matrix mpc.{name} not found")

    block = re.sub(r"%[^\n]*", "", match.group(1))
    rows = []

    for line in block.split(";"):
        line = line.strip()
        if not line:
            continue

        try:
            row = [float(value) for value in line.split()]
        except ValueError as exc:
            raise ValueError(
                f"Invalid numeric data in mpc.{name}: {line}"
            ) from exc

        if len(row) < min_columns:
            raise ValueError(
                f"Invalid {name} row: expected at least "
                f"{min_columns} columns, got {len(row)}: {row}"
            )

        rows.append(row)

    return rows


def load_matpower_case(filepath):
    content = Path(filepath).read_text(encoding="utf-8")

    base_match = re.search(
        r"mpc\.baseMVA\s*=\s*([0-9.eE+-]+)\s*;",
        content
    )

    if not base_match:
        raise ValueError("baseMVA not found")

    network = Network(base_mva=float(base_match.group(1)))

    bus_data = read_matrix(content, "bus", 13)
    gen_data = read_matrix(content, "gen", 10)
    branch_data = read_matrix(content, "branch", 13)

    # Bus data
    for row in bus_data:
        bus_id = int(row[0])
        bus_type_code = int(row[1])

        bus_types = {
            1: "PQ",
            2: "PV",
            3: "Slack"
        }

        if bus_type_code not in bus_types:
            raise ValueError(
                f"Unsupported MATPOWER bus type {bus_type_code} "
                f"at bus {bus_id}"
            )

        voltage_mag = row[7]
        voltage_angle = math.radians(row[8])

        network.add_bus(Bus(
            bus_id=bus_id,
            bus_type=bus_types[bus_type_code],
            voltage_mag_pu=voltage_mag,
            voltage_angle_rad=voltage_angle,
            nominal_kv=max(0.0, row[9]),
            vmin_pu=row[12] if row[12] > 0 else 0.95,
            vmax_pu=row[11] if row[11] > 0 else 1.05
        ))

        # MATPOWER Gs is MW consumed at 1 pu.
        # MATPOWER Bs is MVAr injected at 1 pu.
        g_pu = row[4] / network.base_mva
        b_pu = row[5] / network.base_mva

        if g_pu != 0 or b_pu != 0:
            network.add_shunt(Shunt(
                bus_id=bus_id,
                g_pu=g_pu,
                b_pu=b_pu
            ))

        # Constant PQ load
        if row[2] != 0 or row[3] != 0:
            network.add_load(Load(
                bus_id=bus_id,
                p_mw=row[2],
                q_mvar=row[3]
            ))

    # Generator data
    for row in gen_data:
        status = row[7] > 0

        network.add_generator(Generator(
            bus_id=int(row[0]),
            p_mw=row[1],
            q_mvar=row[2],
            q_max_mvar=row[3],
            q_min_mvar=row[4],
            voltage_setpoint_pu=row[5],
            status=status
        ))

    # Apply generator voltage setpoints to PV and Slack buses
    for bus in network.buses:
        if bus.bus_type in ("PV", "Slack"):
            generators = [
                gen for gen in network.generators
                if gen.bus_id == bus.bus_id and gen.status
            ]

            if generators:
                bus.voltage_mag_pu = (
                    generators[0].voltage_setpoint_pu
                )

    # Branch data
    for row in branch_data:
        from_bus = int(row[0])
        to_bus = int(row[1])

        r_pu = row[2]
        x_pu = row[3]
        b_pu = row[4]
        rate_mva = row[5]
        tap_ratio = row[8]
        phase_shift = row[9]
        status = row[10] > 0

        # MATPOWER uses tap = 0 to represent an ordinary line.
        if tap_ratio == 0:
            tap_ratio = 1.0
            is_transformer = False
        else:
            is_transformer = (
                abs(tap_ratio - 1.0) > 1e-12
                or abs(phase_shift) > 1e-12
            )

        if is_transformer:
            network.add_transformer(Transformer(
                from_bus=from_bus,
                to_bus=to_bus,
                r_pu=r_pu,
                x_pu=x_pu,
                tap_ratio=tap_ratio,
                phase_shift_deg=phase_shift,
                rate_mva=rate_mva,
                status=status,
                b_pu=b_pu
            ))
        else:
            network.add_line(Line(
                from_bus=from_bus,
                to_bus=to_bus,
                r_pu=r_pu,
                x_pu=x_pu,
                b_pu=b_pu,
                rate_mva=rate_mva,
                status=status
            ))

    network.validate()
    return network
