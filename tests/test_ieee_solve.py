
from pathlib import Path

import pytest

from loadflow.matpower_import import load_matpower_case
from loadflow.solver import solve_newton_raphson


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.mark.parametrize(
    "case_name",
    [
        "case14.m",
        "case_ieee30.m",
        "case57.m",
        "case118.m",
    ],
)
def test_ieee_solver(case_name):
    network = load_matpower_case(DATA_DIR / case_name)

    # Flat start
    for bus in network.buses:
        bus.voltage_angle_rad = 0.0

        if bus.bus_type == "PQ":
            bus.voltage_mag_pu = 1.0

    # Effectively disable generator reactive power limits
    for generator in network.generators:
        generator.q_min_mvar = -1e6
        generator.q_max_mvar = 1e6

    result = solve_newton_raphson(
        network,
        tolerance=1e-8,
        max_iterations=20
    )

    mismatch = max(abs(x) for x in result["mismatch"])

    print(f"\n{case_name}")
    print("Buses:", len(network.buses))
    print("Converged:", result["converged"])
    print("Iterations:", result["iterations"])
    print("Maximum mismatch:", mismatch)

    assert result["converged"]
    assert mismatch <= 1e-8

    # Assignment requirement for IEEE 118-bus case
    if case_name == "case118.m":
        assert result["iterations"] <= 7
