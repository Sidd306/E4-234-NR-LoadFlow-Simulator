
from pathlib import Path

from loadflow.matpower_import import load_matpower_case


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_ieee_cases_import():
    cases = {
        "case14.m": 14,
        "case_ieee30.m": 30,
        "case57.m": 57,
        "case118.m": 118,
    }

    for filename, expected_buses in cases.items():
        network = load_matpower_case(DATA_DIR / filename)

        assert len(network.buses) == expected_buses
        assert len([
            bus for bus in network.buses
            if bus.bus_type == "Slack"
        ]) == 1

        assert network.validate()

        print(
            f"{filename}: "
            f"{len(network.buses)} buses, "
            f"{len(network.generators)} generators, "
            f"{len(network.lines)} lines, "
            f"{len(network.transformers)} transformers"
        )
