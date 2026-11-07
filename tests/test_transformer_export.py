import math
import pytest
from loadflow.models import Network, Bus, Generator, Load, Line, Transformer
from loadflow.units import (transformer_nameplate_to_system_pu,
                            transformer_system_pu_to_nameplate)
from loadflow.matpower_export import save_matpower_case, network_to_matpower
from loadflow.matpower_import import load_matpower_case


def test_transformer_nameplate_base_conversion():
    r, x = transformer_nameplate_to_system_pu(10, 10, 50, 110, 100, 110)
    assert math.hypot(r, x) == pytest.approx(0.2)
    assert x / r == pytest.approx(10)
    z, xr = transformer_system_pu_to_nameplate(r, x, 50, 110, 100, 110)
    assert z == pytest.approx(10)
    assert xr == pytest.approx(10)
    r2, x2 = transformer_nameplate_to_system_pu(10, 10, 50, 110, 100, 220)
    assert r2 == pytest.approx(r / 4)
    assert x2 == pytest.approx(x / 4)


def test_invalid_transformer_nameplate():
    with pytest.raises(ValueError):
        transformer_nameplate_to_system_pu(0, 10, 50, 110, 100, 110)
    with pytest.raises(ValueError):
        transformer_nameplate_to_system_pu(10, -1, 50, 110, 100, 110)


def test_matpower_export_roundtrip(tmp_path):
    n = Network(base_mva=100)
    n.add_bus(Bus(1, 'Slack', voltage_mag_pu=1.03, nominal_kv=110))
    n.add_bus(Bus(2, 'PQ', nominal_kv=110))
    n.add_bus(Bus(3, 'PQ', nominal_kv=110))
    n.add_generator(Generator(bus_id=1, p_mw=0, voltage_setpoint_pu=1.03))
    n.add_load(Load(bus_id=2, p_mw=75, q_mvar=25))
    n.add_line(Line(1, 2, r_pu=.02, x_pu=.06, b_pu=.03, rate_mva=100))
    n.add_transformer(Transformer(2, 3, r_pu=.01, x_pu=.08, tap_ratio=1.05,
                                  phase_shift_deg=5, rate_mva=80))
    p = tmp_path / 'case_roundtrip.m'
    save_matpower_case(p, n)
    n2 = load_matpower_case(p)
    assert len(n2.buses) == 3
    assert len(n2.lines) == 1
    assert len(n2.transformers) == 1
    assert n2.loads[0].p_mw == pytest.approx(75)
    assert n2.transformers[0].tap_ratio == pytest.approx(1.05)
    assert n2.transformers[0].phase_shift_deg == pytest.approx(5)


def test_export_implicit_slack_and_zip_rejection(tmp_path):
    n = Network()
    n.add_bus(Bus(1, 'Slack'))
    n.add_bus(Bus(2))
    n.add_line(Line(1, 2, .01, .1))
    text = network_to_matpower(n)
    assert 'mpc.gen' in text
    n.add_load(Load(bus_id=2, model='Z', p_mw=20))
    with pytest.raises(ValueError, match='constant-PQ'):
        network_to_matpower(n)
