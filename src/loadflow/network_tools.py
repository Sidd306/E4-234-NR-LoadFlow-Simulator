"""GUI-independent operations for safe network editing."""
from copy import deepcopy
import math


def convert_system_base(network, new_base_mva):
    """Change Sbase while preserving physical impedances/admittances.

    Voltage bases are unchanged. Generator/load powers remain in MW/MVAr.
    Branch series Zpu scales by new/old; parallel and bus shunt Ypu
    scales by old/new. Transformer tap ratios and phase shifts remain.
    """
    new = float(new_base_mva)
    if not math.isfinite(new) or new <= 0:
        raise ValueError("System base MVA must be finite and positive")
    old = float(network.base_mva)
    if not math.isfinite(old) or old <= 0:
        raise ValueError("Existing base MVA must be finite and positive")
    factor = new / old
    for branch in network.lines + network.transformers:
        branch.r_pu *= factor
        branch.x_pu *= factor
        branch.b_pu /= factor
    for shunt in network.shunts:
        shunt.g_pu /= factor
        shunt.b_pu /= factor
    network.base_mva = new


def duplicate_buses(network, bus_ids, positions=None, offset=(70.0, 70.0)):
    """Duplicate selected buses and their equipment; include internal branches.

    The copied slack bus becomes PQ to avoid creating an extra slack bus.
    New IDs are allocated without disturbing existing IDs.
    Returns (new_ids, new_positions). Does not mutate existing elements.
    """
    selected = set(int(i) for i in bus_ids)
    selected_buses = [b for b in network.buses if b.bus_id in selected]
    if not selected_buses:
        return [], {}
    next_id = max((b.bus_id for b in network.buses), default=0) + 1
    mapping = {b.bus_id: next_id + k for k, b in enumerate(selected_buses)}
    for bus in selected_buses:
        clone = deepcopy(bus)
        clone.bus_id = mapping[bus.bus_id]
        if clone.bus_type == 'Slack':
            clone.bus_type = 'PQ'
        network.add_bus(clone)
    for collection_name in ('generators', 'loads', 'shunts'):
        collection = getattr(network, collection_name)
        for obj in list(collection):
            if obj.bus_id in mapping:
                clone = deepcopy(obj)
                clone.bus_id = mapping[obj.bus_id]
                collection.append(clone)
    for collection_name in ('lines', 'transformers'):
        collection = getattr(network, collection_name)
        for obj in list(collection):
            if obj.from_bus in mapping and obj.to_bus in mapping:
                clone = deepcopy(obj)
                clone.from_bus = mapping[obj.from_bus]
                clone.to_bus = mapping[obj.to_bus]
                collection.append(clone)
    new_positions = {}
    positions = positions or {}
    for old_id, new_id in mapping.items():
        if old_id in positions:
            point = positions[old_id]
            x, y = (point.x(), point.y()) if hasattr(point, 'x') else point
            new_positions[new_id] = (float(x) + offset[0], float(y) + offset[1])
    return list(mapping.values()), new_positions
