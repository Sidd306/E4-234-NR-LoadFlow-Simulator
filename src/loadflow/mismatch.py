import numpy as np


def calculate_mismatch(network, P_spec, Q_spec, P_calc, Q_calc):

    p_indices = []
    q_indices = []

    for i, bus in enumerate(network.buses):

        if bus.bus_type in ("PV", "PQ"):
            p_indices.append(i)

        if bus.bus_type == "PQ":
            q_indices.append(i)

    delta_P = P_spec[p_indices] - P_calc[p_indices]
    delta_Q = Q_spec[q_indices] - Q_calc[q_indices]

    mismatch = np.concatenate((delta_P, delta_Q))

    return mismatch, p_indices, q_indices