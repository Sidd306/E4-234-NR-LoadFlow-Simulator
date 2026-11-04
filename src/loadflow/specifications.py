import numpy as np


def calculate_specified_power(network):
    network.validate()

    n = len(network.buses)

    bus_index = {
        bus.bus_id: i for i, bus in enumerate(network.buses)
    }

    P_spec = np.zeros(n)
    Q_spec = np.zeros(n)

    # Add generator power
    for generator in network.generators:
        if not generator.status:
            continue

        i = bus_index[generator.bus_id]

        P_spec[i] += generator.p_mw / network.base_mva
        Q_spec[i] += generator.q_mvar / network.base_mva

    # Subtract load power
    for load in network.loads:
        if not load.status:
            continue

        i = bus_index[load.bus_id]

        P_spec[i] -= load.p_mw / network.base_mva
        Q_spec[i] -= load.q_mvar / network.base_mva

    return P_spec, Q_spec

    