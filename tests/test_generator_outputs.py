
import sys
sys.path.insert(0, "src")

import numpy as np

from loadflow.models import Bus, Generator, Load, Line, Network
from loadflow.solver import solve_newton_raphson
from loadflow.generator_outputs import calculate_generator_outputs


def test_generator_outputs():

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

    # Calculate generator outputs
    outputs = calculate_generator_outputs(
        network,
        solution["P_calc"],
        solution["Q_calc"]
    )

    assert len(outputs) == 2

    slack = next(x for x in outputs if x["bus_id"] == 1)
    pv = next(x for x in outputs if x["bus_id"] == 2)

    # Verify generator outputs
    assert np.isclose(slack["P_generation_mw"], 43.3805, atol=0.01)
    assert np.isclose(slack["Q_generation_mvar"], 52.3393, atol=0.01)

    assert np.isclose(pv["P_generation_mw"], 50.0, atol=0.01)
    assert np.isclose(pv["Q_generation_mvar"], -20.1738, atol=0.01)

    print("\nGenerator Outputs:")

    for output in outputs:
        print(
            f"Bus {output['bus_id']}: "
            f"P = {output['P_generation_mw']:.4f} MW, "
            f"Q = {output['Q_generation_mvar']:.4f} MVAr"
        )

    print("\nGenerator output test passed!")
