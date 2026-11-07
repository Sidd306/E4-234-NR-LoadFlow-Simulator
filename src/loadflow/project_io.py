"""Versioned JSON project persistence (no GUI dependency)."""
import json
import math
from dataclasses import asdict, fields
from pathlib import Path
from .models import Bus, Generator, Load, Line, Transformer, Shunt, Network

ELEMENTS = {"buses": Bus, "generators": Generator, "loads": Load,
            "lines": Line, "transformers": Transformer, "shunts": Shunt}
STUDY_KEYS = ("tolerance", "max_iterations", "enforce_q_limits",
              "use_previous_solution", "load_scale")


def project_to_dict(network, positions=None, settings=None):
    if network is None:
        raise ValueError("Cannot save an empty project")
    positions = positions or {}
    def xy(v):
        if hasattr(v, "x") and hasattr(v, "y"):
            return [float(v.x()), float(v.y())]
        return [float(v[0]), float(v[1])]
    return {"format": "E4234_LoadFlow_Project", "version": 1,
            "base_mva": network.base_mva, "frequency_hz": network.frequency_hz,
            "elements": {key: [asdict(item) for item in getattr(network, key)]
                         for key in ELEMENTS},
            "layout": {str(k): xy(v) for k, v in positions.items()},
            "study": {key: settings[key] for key in STUDY_KEYS
                      if settings and key in settings}}


def project_from_dict(payload):
    if not isinstance(payload, dict) or payload.get("format") != "E4234_LoadFlow_Project" or payload.get("version") != 1:
        raise ValueError("Unsupported project file or version")
    if not isinstance(payload.get("elements"), dict):
        raise ValueError("Missing project elements")
    network = Network(base_mva=float(payload["base_mva"]),
                      frequency_hz=float(payload.get("frequency_hz", 50.0)))
    for name, cls in ELEMENTS.items():
        objects = payload["elements"].get(name, [])
        if not isinstance(objects, list):
            raise ValueError(f"Invalid {name} list")
        allowed = {f.name for f in fields(cls)}
        for obj in objects:
            if not isinstance(obj, dict) or set(obj) - allowed:
                raise ValueError(f"Invalid {name} entry")
            getattr(network, name).append(cls(**obj))
    # Validate only if a complete network was saved. In-progress diagrams may have
    # zero or multiple slack buses and must remain editable after reopening.
    if network.buses and sum(b.bus_type == "Slack" for b in network.buses) == 1:
        network.validate()
    layout = {}
    for k, xy in payload.get("layout", {}).items():
        if not isinstance(xy, list) or len(xy) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in xy):
            raise ValueError("Invalid bus layout coordinates")
        layout[int(k)] = (float(xy[0]), float(xy[1]))
    settings = payload.get("study", {})
    if not isinstance(settings, dict):
        raise ValueError("Invalid study settings")
    settings = {key: settings[key] for key in STUDY_KEYS if key in settings}
    return network, layout, settings


def save_project_file(path, network, positions=None, settings=None):
    data = project_to_dict(network, positions, settings)
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load_project_file(path):
    return project_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
