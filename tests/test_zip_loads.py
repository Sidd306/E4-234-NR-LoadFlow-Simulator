"""Regression tests for voltage-dependent load models."""
import numpy as np
import pytest

from loadflow.models import Network, Bus, Line, Load
from loadflow.solver import solve_newton_raphson
from loadflow.specifications import calculate_specified_power_voltage_derivatives


def network_with_load(model, **kwargs):
    n = Network(base_mva=100)
    n.add_bus(Bus(1, 'Slack', 1.0))
    n.add_bus(Bus(2, 'PQ'))
    n.add_line(Line(1, 2, 0.02, 0.06))
    n.add_load(Load(2, 50.0, 20.0, model=model, **kwargs))
    return n


def test_default_pq_unchanged():
    a = solve_newton_raphson(network_with_load('PQ'))
    b = solve_newton_raphson(network_with_load('ZIP', p_zip=(0, 0, 1), q_zip=(0, 0, 1)))
    assert a['converged'] and b['converged']
    assert np.allclose(a['voltage_mag'], b['voltage_mag'], atol=1e-12)
    assert a['system_summary']['power_balance_ok']


def test_constant_impedance_load_uses_actual_voltage():
    n = network_with_load('Z')
    r = solve_newton_raphson(n)
    assert r['converged']
    v = r['voltage_mag'][1]
    assert v < 1
    s = r['system_summary']
    assert s['P_load_mw'] == pytest.approx(50 * v**2, abs=1e-9)
    assert s['Q_load_mvar'] == pytest.approx(20 * v**2, abs=1e-9)
    assert s['power_balance_ok']
    assert n.loads[0].model == 'Z'  # solver must not modify original


def test_zip_mixed_model_and_derivative():
    n = network_with_load('ZIP', p_zip=(0.3, 0.2, 0.5), q_zip=(0.1, 0.3, 0.6))
    r = solve_newton_raphson(n)
    assert r['converged']
    v = r['voltage_mag'][1]
    s = r['system_summary']
    assert s['P_load_mw'] == pytest.approx(50 * (0.3*v*v + 0.2*v + 0.5))
    assert s['Q_load_mvar'] == pytest.approx(20 * (0.1*v*v + 0.3*v + 0.6))
    assert s['power_balance_ok']
    dp, dq = calculate_specified_power_voltage_derivatives(n, r['voltage_mag'])
    h = 1e-6
    ld = n.loads[0]
    fd = (ld.power_at_voltage(v+h)[0]-ld.power_at_voltage(v-h)[0])/(2*h)
    assert dp[1] == pytest.approx(-fd / 100, abs=1e-9)


def test_invalid_zip_coefficients():
    with pytest.raises(ValueError):
        Load(2, 50, 20, model='ZIP', p_zip=(0.5, 0.5, 0.5))
    with pytest.raises(ValueError):
        Load(2, 50, 20, model='XYZ')
