import json
import pytest
from loadflow.models import Network, Bus, Load, Generator, Line
from loadflow.project_io import project_to_dict, project_from_dict, save_project_file, load_project_file


def example():
    net = Network(base_mva=75.0)
    net.add_bus(Bus(1, bus_type='Slack', voltage_mag_pu=1.02))
    net.add_bus(Bus(2, bus_type='PQ'))
    net.add_line(Line(1, 2, .01, .1))
    net.add_generator(Generator(1, p_mw=10))
    net.add_load(Load(2, p_mw=20, q_mvar=4, model='ZIP',
                      p_zip=(.2, .3, .5), q_zip=(.4, .1, .5)))
    return net


def test_round_trip(tmp_path):
    net = example()
    path = tmp_path/'case.json'
    settings = {'tolerance':1e-9, 'load_scale':1.25, 'max_iterations':30}
    save_project_file(path, net, {1:(22,33),2:(44,55)}, settings)
    restored, positions, study = load_project_file(path)
    assert restored.base_mva == 75
    assert restored.loads[0].model == 'ZIP'
    assert tuple(restored.loads[0].p_zip) == (.2,.3,.5)
    assert positions[2] == (44.,55.)
    assert study == settings
    assert project_to_dict(restored, positions, study) == json.loads(path.read_text())


def test_bad_format_rejected():
    with pytest.raises(ValueError, match='Unsupported'):
        project_from_dict({'format':'other','version':1,'elements':{}})


def test_invalid_position_rejected():
    payload = project_to_dict(example())
    payload['layout'] = {'1':[float('nan'), 0]}
    with pytest.raises(ValueError, match='coordinates'):
        project_from_dict(payload)


def test_partial_project_can_be_saved():
    net = Network()
    net.add_bus(Bus(1))
    restored, _, _ = project_from_dict(project_to_dict(net))
    assert restored.buses[0].bus_type == 'PQ'
