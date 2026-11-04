
import sys
sys.path.insert(0, "src")

import numpy as np

from loadflow.models import Bus, Generator, Load, Line, Network
from loadflow.ybus import build_ybus
from loadflow.power import calculate_power
from loadflow.specifications import calculate_specified_power
from loadflow.mismatch import calculate_mismatch
from loadflow.jacobian import build_jacobian
from loadflow.linear_solver import solve_correction
from loadflow.voltage_update import update_voltages


def test_jacobian():

    # Create a 3-bus network
    network = Network(base_mva=100)

    network.add_bus(Bus(1, "Slack", 1.06, 0.0))
    network.add_bus(Bus(2, "PV", 1.04, 0.0))
    network.add_bus(Bus(3, "PQ", 1.00, 0.0))

    network.add_generator(Generator(1))
    network.add_generator(Generator(2, p_mw=50))

    network.add_load(Load(3, p_mw=90, q_mvar=30))

    network.add_line(Line(1, 2, 0.02, 0.06, 0.03))
    network.add_line(Line(1, 3, 0.08, 0.24, 0.025))
    network.add_line(Line(2, 3, 0.06, 0.18, 0.02))

    # Build Ybus
    Ybus, bus_index = build_ybus(network)

    # Initial voltage values
    V = np.array([1.06, 1.04, 1.00])
    theta = np.array([0.0, 0.0, 0.0])

    # Calculate power
    P_calc, Q_calc = calculate_power(Ybus, V, theta)

    # Calculate specified power
    P_spec, Q_spec = calculate_specified_power(network)

    # Calculate mismatch
    mismatch, p_indices, q_indices = calculate_mismatch(
        network, P_spec, Q_spec, P_calc, Q_calc
    )

    # Build Jacobian
    J = build_jacobian(
        network, Ybus, V, theta,
        P_calc, Q_calc, p_indices, q_indices
    )

    # Verify Jacobian
    assert J.shape == (3, 3)
    assert np.all(np.isfinite(J))

    print("\nJacobian matrix:")
    print(J)

    print("\nJacobian test passed!")

    # Solve for voltage corrections
    correction = solve_correction(J, mismatch)

    # Verify LU solver
    residual = J @ correction - mismatch

    assert np.allclose(residual, 0, atol=1e-10)

    print("\nMismatch vector:")
    print(mismatch)

    print("\nVoltage correction vector:")
    print(correction)

    print("\nSolver residual:")
    print(residual)

    print("\nLU solver test passed!")

    # Update voltages
    V_new, theta_new = update_voltages(
        V, theta, correction, p_indices, q_indices
    )

    # Verify voltage updates
    assert V_new[0] == V[0]       # Slack voltage unchanged
    assert V_new[1] == V[1]       # PV voltage unchanged

    assert np.allclose(V_new[2], V[2] + correction[2])

    print("\nUpdated voltage magnitudes:")
    print(V_new)

    print("\nUpdated voltage angles (degrees):")
    print(np.degrees(theta_new))

    print("\nVoltage update test passed!")
