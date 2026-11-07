
def calculate_generator_outputs(network, P_calc, Q_calc, voltage_mag=None):

    bus_index = {
        bus.bus_id: i
        for i, bus in enumerate(network.buses)
    }

    results = []

    for bus in network.buses:

        generators = [
            gen for gen in network.generators
            if gen.bus_id == bus.bus_id and gen.status
        ]

        # A Slack bus represents an external-grid source even when no
        # explicit Generator object was created in the GUI.
        if not generators and bus.bus_type != "Slack":
            continue

        i = bus_index[bus.bus_id]

        # Total active and reactive load at this bus
        v = voltage_mag[i] if voltage_mag is not None else 1.0
        loads = [load.power_at_voltage(v) for load in network.loads
                 if load.bus_id == bus.bus_id and load.status]
        P_load = sum(p for p, q in loads)
        Q_load = sum(q for p, q in loads)

        # Total generation = calculated injection + load
        P_generation = P_calc[i] * network.base_mva + P_load
        Q_generation = Q_calc[i] * network.base_mva + Q_load

        results.append({
            "bus_id": bus.bus_id,
            "P_generation_mw": P_generation,
            "Q_generation_mvar": Q_generation,
            "generator_count": len(generators),
            "source_type": "External Grid" if not generators else "Generator",
        })

    return results
