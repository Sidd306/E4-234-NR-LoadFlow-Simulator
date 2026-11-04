
import sys
sys.path.insert(0, "src")

from loadflow.models import Bus, Generator, Network
from loadflow.q_limits import check_q_limits


def create_test_network():

    network = Network(base_mva=100)

    network.add_bus(Bus(1, "Slack"))
    network.add_bus(Bus(2, "PV", 1.04))

    network.add_generator(Generator(bus_id=1))

    generator = Generator(
        bus_id=2,
        p_mw=50,
        q_min_mvar=-40,
        q_max_mvar=40
    )

    network.add_generator(generator)

    return network, generator


def test_qmax_violation():

    network, generator = create_test_network()

    # Required Q at bus 2 = 60 MVAr
    Q_calc = [0.0, 0.60]

    events = check_q_limits(network, Q_calc)

    assert network.buses[1].bus_type == "PQ"
    assert generator.q_mvar == 40

    assert len(events) == 1
    assert events[0]["limit"] == "Qmax"
    assert events[0]["q_required"] == 60
    assert events[0]["q_limit"] == 40

    print("\nQmax test passed!")


def test_qmin_violation():

    network, generator = create_test_network()

    # Required Q at bus 2 = -60 MVAr
    Q_calc = [0.0, -0.60]

    events = check_q_limits(network, Q_calc)

    assert network.buses[1].bus_type == "PQ"
    assert generator.q_mvar == -40

    assert len(events) == 1
    assert events[0]["limit"] == "Qmin"
    assert events[0]["q_required"] == -60
    assert events[0]["q_limit"] == -40

    print("\nQmin test passed!")
