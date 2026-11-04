import numpy as np

from loadflow.ybus import build_ybus
from loadflow.power import calculate_power
from loadflow.specifications import calculate_specified_power
from loadflow.mismatch import calculate_mismatch
from loadflow.jacobian import build_jacobian
from loadflow.linear_solver import solve_correction
from loadflow.voltage_update import update_voltages


def solve_newton_raphson(network, tolerance=1e-8, max_iterations=20):

    network.validate()

    # Build Ybus and calculate specified powers
    Ybus, bus_index = build_ybus(network)
    P_spec, Q_spec = calculate_specified_power(network)

    # Initialise bus voltages
    voltage_mag = np.array(
        [bus.voltage_mag_pu for bus in network.buses]
    )

    voltage_angle = np.array(
        [bus.voltage_angle_rad for bus in network.buses]
    )
    history = []        
    # Newton-Raphson iteration
    for iteration in range(max_iterations + 1):

        # Calculate power injections
        P_calc, Q_calc = calculate_power(
            Ybus, voltage_mag, voltage_angle
        )

        # Calculate mismatch
        mismatch, p_indices, q_indices = calculate_mismatch(
            network, P_spec, Q_spec, P_calc, Q_calc
        )

        # Check convergence
        error = np.max(np.abs(mismatch)) if mismatch.size else 0.0
        
        history.append({
        "iteration": iteration,
        "max_mismatch": error
        })

        if error <= tolerance:
            return {
                "converged": True,
                "iterations": iteration,
                "voltage_mag": voltage_mag,
                "voltage_angle": voltage_angle,
                "P_calc": P_calc,
                "Q_calc": Q_calc,
                "mismatch": mismatch,
                "history": history
            }

        if iteration == max_iterations:
            break

        # Construct Jacobian
        J = build_jacobian(
            network, Ybus, voltage_mag, voltage_angle,
            P_calc, Q_calc, p_indices, q_indices
        )

        # Solve for voltage corrections
        correction = solve_correction(J, mismatch)

        # Update voltages
        voltage_mag, voltage_angle = update_voltages(
            voltage_mag, voltage_angle,
            correction, p_indices, q_indices
        )

    return {
        "converged": False,
        "iterations": max_iterations,
        "voltage_mag": voltage_mag,
        "voltage_angle": voltage_angle,
        "P_calc": P_calc,
        "Q_calc": Q_calc,
        "mismatch": mismatch
    }
