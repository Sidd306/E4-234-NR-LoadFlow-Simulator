
import numpy as np

from loadflow.ybus import build_ybus
from loadflow.power import calculate_power
from loadflow.specifications import calculate_specified_power
from loadflow.mismatch import calculate_mismatch
from loadflow.jacobian import build_jacobian
from loadflow.linear_solver import solve_correction
from loadflow.voltage_update import update_voltages
from loadflow.q_limits import check_q_limits


def solve_newton_raphson(network, tolerance=1e-8, max_iterations=20):
    network.validate()

    Ybus, bus_index = build_ybus(network)
    P_spec, Q_spec = calculate_specified_power(network)

    voltage_mag = np.array([bus.voltage_mag_pu for bus in network.buses])
    voltage_angle = np.array([bus.voltage_angle_rad for bus in network.buses])

    history = []
    q_limit_events = []

    total_iterations = 0
    stage = 1

    while True:

        # Inner Newton-Raphson loop
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

            correction = solve_correction(J, mismatch)

            voltage_mag, voltage_angle = update_voltages(
                voltage_mag, voltage_angle,
                correction, p_indices, q_indices
            )

            total_iterations += 1

        # Stop if NR did not converge
        if not converged:
            break

        # Check Q limits only after NR convergence
        q_events = check_q_limits(network, Q_calc)
        q_limit_events.extend(q_events)

        # No violations: final solution obtained
        if not q_events:
            return {
                "converged": True,
                "iterations": total_iterations,
                "voltage_mag": voltage_mag,
                "voltage_angle": voltage_angle,
                "P_calc": P_calc,
                "Q_calc": Q_calc,
                "mismatch": mismatch,
                "history": history,
                "q_limit_events": q_limit_events
            }

        # Update specified powers after PV-to-PQ conversion
        P_spec, Q_spec = calculate_specified_power(network)

        # Start the next NR stage using the latest voltages
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
        "q_limit_events": q_limit_events
    }
