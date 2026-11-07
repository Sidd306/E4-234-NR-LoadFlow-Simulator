
import sys
from pathlib import Path
from collections import Counter, defaultdict

import pandapower as pp

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from loadflow.matpower_import import load_matpower_case

DATA = ROOT / "data"

CASES = {
    "case14.m": pp.networks.case14,
    "case_ieee30.m": pp.networks.case30,
    "case57.m": pp.networks.case57,
    "case118.m": pp.networks.case118,
}


def diagnose(filename, reference_function):

    print("\n" + "=" * 55)
    print(filename)
    print("=" * 55)

    ours = load_matpower_case(DATA / filename)
    ref = reference_function()

    # Assumed bus mapping
    bus_ids = [bus.bus_id for bus in ours.buses]
    pp_to_id = dict(enumerate(bus_ids))

    # Aggregate loads at each bus
    our_load = defaultdict(lambda: [0.0, 0.0])
    pp_load = defaultdict(lambda: [0.0, 0.0])

    for load in ours.loads:
        if load.status:
            our_load[load.bus_id][0] += load.p_mw
            our_load[load.bus_id][1] += load.q_mvar

    for _, load in ref.load.iterrows():
        if load.in_service:
            bus_id = pp_to_id[load.bus]
            pp_load[bus_id][0] += load.p_mw
            pp_load[bus_id][1] += load.q_mvar

    # Aggregate non-slack generation
    our_gen = defaultdict(float)
    pp_gen = defaultdict(float)

    slack_ids = {
        bus.bus_id for bus in ours.buses
        if bus.bus_type == "Slack"
    }

    for gen in ours.generators:
        if gen.status and gen.bus_id not in slack_ids:
            our_gen[gen.bus_id] += gen.p_mw

    for _, gen in ref.gen.iterrows():
        if gen.in_service:
            bus_id = pp_to_id[gen.bus]
            pp_gen[bus_id] += gen.p_mw

    # Find bus-wise load differences
    load_differences = []

    for bus_id in bus_ids:
        op, oq = our_load[bus_id]
        rp, rq = pp_load[bus_id]

        error = max(abs(op - rp), abs(oq - rq))

        if error > 1e-6:
            load_differences.append(
                (bus_id, op, rp, oq, rq)
            )

    # Find bus-wise generation differences
    gen_differences = []

    for bus_id in bus_ids:
        op = our_gen[bus_id]
        rp = pp_gen[bus_id]

        if abs(op - rp) > 1e-6:
            gen_differences.append((bus_id, op, rp))

    # Compare branch endpoint counts, regardless of type
    our_branches = Counter()

    for line in ours.lines:
        if line.status:
            our_branches[frozenset(
                (line.from_bus, line.to_bus)
            )] += 1

    for trafo in ours.transformers:
        if trafo.status:
            our_branches[frozenset(
                (trafo.from_bus, trafo.to_bus)
            )] += 1

    pp_branches = Counter()

    for _, line in ref.line.iterrows():
        if line.in_service:
            pp_branches[frozenset((
                pp_to_id[line.from_bus],
                pp_to_id[line.to_bus]
            ))] += 1

    for _, trafo in ref.trafo.iterrows():
        if trafo.in_service:
            pp_branches[frozenset((
                pp_to_id[trafo.hv_bus],
                pp_to_id[trafo.lv_bus]
            ))] += 1

    missing = our_branches - pp_branches
    extra = pp_branches - our_branches

    print("\nBUS-WISE LOAD DIFFERENCES")
    print("Count:", len(load_differences))

    for row in load_differences[:15]:
        bus, op, rp, oq, rq = row
        print(
            f"Bus {bus}: "
            f"Our P/Q = {op:.3f}/{oq:.3f}, "
            f"PP P/Q = {rp:.3f}/{rq:.3f}"
        )

    print("\nBUS-WISE GENERATION DIFFERENCES")
    print("Count:", len(gen_differences))

    for bus, op, rp in gen_differences[:15]:
        print(
            f"Bus {bus}: Our P = {op:.3f}, "
            f"PP P = {rp:.3f} MW"
        )

    print("\nBRANCH TOPOLOGY")
    print("Our branches:", sum(our_branches.values()))
    print("PP branches:", sum(pp_branches.values()))
    print("Connections missing in PP:", dict(missing))
    print("Extra connections in PP:", dict(extra))


if __name__ == "__main__":
    for filename, reference_function in CASES.items():
        diagnose(filename, reference_function)
