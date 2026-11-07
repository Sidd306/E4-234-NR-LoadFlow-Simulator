def check_q_limits(network, Q_calc, voltage_mag=None):
    """
    Check reactive power limits at PV buses.

    If the required generator reactive power exceeds
    the aggregate limits, convert the PV bus to PQ.
    """

    events = []

    for i, bus in enumerate(network.buses):

        if bus.bus_type != "PV":
            continue

        # Find online generators connected to this bus
        generators = [
            gen for gen in network.generators
            if gen.bus_id == bus.bus_id and gen.status
        ]

        if not generators:
            continue

        # Calculate total reactive power required from generators
        v = voltage_mag[i] if voltage_mag is not None else 1.0
        q_load = sum(
            load.power_at_voltage(v)[1]
            for load in network.loads
            if load.bus_id == bus.bus_id and load.status
        )

        q_required = Q_calc[i] * network.base_mva + q_load

        # Aggregate generator reactive power limits
        q_min = sum(gen.q_min_mvar for gen in generators)
        q_max = sum(gen.q_max_mvar for gen in generators)

        # Check whether reactive power limits are violated
        if q_required < q_min:
            q_limit = q_min
            limit_type = "Qmin"

        elif q_required > q_max:
            q_limit = q_max
            limit_type = "Qmax"

        else:
            continue

        # Set generators to their respective limiting values
        for gen in generators:
            if limit_type == "Qmin":
                gen.q_mvar = gen.q_min_mvar
            else:
                gen.q_mvar = gen.q_max_mvar
        # Convert PV bus to PQ
        bus.bus_type = "PQ"

        events.append({
            "bus_id": bus.bus_id,
            "limit": limit_type,
            "q_required": q_required,
            "q_limit": q_limit
        })

    return events