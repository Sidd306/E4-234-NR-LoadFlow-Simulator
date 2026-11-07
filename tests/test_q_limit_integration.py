
import sys
sys.path.insert(0, "src")

from loadflow.models import Bus, Generator, Load, Line, Network
from loadflow.solver import solve_newton_raphson


def test_pv_to_pq_switching():

    # Create a 3-bus network
    network = Network(base_mva=100)

    network.add_bus(Bus(1, "Slack", 1.06, 0.0))
    network.add_bus(Bus(2, "PV", 1.04, 0.0))
    network.add_bus(Bus(3, "PQ", 1.00, 0.0))

    network.add_generator(Generator(1))

    # Restrict reactive power limits at bus 2
    generator = Generator(
        2,
        p_mw=50,
        q_min_mvar=-10,
        q_max_mvar=10
    )
    network.add_generator(generator)

    network.add_load(Load(3, p_mw=90, q_mvar=30))

    network.add_line(Line(1, 2, 0.02, 0.06, 0.03))
    network.add_line(Line(1, 3, 0.08, 0.24, 0.025))
    network.add_line(Line(2, 3, 0.06, 0.18, 0.02))

    # Run solver
    results = solve_newton_raphson(network)

    # Verify convergence
    assert results["converged"]

    # Effective operating bus becomes PQ; original model remains unchanged.
    assert results["effective_bus_types"][2] == "PQ"
    assert network.buses[1].bus_type == "PV"
    assert generator.q_mvar == 0.0

    # Verify Q-limit event
    assert len(results["q_limit_events"]) == 1
    assert results["q_limit_events"][0]["limit"] == "Qmin"

    # Verify that a second NR stage was executed
    assert any(entry["stage"] == 2 for entry in results["history"])

    print("\nPV-to-PQ switching test passed!")
    print("Bus 2 temporarily converted from PV to PQ.")
    print("Original generator schedule remains:", generator.q_mvar, "MVAr")
    print("Total NR iterations:", results["iterations"])
