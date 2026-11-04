import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu


def solve_correction(J, mismatch):

    # Convert Jacobian into CSC sparse format
    J_sparse = csc_matrix(J)

    # Perform LU decomposition
    lu = splu(J_sparse)

    # Solve J * correction = mismatch
    correction = lu.solve(mismatch)

    return correction