
import numpy as np
import math


def calculate_line_flows(network, voltage_mag, voltage_angle):

    V = np.asarray(voltage_mag) * np.exp(
        1j * np.asarray(voltage_angle)
    )

    bus_index = {
        bus.bus_id: i
        for i, bus in enumerate(network.buses)
    }

    results = []

    # Transmission line flows
    for line in network.lines:

        if not line.status:
            continue

        i = bus_index[line.from_bus]
        j = bus_index[line.to_bus]

        z = complex(line.r_pu, line.x_pu)
        y = 1 / z
        y_sh = 1j * line.b_pu / 2

        I_from = (V[i] - V[j]) * y + V[i] * y_sh
        I_to = (V[j] - V[i]) * y + V[j] * y_sh

        S_from = V[i] * np.conj(I_from) * network.base_mva
        S_to = V[j] * np.conj(I_to) * network.base_mva

        S_loss = S_from + S_to

        if line.rate_mva > 0:
            loading = max(abs(S_from), abs(S_to)) / line.rate_mva * 100
        else:
            loading = None

        results.append({
            "element_type": "Line",
            "from_bus": line.from_bus,
            "to_bus": line.to_bus,
            "P_from_mw": S_from.real,
            "Q_from_mvar": S_from.imag,
            "P_to_mw": S_to.real,
            "Q_to_mvar": S_to.imag,
            "P_loss_mw": S_loss.real,
            "Q_loss_mvar": S_loss.imag,
            "loading_percent": loading
        })

    # Transformer flows
    for transformer in network.transformers:

        if not transformer.status:
            continue

        i = bus_index[transformer.from_bus]
        j = bus_index[transformer.to_bus]

        z = complex(transformer.r_pu, transformer.x_pu)
        y = 1 / z

        phi = math.radians(transformer.phase_shift_deg)

        a = transformer.tap_ratio * complex(
            math.cos(phi), math.sin(phi)
        )

        # Currents at both transformer ends
        I_from = (
            y / abs(a)**2 * V[i]
            - y / np.conj(a) * V[j]
        )

        I_to = (
            -y / a * V[i]
            + y * V[j]
        )

        # Complex powers in MW and MVAr
        S_from = V[i] * np.conj(I_from) * network.base_mva
        S_to = V[j] * np.conj(I_to) * network.base_mva

        S_loss = S_from + S_to

        if transformer.rate_mva > 0:
            loading = max(abs(S_from), abs(S_to)) / transformer.rate_mva * 100
        else:
            loading = None

        results.append({
            "element_type": "Transformer",
            "from_bus": transformer.from_bus,
            "to_bus": transformer.to_bus,
            "P_from_mw": S_from.real,
            "Q_from_mvar": S_from.imag,
            "P_to_mw": S_to.real,
            "Q_to_mvar": S_to.imag,
            "P_loss_mw": S_loss.real,
            "Q_loss_mvar": S_loss.imag,
            "loading_percent": loading
        })

    return results
