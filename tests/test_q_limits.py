import sys
sys.path.insert(0, "src")

from loadflow.models import Bus, Generator, Network
from loadflow.q_limits import check_q_limits


network = Network(base_mva=100)

network.add_bus(Bus(1, "Slack"))
network.add_bus(Bus(2, "PV", 1.04))

network.add_generator(Generator(
    bus_id=1
))

network.add_generator(Generator(
    bus_id=2,
    p_mw=50,
    q_min_mvar=-40,
    q_max_mvar=40
))

# Required Q at bus 2 = 60 MVAr
Q_calc = [0.0, 0.60]

events = check_q_limits(network, Q_calc)

print("Events:", events)
print("Bus 2 type:", network.buses[1].bus_type)
print("Generator Q:", network.generators[1].q_mvar)

assert network.buses[1].bus_type == "PQ"
assert network.generators[1].q_mvar == 40

print("\nQ-limit test passed!")

# Test Qmin violation
network2 = Network(base_mva=100)

network2.add_bus(Bus(1, "Slack"))
network2.add_bus(Bus(2, "PV", 1.04))

network2.add_generator(Generator(bus_id=1))
network2.add_generator(Generator(
    bus_id=2,
    p_mw=50,
    q_min_mvar=-40,
    q_max_mvar=40
))

# Required Q = -60 MVAr
Q_calc2 = [0.0, -0.60]

events2 = check_q_limits(network2, Q_calc2)

print("\nQmin Events:", events2)
print("Bus 2 type:", network2.buses[1].bus_type)
print("Generator Q:", network2.generators[1].q_mvar)

assert network2.buses[1].bus_type == "PQ"
assert network2.generators[1].q_mvar == -40

print("\nQmin test passed!")