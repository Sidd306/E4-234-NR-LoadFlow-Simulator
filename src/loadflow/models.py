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

    def __post_init__(self):
        if self.bus_id <= 0:
            raise ValueError("Bus ID must be positive")

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
        if self.base_mva <= 0:
            raise ValueError("Base MVA must be positive")

        if not self.buses:
            raise ValueError("Network must contain at least one bus")

        bus_ids = [bus.bus_id for bus in self.buses]

        if len(bus_ids) != len(set(bus_ids)):
            raise ValueError("Duplicate bus IDs found")

        slack_count = sum(
            bus.bus_type == "Slack" for bus in self.buses
        )

        if slack_count != 1:
            raise ValueError("Network must contain exactly one Slack bus")

        existing_buses = set(bus_ids)

        for component in self.generators + self.loads + self.shunts:
            if component.bus_id not in existing_buses:
                raise ValueError(
                    f"Bus {component.bus_id} does not exist"
                )

        for component in self.lines + self.transformers:
            if component.from_bus not in existing_buses:
                raise ValueError(
                    f"Bus {component.from_bus} does not exist"
                )

            if component.to_bus not in existing_buses:
                raise ValueError(
                    f"Bus {component.to_bus} does not exist"
                )

        return True