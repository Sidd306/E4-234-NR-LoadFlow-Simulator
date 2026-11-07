
import numpy as np
import copy
from time import perf_counter

from loadflow.ybus import build_ybus
from loadflow.power import calculate_power
from loadflow.specifications import (calculate_specified_power,
    calculate_specified_power_voltage_derivatives)
from loadflow.mismatch import calculate_mismatch
from loadflow.jacobian import build_jacobian
from loadflow.linear_solver import solve_correction
from loadflow.voltage_update import update_voltages
from loadflow.q_limits import check_q_limits
from loadflow.generator_outputs import calculate_generator_outputs
from loadflow.branch_flows import calculate_line_flows


def calculate_system_summary(network, voltage_mag, generator_outputs, branch_flows):

    base_mva = network.base_mva

    # Total generation
    P_generation = sum(
        gen["P_generation_mw"] for gen in generator_outputs
    )
    Q_generation = sum(
        gen["Q_generation_mvar"] for gen in generator_outputs
    )

    # Total load
    bus_index = {bus.bus_id: i for i, bus in enumerate(network.buses)}
    actual_loads = [load.power_at_voltage(voltage_mag[bus_index[load.bus_id]])
                    for load in network.loads if load.status]
    P_load = sum(item[0] for item in actual_loads)
    Q_load = sum(item[1] for item in actual_loads)

    # Losses in lines and transformers
    P_branch_loss = sum(
        branch["P_loss_mw"] for branch in branch_flows
    )
    Q_branch_loss = sum(
        branch["Q_loss_mvar"] for branch in branch_flows
    )

    # Losses / absorption in bus shunts
    P_shunt_loss = 0.0
    Q_shunt_loss = 0.0

    bus_index = {
        bus.bus_id: i for i, bus in enumerate(network.buses)
    }

    for shunt in network.shunts:
        if not shunt.status:
            continue

        i = bus_index[shunt.bus_id]
        V_squared = voltage_mag[i] ** 2

        P_shunt_loss += V_squared * shunt.g_pu * base_mva
        Q_shunt_loss -= V_squared * shunt.b_pu * base_mva

    # Total system losses
    P_loss = P_branch_loss + P_shunt_loss
    Q_loss = Q_branch_loss + Q_shunt_loss

    # Power balance errors
    P_balance_error = P_generation - P_load - P_loss
    Q_balance_error = Q_generation - Q_load - Q_loss

    return {
        "P_generation_mw": P_generation,
        "Q_generation_mvar": Q_generation,
        "P_load_mw": P_load,
        "Q_load_mvar": Q_load,
        "P_branch_loss_mw": P_branch_loss,
        "Q_branch_loss_mvar": Q_branch_loss,
        "P_shunt_loss_mw": P_shunt_loss,
        "Q_shunt_loss_mvar": Q_shunt_loss,
        "P_loss_mw": P_loss,
        "Q_loss_mvar": Q_loss,
        "P_balance_error_mw": P_balance_error,
        "Q_balance_error_mvar": Q_balance_error,
        "power_balance_ok": (
            abs(P_balance_error) <= 1e-6
            and abs(Q_balance_error) <= 1e-6
        )
    }


