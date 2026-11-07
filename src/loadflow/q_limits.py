"""Generator reactive limits for a polar Newton-Raphson power flow.

Only non-slack voltage-controlled buses participate. Limits for multiple
online generators are aggregated at each bus. Caller operates on a working
copy of the network, not the user's original network.
"""


def _online_generators(network, bus_id):
    return [g for g in network.generators if g.status and g.bus_id == bus_id]


def _required_q(network, bus_id, index, Q_calc, voltage_mag):
    q_load = sum(load.power_at_voltage(voltage_mag[index])[1]
                 for load in network.loads
                 if load.status and load.bus_id == bus_id)
    return Q_calc[index] * network.base_mva + q_load


def check_q_limits(network, Q_calc, voltage_mag=None, *, limited_buses=None,
                   voltage_setpoints=None, q_tolerance_mvar=1e-7,
                   voltage_hysteresis_pu=1e-5):
    """Apply PV->PQ limit enforcement and optional PQ->PV recovery.

    limited_buses: mutable mapping bus ID -> {'limit': 'Qmin'|'Qmax',
      'original_q': tuple of pre-limit generator reactive schedules}.
    When omitted, retains the original PV->PQ-only API for older callers.

    Recovery criterion: at Qmax, voltage above the regulation setpoint means
    that reducing Q would be needed; at Qmin, voltage below the setpoint
    means that increasing Q would be needed. A small voltage deadband avoids
    switches caused by rounding at the limit boundary.
    """
    if voltage_mag is None:
        voltage_mag = [1.0] * len(network.buses)
    events = []
    restored = set()

    # Recover limited buses first, using the converged PQ voltage.
    if limited_buses is not None:
        for i, bus in enumerate(network.buses):
            state = limited_buses.get(bus.bus_id)
            if state is None or bus.bus_type != 'PQ':
                continue
            setpoint = voltage_setpoints[bus.bus_id]
            actual_v = float(voltage_mag[i])
            limit = state['limit']
            can_restore = (
                (limit == 'Qmax' and actual_v > setpoint + voltage_hysteresis_pu)
                or (limit == 'Qmin' and actual_v < setpoint - voltage_hysteresis_pu)
            )
            if not can_restore:
                continue
            gens = _online_generators(network, bus.bus_id)
            if len(gens) != len(state['original_q']):
                raise ValueError('Generator membership changed during Q-limit check')
            for gen, original_q in zip(gens, state['original_q']):
                gen.q_mvar = original_q
            bus.bus_type = 'PV'
            # PV voltage magnitude is prescribed; solver reapplies it.
            events.append({
                'bus_id': bus.bus_id, 'action': 'PQ->PV',
                'limit': limit, 'voltage_pu': actual_v,
                'setpoint_pu': setpoint
            })
            del limited_buses[bus.bus_id]
            restored.add(bus.bus_id)

    for i, bus in enumerate(network.buses):
        if bus.bus_type != 'PV' or bus.bus_id in restored:
            continue
        generators = _online_generators(network, bus.bus_id)
        if not generators:
            continue
        q_required = _required_q(network, bus.bus_id, i, Q_calc, voltage_mag)
        q_min = sum(g.q_min_mvar for g in generators)
        q_max = sum(g.q_max_mvar for g in generators)
        if q_required < q_min - q_tolerance_mvar:
            q_limit, limit_type = q_min, 'Qmin'
        elif q_required > q_max + q_tolerance_mvar:
            q_limit, limit_type = q_max, 'Qmax'
        else:
            continue
        if limited_buses is not None:
            limited_buses[bus.bus_id] = {
                'limit': limit_type,
                'original_q': tuple(g.q_mvar for g in generators),
            }
        for gen in generators:
            gen.q_mvar = gen.q_min_mvar if limit_type == 'Qmin' else gen.q_max_mvar
        bus.bus_type = 'PQ'
        events.append({
            'bus_id': bus.bus_id, 'action': 'PV->PQ',
            'limit': limit_type, 'q_required': q_required, 'q_limit': q_limit
        })
    return events
