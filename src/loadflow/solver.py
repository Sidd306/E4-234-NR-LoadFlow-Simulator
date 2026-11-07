
import numpy as np
import copy

from loadflow.ybus import build_ybus
from loadflow.power import calculate_power
from loadflow.specifications import calculate_specified_power
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
    P_load = sum(
        load.p_mw for load in network.loads if load.status
    )
    Q_load = sum(
        load.q_mvar for load in network.loads if load.status
    )

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


def solve_newton_raphson(network, tolerance=1e-8, max_iterations=20):

    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("Tolerance must be finite and positive")
    if not isinstance(max_iterations, int) or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    network.validate()
    # Q-limit PV -> PQ switching operates on a temporary network.
    # Never overwrite the GUI's original bus types or generator schedules.
    network = copy.deepcopy(network)

    Ybus, bus_index = build_ybus(network)
    P_spec, Q_spec = calculate_specified_power(network)

    voltage_mag = np.array([bus.voltage_mag_pu for bus in network.buses])
    voltage_angle = np.array([bus.voltage_angle_rad for bus in network.buses])

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

    history = []
    q_limit_events = []

    total_iterations = 0
    stage = 1

    while True:

        converged = False

        for iteration in range(max_iterations + 1):

            P_calc, Q_calc = calculate_power(
                Ybus, voltage_mag, voltage_angle
            )

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
                converged = True
                break

            if iteration == max_iterations:
                break

            J = build_jacobian(
                network, Ybus, voltage_mag, voltage_angle,
                P_calc, Q_calc, p_indices, q_indices
            )

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

        if not converged:
            break

        # Check Q limits after convergence
        q_events = check_q_limits(network, Q_calc)
        q_limit_events.extend(q_events)

        if not q_events:

            generator_outputs = calculate_generator_outputs(
                network, P_calc, Q_calc
            )

            branch_flows = calculate_line_flows(
                network, voltage_mag, voltage_angle
            )

            system_summary = calculate_system_summary(
                network, voltage_mag, generator_outputs, branch_flows
            )

            return {
                "converged": True,
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

        P_spec, Q_spec = calculate_specified_power(network)
        stage += 1

    return {
        "converged": False,
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
