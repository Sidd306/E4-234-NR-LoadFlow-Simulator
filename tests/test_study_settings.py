import numpy as np
import pytest
from loadflow.models import Network, Bus, Generator, Load, Line
from loadflow.solver import solve_newton_raphson


def case():
    net = Network(base_mva=100)
    net.add_bus(Bus(1, 'Slack', 1.04))
    net.add_bus(Bus(2, 'PQ'))
    net.add_generator(Generator(1))
    net.add_load(Load(2, p_mw=45, q_mvar=17))
    net.add_line(Line(1, 2, 0.03, 0.1))
    return net


def test_timing_and_previous_solution():
    net = case()
    first = solve_newton_raphson(net)
    assert first['converged']
    assert first['solve_time_s'] >= 0
    assert len(first['iteration_times_s']) == len(first['history'])
    initial = {'voltage_mag': first['voltage_mag'], 'voltage_angle': first['voltage_angle']}
    second = solve_newton_raphson(net, initial_state=initial)
    assert second['converged']
    assert second['iterations'] == 0
    np.testing.assert_allclose(first['voltage_mag'], second['voltage_mag'])


def test_initial_state_validation():
    net = case()
    with pytest.raises(ValueError, match='bus count'):
        solve_newton_raphson(net, initial_state={'voltage_mag': [1.0], 'voltage_angle': [0.0]})
    with pytest.raises(ValueError, match='Invalid initial'):
        solve_newton_raphson(net, initial_state={'voltage_mag': [1, -1], 'voltage_angle': [0, 0]})


def test_q_limit_option():
    net = case()
    for enabled in (True, False):
        answer = solve_newton_raphson(net, enforce_q_limits=enabled)
        assert answer['converged']
