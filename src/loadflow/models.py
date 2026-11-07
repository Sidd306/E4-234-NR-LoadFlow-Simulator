from dataclasses import dataclass, field

@dataclass
class Bus:
    bus_id: int
    bus_type: str = "PQ"
    voltage_mag_pu: float = 1.0
    voltage_angle_rad: float = 0.0
    name: str = ""

    def __post_init__(self):
        if self.bus_type not in ("Slack", "PV", "PQ"):
            raise ValueError("Bus type must be Slack, PV, or PQ")

        if self.bus_id <= 0:
            raise ValueError("Bus ID must be positive")

        if self.voltage_mag_pu <= 0:
            raise ValueError("Voltage magnitude must be positive")

@dataclass
class Generator:
    bus_id: int
    p_mw: float = 0.0
    q_mvar: float = 0.0
    q_min_mvar: float = -999.0
    q_max_mvar: float = 999.0
    voltage_setpoint_pu: float = 1.0
    status: bool = True

    def __post_init__(self):
        if self.bus_id <= 0:
            raise ValueError("Bus ID must be positive")

        if self.q_min_mvar > self.q_max_mvar:
            raise ValueError("Minimum Q cannot exceed maximum Q")

        if self.voltage_setpoint_pu <= 0:
            raise ValueError("Voltage setpoint must be positive")

@dataclass
class Load:
    bus_id: int
    p_mw: float = 0.0
    q_mvar: float = 0.0
    status: bool = True
    # PQ, Z, or ZIP. P/Q specify nominal load at 1 pu.
    model: str = "PQ"
    p_zip: tuple[float, float, float] = (0.0, 0.0, 1.0)  # Z, I, P
    q_zip: tuple[float, float, float] = (0.0, 0.0, 1.0)

    def __post_init__(self):
        if self.bus_id <= 0:
            raise ValueError("Bus ID must be positive")
        self.validate_model()

    def validate_model(self):
        import math
        if self.model not in ("PQ", "Z", "ZIP"):
            raise ValueError("Load model must be PQ, Z or ZIP")
        if self.model == "ZIP":
            for label, coefficients in (("P", self.p_zip), ("Q", self.q_zip)):
                if len(coefficients) != 3 or any(not math.isfinite(x) or x < 0 for x in coefficients):
                    raise ValueError(f"Invalid {label} ZIP coefficients")
                if not math.isclose(sum(coefficients), 1.0, rel_tol=0, abs_tol=1e-8):
                    raise ValueError(f"{label} ZIP coefficients must sum to 1")

    def power_at_voltage(self, voltage):
        if self.model == "PQ":
            return self.p_mw, self.q_mvar
        if self.model == "Z":
            return self.p_mw * voltage**2, self.q_mvar * voltage**2
        def multiplier(coeff):
            z, i, p = coeff
            return z * voltage**2 + i * voltage + p
        return self.p_mw * multiplier(self.p_zip), self.q_mvar * multiplier(self.q_zip)

    def power_derivative(self, voltage):
        if self.model == "PQ":
            return 0.0, 0.0
        if self.model == "Z":
            return 2 * self.p_mw * voltage, 2 * self.q_mvar * voltage
        pz, pi, _ = self.p_zip
        qz, qi, _ = self.q_zip
        return self.p_mw * (2 * pz * voltage + pi), self.q_mvar * (2 * qz * voltage + qi)

@dataclass
class Line:
    from_bus: int
    to_bus: int
    r_pu: float
    x_pu: float
    b_pu: float = 0.0
    rate_mva: float = 0.0
    status: bool = True

    def __post_init__(self):
        if self.from_bus <= 0 or self.to_bus <= 0:
            raise ValueError("Bus IDs must be positive")

        if self.from_bus == self.to_bus:
            raise ValueError("A line cannot connect a bus to itself")

        if self.r_pu == 0 and self.x_pu == 0:
            raise ValueError("Line impedance cannot be zero")

        if self.rate_mva < 0:
            raise ValueError("Line rating cannot be negative")

@dataclass
class Transformer:
    from_bus: int
    to_bus: int
    r_pu: float
    x_pu: float
    tap_ratio: float = 1.0
    phase_shift_deg: float = 0.0
    rate_mva: float = 0.0
    status: bool = True
    b_pu: float = 0.0

    def __post_init__(self):
        if self.from_bus <= 0 or self.to_bus <= 0:
            raise ValueError("Bus IDs must be positive")

        if self.from_bus == self.to_bus:
            raise ValueError("A transformer cannot connect a bus to itself")

        if self.r_pu == 0 and self.x_pu == 0:
            raise ValueError("Transformer impedance cannot be zero")

        if self.tap_ratio <= 0:
            raise ValueError("Tap ratio must be positive")

        if self.rate_mva < 0:
            raise ValueError("Transformer rating cannot be negative")
@dataclass
class Shunt:
    bus_id: int
    g_pu: float = 0.0
    b_pu: float = 0.0
    status: bool = True

    def __post_init__(self):
        if self.bus_id <= 0:
            raise ValueError("Bus ID must be positive")


