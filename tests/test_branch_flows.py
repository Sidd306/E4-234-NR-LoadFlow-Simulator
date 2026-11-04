
import sys
sys.path.insert(0, "src")

import numpy as np

from loadflow.models import Bus, Generator, Load, Line, Network
from loadflow.solver import solve_newton_raphson
from loadflow.branch_flows import calculate_line_flows


def test_line_flows():

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

    # Solve load flow
    solution = solve_newton_raphson(network)

    assert solution["converged"]

    # Calculate line flows
    flows = calculate_line_flows(
        network,
        solution["voltage_mag"],
        solution["voltage_angle"]
    )

    # Verify number of line results
    assert len(flows) == 3

    # Verify active power losses are positive
    for flow in flows:
        assert flow["P_loss_mw"] > 0

    # Verify total line losses against total network active power loss
    total_line_loss = sum(flow["P_loss_mw"] for flow in flows)

    total_network_loss = np.sum(solution["P_calc"]) * network.base_mva

    assert np.isclose(total_line_loss, total_network_loss, atol=1e-6)

    print("\nLine Flow Results:")

    for flow in flows:
        print(
            f"Line {flow['from_bus']} - {flow['to_bus']}: "
            f"P_from = {flow['P_from_mw']:.4f} MW, "
            f"P_to = {flow['P_to_mw']:.4f} MW, "
            f"P_loss = {flow['P_loss_mw']:.4f} MW"
        )

    print("\nTotal line losses:", total_line_loss, "MW")


