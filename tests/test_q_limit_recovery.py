"""Tests for A2 Q-limit enforcement, restoration, and safety."""
import copy
import numpy as np
import pytest

from loadflow.models import Bus, Generator, Line, Load, Network
from loadflow.q_limits import check_q_limits
from loadflow.solver import solve_newton_raphson


def sample_network():
    net = Network(base_mva=100)
    for bus in (Bus(1, 'Slack', 1.06), Bus(2, 'PV', 1.04), Bus(3, 'PQ')):
        net.add_bus(bus)
    net.add_generator(Generator(1))
    net.add_generator(Generator(2, p_mw=50, q_min_mvar=-10,
                                q_max_mvar=10, q_mvar=2))
    net.add_load(Load(3, p_mw=90, q_mvar=30))
    for line in (Line(1, 2, .02, .06, .03),
                 Line(1, 3, .08, .24, .025),
                 Line(2, 3, .06, .18, .02)):
        net.add_line(line)
    return net


def test_enforcement_toggle_works_without_modifying_original():
    net = sample_network()
    before = copy.deepcopy(net)
    off = solve_newton_raphson(net, enforce_q_limits=False)
    on = solve_newton_raphson(net, enforce_q_limits=True)
    assert off['converged'] and on['converged']
    assert off['effective_bus_types'][2] == 'PV'
    assert on['effective_bus_types'][2] == 'PQ'
    assert on['q_limit_events'][0]['action'] == 'PV->PQ'
    assert off['q_limit_events'] == []
    assert net == before


@pytest.mark.parametrize('limit,actual_v', [('Qmax', 1.06), ('Qmin', 1.02)])
def test_limited_pq_bus_recovers_when_voltage_crosses_setpoint(limit, actual_v):
    net = sample_network()
    net.buses[1].bus_type = 'PQ'
    gen = net.generators[1]
    gen.q_mvar = gen.q_max_mvar if limit == 'Qmax' else gen.q_min_mvar
    limited = {2: {'limit': limit, 'original_q': (2,)}}
    events = check_q_limits(net, np.zeros(3), [1.06, actual_v, 1.0],
                            limited_buses=limited,
                            voltage_setpoints={2: 1.04})
    assert [e['action'] for e in events] == ['PQ->PV']
    assert net.buses[1].bus_type == 'PV'
    assert gen.q_mvar == 2
    assert limited == {}


@pytest.mark.parametrize('limit,actual_v', [('Qmax', 1.02), ('Qmin', 1.06),
                                             ('Qmax', 1.04000001)])
def test_limited_bus_stays_pq_until_recovery_criterion(limit, actual_v):
    net = sample_network()
    net.buses[1].bus_type = 'PQ'
    gen = net.generators[1]
    gen.q_mvar = gen.q_max_mvar if limit == 'Qmax' else gen.q_min_mvar
    limited = {2: {'limit': limit, 'original_q': (2,)}}
    events = check_q_limits(net, np.zeros(3), [1.06, actual_v, 1.0],
                            limited_buses=limited,
                            voltage_setpoints={2: 1.04})
    assert events == []
    assert net.buses[1].bus_type == 'PQ'
    assert 2 in limited


def test_zip_load_q_requirement_uses_actual_voltage():
    net = sample_network()
    net.loads.append(Load(2, p_mw=0, q_mvar=20, model='Z'))
    events = check_q_limits(net, np.array([0., .01, 0.]), [1.06, 1.1, 1.0])
    assert events[0]['q_required'] == pytest.approx(25.2)  # 1 + 20*1.1^2


def test_q_switch_stage_limit_validation():
    net = sample_network()
    with pytest.raises(ValueError):
        solve_newton_raphson(net, max_q_switch_stages=0)