@dataclass
class Network:
    base_mva: float = 100.0

    buses: list[Bus] = field(default_factory=list)
    generators: list[Generator] = field(default_factory=list)
    loads: list[Load] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    transformers: list[Transformer] = field(default_factory=list)
    shunts: list[Shunt] = field(default_factory=list)

    def add_bus(self, bus):
        if any(b.bus_id == bus.bus_id for b in self.buses):
            raise ValueError("Duplicate bus ID")

        self.buses.append(bus)

    def add_generator(self, generator):
        self.generators.append(generator)

    def add_load(self, load):
        self.loads.append(load)

    def add_line(self, line):
        self.lines.append(line)

    def add_transformer(self, transformer):
        self.transformers.append(transformer)

    def add_shunt(self, shunt):
        self.shunts.append(shunt)
    
    def validate(self):
        """Validate the CURRENT network, including values edited after creation."""
        import math

        if not math.isfinite(self.base_mva) or self.base_mva <= 0:
            raise ValueError("Base MVA must be finite and positive")
        if not self.buses:
            raise ValueError("Network must contain at least one bus")
        ids = [b.bus_id for b in self.buses]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate bus IDs found")
        if sum(b.bus_type == "Slack" for b in self.buses) != 1:
            raise ValueError("Network must contain exactly one Slack bus")
        existing = set(ids)

        for bus in self.buses:
            if bus.bus_type not in ("Slack", "PV", "PQ"):
                raise ValueError(f"Bus {bus.bus_id}: invalid bus type")
            if (not math.isfinite(bus.voltage_mag_pu)
                    or bus.voltage_mag_pu <= 0
                    or not math.isfinite(bus.voltage_angle_rad)):
                raise ValueError(f"Bus {bus.bus_id}: invalid voltage or angle")

        for component in self.generators + self.loads + self.shunts:
            if component.bus_id not in existing:
                raise ValueError(f"Bus {component.bus_id} does not exist")

        for gen in self.generators:
            vals = (gen.p_mw, gen.q_mvar, gen.q_min_mvar,
                    gen.q_max_mvar, gen.voltage_setpoint_pu)
            if not all(math.isfinite(v) for v in vals):
                raise ValueError(f"Generator at bus {gen.bus_id}: non-finite data")
            if gen.q_min_mvar > gen.q_max_mvar or gen.voltage_setpoint_pu <= 0:
                raise ValueError(f"Generator at bus {gen.bus_id}: invalid limits/setpoint")
        for load in self.loads:
            load.validate_model()
            if not all(math.isfinite(v) for v in (load.p_mw, load.q_mvar)):
                raise ValueError(f"Load at bus {load.bus_id}: non-finite data")
        for shunt in self.shunts:
            if not all(math.isfinite(v) for v in (shunt.g_pu, shunt.b_pu)):
                raise ValueError(f"Shunt at bus {shunt.bus_id}: non-finite data")

        adjacency = {bus_id: set() for bus_id in ids}
        for branch in self.lines + self.transformers:
            if branch.from_bus not in existing or branch.to_bus not in existing:
                raise ValueError(f"Branch {branch.from_bus}-{branch.to_bus}: unknown bus")
            if branch.from_bus == branch.to_bus:
                raise ValueError("Branch cannot connect a bus to itself")
            vals = [branch.r_pu, branch.x_pu, branch.b_pu, branch.rate_mva]
            if isinstance(branch, Transformer):
                vals += [branch.tap_ratio, branch.phase_shift_deg]
                if branch.tap_ratio <= 0:
                    raise ValueError("Transformer tap ratio must be positive")
            if not all(math.isfinite(v) for v in vals):
                raise ValueError(f"Branch {branch.from_bus}-{branch.to_bus}: non-finite data")
            if branch.r_pu == 0 and branch.x_pu == 0:
                raise ValueError(f"Branch {branch.from_bus}-{branch.to_bus}: zero impedance")
            if branch.rate_mva < 0:
                raise ValueError("Branch rating cannot be negative")
            if branch.status:
                adjacency[branch.from_bus].add(branch.to_bus)
                adjacency[branch.to_bus].add(branch.from_bus)

        # Only one slack bus is supported; consequently all buses must
        # belong to its connected electrical island.
        slack = next(b.bus_id for b in self.buses if b.bus_type == "Slack")
        visited, pending = set(), [slack]
        while pending:
            bus_id = pending.pop()
            if bus_id in visited:
                continue
            visited.add(bus_id)
            pending.extend(adjacency[bus_id] - visited)
        if len(visited) != len(existing):
            missing = sorted(existing - visited)
            raise ValueError(f"Disconnected buses not reachable from slack: {missing}")

        for bus in self.buses:
            online = [g for g in self.generators if g.status and g.bus_id == bus.bus_id]
            if bus.bus_type == "PV" and not online:
                raise ValueError(f"PV bus {bus.bus_id} has no online generator")
            if bus.bus_type in ("PV", "Slack") and len(online) > 1:
                setpoints = [g.voltage_setpoint_pu for g in online]
                # Default 1 pu is conventionally an unspecified setpoint
                # in projects constructed directly with these dataclasses.
                specified = [v for v in setpoints if abs(v - 1.0) > 1e-10]
                if specified and max(specified) - min(specified) > 1e-6:
                    raise ValueError(f"Conflicting generator voltage setpoints at bus {bus.bus_id}")
        return True
