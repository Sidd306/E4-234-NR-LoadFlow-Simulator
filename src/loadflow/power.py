
import numpy as np


def calculate_power(Ybus, voltage_mag, voltage_angle):
    # Convert inputs to NumPy arrays
    voltage_mag = np.asarray(voltage_mag, dtype=float)
    voltage_angle = np.asarray(voltage_angle, dtype=float)

    # Construct complex bus voltage vector
    V = voltage_mag * np.exp(1j * voltage_angle)

    # Calculate bus current injections
    I = Ybus @ V

    # Calculate complex power injections
    S = V * np.conj(I)

    P = S.real
    Q = S.imag

    return P, Q
