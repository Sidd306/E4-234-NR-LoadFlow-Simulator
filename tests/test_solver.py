
import sys
sys.path.insert(0, "src")

import numpy as np

from loadflow.models import Bus, Generator, Load, Line, Network
from loadflow.solver import solve_newton_raphson


def test_solver():

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
    print("\nConverged:", results["converged"])
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

    # Generator outputs
    print("\nGenerator Outputs:")

    for output in results["generator_outputs"]:
        print(
            f"Bus {output['bus_id']}: "
            f"P = {output['P_generation_mw']:.4f} MW, "
            f"Q = {output['Q_generation_mvar']:.4f} MVAr"
        )

    # Branch flows
    print("\nBranch Flows:")

    for branch in results["branch_flows"]:
        print(
            f"{branch['element_type']} "
            f"{branch['from_bus']} -> {branch['to_bus']}: "
            f"P loss = {branch['P_loss_mw']:.4f} MW, "
            f"Q loss = {branch['Q_loss_mvar']:.4f} MVAr"
        )

    # System summary
    summary = results["system_summary"]

    print("\nSystem Summary:")
    print(f"Total Active Generation: {summary['P_generation_mw']:.4f} MW")
    print(f"Total Reactive Generation: {summary['Q_generation_mvar']:.4f} MVAr")
    print(f"Total Active Load: {summary['P_load_mw']:.4f} MW")
    print(f"Total Reactive Load: {summary['Q_load_mvar']:.4f} MVAr")

    print(f"Active Branch Losses: {summary['P_branch_loss_mw']:.4f} MW")
    print(f"Reactive Branch Losses: {summary['Q_branch_loss_mvar']:.4f} MVAr")

    print(f"Active Shunt Losses: {summary['P_shunt_loss_mw']:.4f} MW")
    print(f"Reactive Shunt Losses: {summary['Q_shunt_loss_mvar']:.4f} MVAr")

    print(f"Total Active Losses: {summary['P_loss_mw']:.4f} MW")
    print(f"Total Reactive Losses: {summary['Q_loss_mvar']:.4f} MVAr")

    print(f"Active Power Balance Error: {summary['P_balance_error_mw']:.10e} MW")
    print(f"Reactive Power Balance Error: {summary['Q_balance_error_mvar']:.10e} MVAr")
    print("Power Balance:", summary["power_balance_ok"])

    # Convergence history
    print("\nConvergence History:")

    for entry in results["history"]:
        print(
            f"Stage {entry['stage']}, "
            f"Iteration {entry['stage_iteration']}, "
            f"Total Iterations {entry['total_iterations']}: "
            f"Mismatch = {entry['max_mismatch']:.10e}"
        )

    # Solver assertions
    assert results["converged"]
    assert np.max(np.abs(results["mismatch"])) <= 1e-8

    # Generator output assertions
    assert len(results["generator_outputs"]) == 2

    slack = next(
        x for x in results["generator_outputs"] if x["bus_id"] == 1
    )
    pv = next(
        x for x in results["generator_outputs"] if x["bus_id"] == 2
    )

    assert np.isclose(slack["P_generation_mw"], 43.3805, atol=0.01)
    assert np.isclose(slack["Q_generation_mvar"], 52.3393, atol=0.01)
    assert np.isclose(pv["P_generation_mw"], 50.0, atol=0.01)
    assert np.isclose(pv["Q_generation_mvar"], -20.1738, atol=0.01)

    # Branch flow assertions
    assert len(results["branch_flows"]) == 3

    for branch in results["branch_flows"]:
        assert branch["P_loss_mw"] >= -1e-8

    # System summary assertions
    assert np.isclose(summary["P_generation_mw"], 93.3805, atol=0.01)
    assert np.isclose(summary["P_load_mw"], 90.0, atol=1e-8)
    assert np.isclose(summary["P_loss_mw"], 3.3805, atol=0.01)

    assert abs(summary["P_balance_error_mw"]) <= 1e-6
    assert abs(summary["Q_balance_error_mvar"]) <= 1e-6
    assert summary["power_balance_ok"]

    print("\nNewton-Raphson test passed!")


