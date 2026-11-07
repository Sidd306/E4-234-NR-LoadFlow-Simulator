
def calculate_generator_outputs(network, P_calc, Q_calc):

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
        P_load = sum(
            load.p_mw
            for load in network.loads
            if load.bus_id == bus.bus_id and load.status
        )

        Q_load = sum(
            load.q_mvar
            for load in network.loads
            if load.bus_id == bus.bus_id and load.status
        )

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
