import sys
sys.path.insert(0, "src")

import numpy as np

from loadflow.models import Bus, Generator, Load, Line, Network
from loadflow.solver import solve_newton_raphson


# Create a 3-bus network
network = Network(base_mva=100)

network.add_bus(Bus(1, "Slack", 1.06, 0.0))
network.add_bus(Bus(2, "PV", 1.04, 0.0))
network.add_bus(Bus(3, "PQ", 1.00, 0.0))

network.add_generator(Generator(1))
network.add_generator(Generator(2, p_mw=50))

network.add_load(Load(3, p_mw=90, q_mvar=30))

network.add_line(Line(1, 2, 0.02, 0.06, 0.03))
network.add_line(Line(1, 3, 0.08, 0.24, 0.025))
network.add_line(Line(2, 3, 0.06, 0.18, 0.02))


# Run Newton-Raphson solver
results = solve_newton_raphson(network)


# Display results
print("Converged:", results["converged"])
print("Iterations:", results["iterations"])

print("\nBus Voltage Magnitudes (pu):")
print(results["voltage_mag"])

print("\nBus Voltage Angles (degrees):")
print(np.degrees(results["voltage_angle"]))

print("\nCalculated Active Power (pu):")
print(results["P_calc"])

print("\nCalculated Reactive Power (pu):")
print(results["Q_calc"])

print("\nFinal Maximum Mismatch:")
print(np.max(np.abs(results["mismatch"])))

assert results["converged"], "Newton-Raphson did not converge!"

print("\nNewton-Raphson test passed!")