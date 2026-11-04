import numpy as np


def update_voltages(voltage_mag, voltage_angle,
                    correction, p_indices, q_indices):

    voltage_mag = np.array(voltage_mag, dtype=float, copy=True)
    voltage_angle = np.array(voltage_angle, dtype=float, copy=True)

    nP = len(p_indices)

    # Update voltage angles (PV and PQ buses)
    delta_angle = correction[:nP]

    for k, i in enumerate(p_indices):
        voltage_angle[i] += delta_angle[k]

    # Update voltage magnitudes (PQ buses only)
    delta_voltage = correction[nP:]

    for k, i in enumerate(q_indices):
        voltage_mag[i] += delta_voltage[k]

    return voltage_mag, voltage_angle