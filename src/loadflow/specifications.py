import numpy as np


def calculate_specified_power(network, voltage_mag=None):
    network.validate()

    n = len(network.buses)

    bus_index = {
        bus.bus_id: i for i, bus in enumerate(network.buses)
    }

    if voltage_mag is None:
        voltage_mag = np.ones(n)
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

        p_load, q_load = load.power_at_voltage(voltage_mag[i])
        P_spec[i] -= p_load / network.base_mva
        Q_spec[i] -= q_load / network.base_mva

    return P_spec, Q_spec

    

def calculate_specified_power_voltage_derivatives(network, voltage_mag):
    """d(P_spec)/d|V|, d(Q_spec)/d|V| in pu for each bus."""
    bus_index = {bus.bus_id: i for i, bus in enumerate(network.buses)}
    dp = np.zeros(len(network.buses))
    dq = np.zeros(len(network.buses))
    for load in network.loads:
        if load.status:
            i = bus_index[load.bus_id]
            a, b = load.power_derivative(voltage_mag[i])
            dp[i] -= a / network.base_mva
            dq[i] -= b / network.base_mva
    return dp, dq
