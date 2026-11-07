
import sys
from pathlib import Path

import pandapower as pp

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from loadflow.matpower_import import load_matpower_case


DATA = Path(__file__).resolve().parent / "data"

CASES = {
    "case14.m": pp.networks.case14,
    "case_ieee30.m": pp.networks.case30,
    "case57.m": pp.networks.case57,
    "case118.m": pp.networks.case118,
}

for filename, reference_function in CASES.items():
    network = load_matpower_case(DATA / filename)
    reference = reference_function()

    print(f"\n{'=' * 45}")
    print(filename)

    print("Our network:")
    print(
        "Buses:", len(network.buses),
        "Generators:", len(network.generators),
        "Lines:", len(network.lines),
        "Transformers:", len(network.transformers),
        "Shunts:", len(network.shunts)
    )

    print("Pandapower network:")
    print(
        "Buses:", len(reference.bus),
        "Generators:", len(reference.gen) + len(reference.ext_grid),
        "Lines:", len(reference.line),
        "Transformers:", len(reference.trafo),
        "Shunts:", len(reference.shunt)
    )

    print("\nOur transformer connections:")
    print([
        (t.from_bus, t.to_bus, t.tap_ratio, t.phase_shift_deg)
        for t in network.transformers
    ])

    print("\nPandapower transformer connections:")
    print([
        (int(t.hv_bus), int(t.lv_bus), t.vn_hv_kv, t.vn_lv_kv)
        for _, t in reference.trafo.iterrows()
    ])
