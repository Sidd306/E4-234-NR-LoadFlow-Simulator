"""Regression tests for data integrity and GUI-to-solver boundary issues."""
import copy
import numpy as np
import pytest
from loadflow.models import Network, Bus, Generator, Line, Load
from loadflow.solver import solve_newton_raphson


def basic_network(with_generator=True):
    net = Network(base_mva=100)
    net.add_bus(Bus(1, "Slack", 1.04))
    net.add_bus(Bus(2, "PQ"))
    if with_generator:
        net.add_generator(Generator(1))
    net.add_load(Load(2, 40, 20))
    net.add_line(Line(1, 2, 0.02, 0.08))
    return net


def test_external_grid_without_generator_is_reported_and_balanced():
    net = basic_network(False)
    result = solve_newton_raphson(net)
    assert result["converged"]
    assert result["system_summary"]["power_balance_ok"]
    assert len(result["generator_outputs"]) == 1
    assert result["generator_outputs"][0]["source_type"] == "External Grid"


def test_disconnected_bus_rejected():
    net = basic_network()
    net.add_bus(Bus(3))
    with pytest.raises(ValueError, match="Disconnected"):
        net.validate()


def test_zero_impedance_after_edit_rejected():
    net = basic_network()
    net.lines[0].r_pu = net.lines[0].x_pu = 0
    with pytest.raises(ValueError, match="zero impedance"):
        net.validate()


def test_explicit_pv_generator_setpoint_is_used():
    net = basic_network()
    net.add_bus(Bus(3, "PV", voltage_mag_pu=1.0))
    net.add_line(Line(1, 3, 0.02, 0.06))
    net.add_generator(Generator(3, p_mw=10, voltage_setpoint_pu=1.05))
    result = solve_newton_raphson(net)
    assert result["converged"]
    assert np.isclose(result["voltage_mag"][2], 1.05)


def test_q_limits_do_not_change_input_network():
    net = basic_network()
    net.add_bus(Bus(3, "PV", voltage_mag_pu=1.05))
    net.add_line(Line(1, 3, 0.02, 0.06))
    net.add_generator(Generator(3, p_mw=10, q_min_mvar=-1, q_max_mvar=1))
    before = copy.deepcopy(net)
    result = solve_newton_raphson(net)
    assert result["converged"]
    assert len(result["q_limit_events"]) >= 1
    assert net == before
    assert result["effective_bus_types"][3] == "PQ"
    result2 = solve_newton_raphson(net)
    assert np.allclose(result["voltage_mag"], result2["voltage_mag"])
