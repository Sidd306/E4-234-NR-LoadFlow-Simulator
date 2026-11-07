import copy
import numpy as np
import pytest
from loadflow.models import Network, Bus, Generator, Load, Transformer
from loadflow.ybus import build_ybus
from loadflow.branch_flows import calculate_line_flows
from loadflow.matpower_export import network_to_matpower
from loadflow.project_io import project_to_dict, project_from_dict


def case():
    n = Network()
    n.add_bus(Bus(1, 'Slack', 1.05))
    n.add_bus(Bus(2, 'PQ', 1.0))
    n.add_generator(Generator(1))
    n.add_load(Load(2, 20, 10))
    n.add_transformer(Transformer(1, 2, .01, .1, tap_ratio=1.04,
                                  phase_shift_deg=8, tap_side='to',
                                  tap_min=.95, tap_max=1.1, tap_step=.01))
    return n


def test_to_side_tap_ybus_matches_reversed_from_side():
    n = case()
    m = copy.deepcopy(n)
    t = m.transformers[0]
    t.from_bus, t.to_bus = t.to_bus, t.from_bus
    t.tap_side = 'from'
    y1, _ = build_ybus(n)
    y2, _ = build_ybus(m)
    np.testing.assert_allclose(y1.toarray(), y2.toarray(), atol=1e-12)
    v = np.array([1.05, .98]); a = np.array([0.0, -.05])
    first = calculate_line_flows(n, v, a)[0]
    second = calculate_line_flows(m, v, a)[0]
    np.testing.assert_allclose([first['P_from_mw'], first['Q_from_mvar']],
                               [second['P_to_mw'], second['Q_to_mvar']], atol=1e-10)


def test_to_side_export_flips_orientation():
    text = network_to_matpower(case(), 'case_tapped')
    assert '2 1 0.01 0.1' in text


def test_tap_fields_json_round_trip():
    project = project_to_dict(case())
    loaded, _, _ = project_from_dict(project)
    assert loaded.transformers[0].tap_side == 'to'
    assert loaded.transformers[0].tap_min == .95
    assert loaded.transformers[0].tap_step == .01


def test_tap_limit_validation():
    with pytest.raises(ValueError, match='below tap minimum'):
        Transformer(1, 2, .01, .1, tap_ratio=.9, tap_min=.95)
