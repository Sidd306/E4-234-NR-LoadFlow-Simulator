from scipy.sparse import lil_matrix
import math

def build_ybus(network):

    network.validate()

    n = len(network.buses)

    # Map bus IDs to matrix indices
    bus_index = {
        bus.bus_id: i
        for i, bus in enumerate(network.buses)
    }

    # Initialise sparse Ybus matrix
    Ybus = lil_matrix((n, n), dtype=complex)

    # Add transmission line contributions
    for line in network.lines:

        if not line.status:
            continue

        i = bus_index[line.from_bus]
        j = bus_index[line.to_bus]

        z = complex(line.r_pu, line.x_pu)
        y = 1 / z

        y_sh = 1j * line.b_pu / 2

        Ybus[i, i] += y + y_sh
        Ybus[j, j] += y + y_sh

        Ybus[i, j] -= y
        Ybus[j, i] -= y

    for shunt in network.shunts:
        if not shunt.status:
            continue

        i = bus_index[shunt.bus_id]
        Ybus[i, i] += complex(shunt.g_pu, shunt.b_pu)
    for transformer in network.transformers:
        if not transformer.status:
            continue

        i = bus_index[transformer.from_bus]
        j = bus_index[transformer.to_bus]

        z = complex(transformer.r_pu, transformer.x_pu)
        y = 1 / z

        phi = math.radians(transformer.phase_shift_deg)
        a = transformer.tap_ratio * complex(
            math.cos(phi), math.sin(phi)
        )

        Ybus[i, i] += y / abs(a)**2
        Ybus[i, j] -= y / a.conjugate()
        Ybus[j, i] -= y / a
        Ybus[j, j] += y
    
    return Ybus.tocsr(), bus_index