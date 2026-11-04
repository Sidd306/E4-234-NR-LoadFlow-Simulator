import numpy as np


def build_jacobian(network, Ybus, voltage_mag, voltage_angle,
                   P_calc, Q_calc, p_indices, q_indices):

    # Convert Ybus into conductance and susceptance matrices
    Y = Ybus.toarray()
    G = Y.real
    B = Y.imag

    # Number of equations and unknowns
    nP = len(p_indices)
    nQ = len(q_indices)

    # Initialise Jacobian blocks
    H = np.zeros((nP, nP))
    N = np.zeros((nP, nQ))
    M = np.zeros((nQ, nP))
    L = np.zeros((nQ, nQ))

    # H block: dP / d(theta)
    for a, i in enumerate(p_indices):
        for b, j in enumerate(p_indices):

            if i == j:
                H[a, b] = -Q_calc[i] - B[i, i] * voltage_mag[i]**2

            else:
                theta = voltage_angle[i] - voltage_angle[j]

                H[a, b] = voltage_mag[i] * voltage_mag[j] * (
                    G[i, j] * np.sin(theta)
                    - B[i, j] * np.cos(theta)
                )

    # N block: dP / dV
    for a, i in enumerate(p_indices):
        for b, j in enumerate(q_indices):

            if i == j:
                N[a, b] = P_calc[i] / voltage_mag[i] + G[i, i] * voltage_mag[i]

            else:
                theta = voltage_angle[i] - voltage_angle[j]

                N[a, b] = voltage_mag[i] * (
                    G[i, j] * np.cos(theta)
                    + B[i, j] * np.sin(theta)
                )

    # M block: dQ / d(theta)
    for a, i in enumerate(q_indices):
        for b, j in enumerate(p_indices):

            if i == j:
                M[a, b] = P_calc[i] - G[i, i] * voltage_mag[i]**2

            else:
                theta = voltage_angle[i] - voltage_angle[j]

                M[a, b] = -voltage_mag[i] * voltage_mag[j] * (
                    G[i, j] * np.cos(theta)
                    + B[i, j] * np.sin(theta)
                )

    # L block: dQ / dV
    for a, i in enumerate(q_indices):
        for b, j in enumerate(q_indices):

            if i == j:
                L[a, b] = Q_calc[i] / voltage_mag[i] - B[i, i] * voltage_mag[i]

            else:
                theta = voltage_angle[i] - voltage_angle[j]

                L[a, b] = voltage_mag[i] * (
                    G[i, j] * np.sin(theta)
                    - B[i, j] * np.cos(theta)
                )

    # Assemble the complete Jacobian
    J = np.block([
        [H, N],
        [M, L]
    ])

    return J