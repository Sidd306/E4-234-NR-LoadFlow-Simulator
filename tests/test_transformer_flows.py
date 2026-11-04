
import sys
sys.path.insert(0, "src")

import numpy as np

from loadflow.models import Bus, Generator, Load, Network, Transformer
from loadflow.solver import solve_newton_raphson
from loadflow.branch_flows import calculate_line_flows


def test_transformer_flows():

    # Create a 2-bus network
    network = Network(base_mva=100)

    network.add_bus(Bus(1, "Slack", 1.05, 0.0))
    network.add_bus(Bus(2, "PQ", 1.00, 0.0))

    network.add_generator(Generator(1))
    network.add_load(Load(2, p_mw=50, q_mvar=20))

    # Transformer with tap ratio and phase shift
    transformer = Transformer(
        from_bus=1,
        to_bus=2,
        r_pu=0.01,
        x_pu=0.10,
        tap_ratio=1.05,
        phase_shift_deg=10,
        rate_mva=100
    )

    network.add_transformer(transformer)

    # Solve load flow
    solution = solve_newton_raphson(network)

    assert solution["converged"]

    # Calculate transformer flows
    flows = calculate_line_flows(
        network,
        solution["voltage_mag"],
        solution["voltage_angle"]
    )

    assert len(flows) == 1

    flow = flows[0]

    # Verify transformer identification
    assert flow["element_type"] == "Transformer"

    # Verify positive active power loss
    assert flow["P_loss_mw"] > 0

    # Verify loading calculation
    assert flow["loading_percent"] is not None

    # Verify power balance
    total_branch_loss = flow["P_loss_mw"]
    total_network_loss = (
        np.sum(solution["P_calc"]) * network.base_mva
    )

    assert np.isclose(
        total_branch_loss,
        total_network_loss,
        atol=1e-6
    )

    print("\nTransformer Flow Results:")
    print(f"P from: {flow['P_from_mw']:.4f} MW")
    print(f"Q from: {flow['Q_from_mvar']:.4f} MVAr")
    print(f"P to: {flow['P_to_mw']:.4f} MW")
    print(f"Q to: {flow['Q_to_mvar']:.4f} MVAr")
    print(f"P loss: {flow['P_loss_mw']:.4f} MW")
    print(f"Q loss: {flow['Q_loss_mvar']:.4f} MVAr")
    print(f"Loading: {flow['loading_percent']:.2f}%")

    print("\nTransformer flow test passed!")