def solve_newton_raphson(network, tolerance=1e-8, max_iterations=20,
                         enforce_q_limits=True, max_q_switch_stages=None,
                         initial_state=None):

    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("Tolerance must be finite and positive")
    if not isinstance(max_iterations, int) or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    if not isinstance(enforce_q_limits, bool):
        raise ValueError("enforce_q_limits must be boolean")
    if max_q_switch_stages is not None and (not isinstance(max_q_switch_stages, int)
                                           or max_q_switch_stages < 1):
        raise ValueError("max_q_switch_stages must be a positive integer")
    started_at = perf_counter()
    network.validate()
    # Q-limit PV -> PQ switching operates on a temporary network.
    # Never overwrite the GUI's original bus types or generator schedules.
    network = copy.deepcopy(network)

    Ybus, bus_index = build_ybus(network)
    voltage_mag = np.array([bus.voltage_mag_pu for bus in network.buses])
    voltage_angle = np.array([bus.voltage_angle_rad for bus in network.buses])

    if initial_state is not None:
        if not isinstance(initial_state, dict) or not {"voltage_mag", "voltage_angle"} <= set(initial_state):
            raise ValueError("initial_state requires voltage_mag and voltage_angle arrays")
        v0 = np.asarray(initial_state["voltage_mag"], dtype=float)
        a0 = np.asarray(initial_state["voltage_angle"], dtype=float)
        if v0.shape != voltage_mag.shape or a0.shape != voltage_angle.shape:
            raise ValueError("Initial voltage arrays must match bus count")
        if not np.all(np.isfinite(v0)) or not np.all(np.isfinite(a0)) or np.any(v0 <= 0):
            raise ValueError("Invalid initial voltage state")
        voltage_mag, voltage_angle = v0.copy(), a0.copy()

    # An explicitly configured generator setpoint wins over the bus
    # initialization. Keep the legacy default (1.0) as unspecified when
    # a manually constructed bus carries a different voltage value.
    for i, bus in enumerate(network.buses):
        if bus.bus_type in ("PV", "Slack"):
            gens = [g for g in network.generators
                    if g.status and g.bus_id == bus.bus_id]
            explicit = [g.voltage_setpoint_pu for g in gens
                        if abs(g.voltage_setpoint_pu - 1.0) > 1e-10]
            if explicit:
                voltage_mag[i] = explicit[0]

    # Preserve each PV bus's prescribed voltage for possible PQ->PV recovery.
    voltage_setpoints = {b.bus_id: float(voltage_mag[i])
                         for i, b in enumerate(network.buses) if b.bus_type == 'PV'}
    limited_buses = {}
    if max_q_switch_stages is None:
        max_q_switch_stages = max(10, 4 * len(voltage_setpoints) + 4)

    history = []
    iteration_times = []
    q_limit_events = []

    total_iterations = 0
    stage = 1

    while True:

        converged = False

        for iteration in range(max_iterations + 1):

            iteration_started_at = perf_counter()
            P_calc, Q_calc = calculate_power(
                Ybus, voltage_mag, voltage_angle
            )
            P_spec, Q_spec = calculate_specified_power(network, voltage_mag)

            mismatch, p_indices, q_indices = calculate_mismatch(
                network, P_spec, Q_spec, P_calc, Q_calc
            )

            error = np.max(np.abs(mismatch)) if mismatch.size else 0.0

            history.append({
                "stage": stage,
                "stage_iteration": iteration,
                "total_iterations": total_iterations,
                "max_mismatch": error
            })

            if error <= tolerance:
                iteration_times.append(perf_counter() - iteration_started_at)
                converged = True
                break

            if iteration == max_iterations:
                iteration_times.append(perf_counter() - iteration_started_at)
                break

            J = build_jacobian(
                network, Ybus, voltage_mag, voltage_angle,
                P_calc, Q_calc, p_indices, q_indices
            )
            # The mismatch is P_spec(V)-P_calc(V). The Newton matrix is
            # dP_calc/dV - dP_spec/dV, likewise for Q.
            dps, dqs = calculate_specified_power_voltage_derivatives(
                network, voltage_mag)
            n_p = len(p_indices)
            for column, j in enumerate(q_indices):
                for row, i in enumerate(p_indices):
                    if i == j:
                        J[row, n_p + column] -= dps[i]
                J[n_p + column, n_p + column] -= dqs[j]

            try:
                correction = solve_correction(J, mismatch)
            except Exception as exc:
                raise RuntimeError(
                    f"Newton-Raphson linear solve failed at iteration "
                    f"{total_iterations}: {exc}"
                ) from exc
            if not np.all(np.isfinite(correction)):
                raise RuntimeError("Newton correction contains NaN/Inf")

            voltage_mag, voltage_angle = update_voltages(
                voltage_mag, voltage_angle,
                correction, p_indices, q_indices
            )

            if (not np.all(np.isfinite(voltage_mag))
                    or not np.all(np.isfinite(voltage_angle))
                    or np.any(voltage_mag <= 0)):
                raise RuntimeError("Invalid voltage state during Newton iteration")
            total_iterations += 1
            iteration_times.append(perf_counter() - iteration_started_at)

        if not converged:
            break

        # Only evaluate switching at a fully converged operating point.
        # Both initial limiting and later recovery use voltage-dependent Q loads.
        q_events = (
            check_q_limits(network, Q_calc, voltage_mag,
                           limited_buses=limited_buses,
                           voltage_setpoints=voltage_setpoints)
            if enforce_q_limits else []
        )
        for event in q_events:
            event['stage'] = stage
        q_limit_events.extend(q_events)
        for event in q_events:
            if event['action'] == 'PQ->PV':
                i = bus_index[event['bus_id']]
                voltage_mag[i] = voltage_setpoints[event['bus_id']]
        if q_events and stage >= max_q_switch_stages:
            raise RuntimeError(
                f"Q-limit switching did not settle within {max_q_switch_stages} "
                "stages; inspect q_limit_events and generator limits"
            )

        if not q_events:

            generator_outputs = calculate_generator_outputs(
                network, P_calc, Q_calc, voltage_mag
            )

            branch_flows = calculate_line_flows(
                network, voltage_mag, voltage_angle
            )

            system_summary = calculate_system_summary(
                network, voltage_mag, generator_outputs, branch_flows
            )

            return {
                "converged": True,
                "solve_time_s": perf_counter() - started_at,
                "iteration_times_s": iteration_times,
                "iterations": total_iterations,
                "voltage_mag": voltage_mag,
                "voltage_angle": voltage_angle,
                "P_calc": P_calc,
                "Q_calc": Q_calc,
                "generator_outputs": generator_outputs,
                "branch_flows": branch_flows,
                "system_summary": system_summary,
                "mismatch": mismatch,
                "history": history,
                "q_limit_events": q_limit_events,
                "effective_bus_types": {b.bus_id: b.bus_type for b in network.buses}
            }

        stage += 1

    return {
        "converged": False,
        "solve_time_s": perf_counter() - started_at,
        "iteration_times_s": iteration_times,
        "iterations": total_iterations,
        "voltage_mag": voltage_mag,
        "voltage_angle": voltage_angle,
        "P_calc": P_calc,
        "Q_calc": Q_calc,
        "mismatch": mismatch,
        "history": history,
        "q_limit_events": q_limit_events,
        "effective_bus_types": {b.bus_id: b.bus_type for b in network.buses}
    }
