"""Regression tests for GUI-independent menu operations."""
import math
import pytest
from loadflow.models import Network, Bus, Line, Transformer, Shunt, Generator, Load
from loadflow.network_tools import convert_system_base, duplicate_buses
from loadflow.project_io import project_to_dict, project_from_dict
from loadflow.solver import solve_newton_raphson


def sample():
    net = Network(base_mva=100., frequency_hz=50.)
    net.buses = [Bus(1, bus_type='Slack', voltage_mag_pu=1.04), Bus(2, bus_type='PQ')]
    net.lines = [Line(1, 2, r_pu=.015, x_pu=.12, b_pu=.02, rate_mva=100)]
    net.loads = [Load(2, p_mw=40, q_mvar=15)]
    net.generators = [Generator(1, p_mw=40)]
    net.shunts = [Shunt(2, g_pu=.002, b_pu=.01)]
    return net


def test_base_change_preserves_powerflow():
    n = sample()
    original = solve_newton_raphson(n)
    convert_system_base(n, 200.)
    assert n.lines[0].r_pu == pytest.approx(.03)
    assert n.lines[0].x_pu == pytest.approx(.24)
    assert n.lines[0].b_pu == pytest.approx(.01)
    assert n.shunts[0].b_pu == pytest.approx(.005)
    result = solve_newton_raphson(n)
    assert result['converged'] and original['converged']
    assert result['voltage_mag'] == pytest.approx(original['voltage_mag'], abs=1e-8)
    assert result['voltage_angle'] == pytest.approx(original['voltage_angle'], abs=1e-8)
    assert result['system_summary']['P_loss_mw'] == pytest.approx(original['system_summary']['P_loss_mw'], abs=1e-5)


def test_base_invalid_rejected_without_mutation():
    n = sample()
    with pytest.raises(ValueError):
        convert_system_base(n, float('nan'))
    assert n.base_mva == 100
    with pytest.raises(ValueError):
        convert_system_base(n, 0)


def test_copy_bus_uses_fresh_ids_and_preserves_original():
    n = sample()
    ids, positions = duplicate_buses(n, [1,2], {1:(0, 0), 2:(100, 0)})
    assert ids == [3,4]
    assert positions[3] == (70.,70.)
    assert n.buses[2].bus_type == 'PQ'  # Never create second slack.
    assert n.buses[0].bus_type == 'Slack'
    assert n.lines[-1].from_bus == 3 and n.lines[-1].to_bus == 4
    assert n.generators[-1].bus_id == 3
    assert n.loads[-1].bus_id == 4
    assert n.shunts[-1].bus_id == 4


def test_copy_only_selected_bus_does_not_duplicate_dangling_lines():
    n = sample()
    ids, _ = duplicate_buses(n, [2])
    assert ids == [3]
    assert len(n.lines) == 1
    assert len(n.loads) == 2


def test_frequency_project_roundtrip_and_old_file():
    n = sample()
    n.frequency_hz = 60
    payload = project_to_dict(n)
    restored, _, _ = project_from_dict(payload)
    assert restored.frequency_hz == 60
    del payload['frequency_hz']
    restored, _, _ = project_from_dict(payload)
    assert restored.frequency_hz == 50


def test_invalid_frequency_rejected():
    n = sample()
    n.frequency_hz = -1
    with pytest.raises(ValueError, match='Frequency'):
        n.validate()
