# IEEE Load Flow Performance and Reference Validation

## Results recorded by the project owner (Windows, Python 3.14)

| Case | Converged | NR updates in `benchmark.py` | Total time (ms) | Mean time per update (ms) | Final maximum mismatch (p.u.) |
|---|---|---:|---:|---:|---:|
| IEEE 14 | Yes | 2 | 3.673 | 1.837 | 1.316e-10 |
| IEEE 30 | Yes | 2 | 7.382 | 3.691 | 3.469e-09 |
| IEEE 57 | Yes | 3 | 33.148 | 11.049 | 3.449e-12 |
| IEEE 118 | Yes | 3 | 90.636 | 30.212 | 1.506e-12 |

## PYPOWER comparison (same input MATPOWER case file)

The owner ran `validate.py` locally and all four cases passed checks for voltage magnitudes, **relative** voltage angles, generator outputs, branch flows, active losses and reactive losses. The solver's validation run reported 4 iterations for each case; do not compare those iteration counts directly with the `benchmark.py` NR-update counts without checking initialization and counting conventions.

| Case | Max abs V error (p.u.) | Max abs relative-angle error (deg) | Max abs generator output error (MW / MVAr) | Max abs branch-flow error (MW / MVAr) | Overall |
|---|---:|---:|---:|---:|---|
| IEEE 14 | 6.661e-16 | 2.842e-14 | 3.801e-13 | 3.606e-13 | PASS |
| IEEE 30 | 1.332e-15 | 9.948e-14 | 1.322e-12 | 1.389e-12 | PASS |
| IEEE 57 | 2.038e-12 | 1.122e-10 | 9.902e-11 | 1.779e-10 | PASS |
| IEEE 118 | 2.109e-14 | 1.802e-13 | 3.577e-11 | 4.630e-11 | PASS |

**Angle convention:** the reference IEEE 118-bus slack angle is 30° and this solver's is 0°. Normalizing each solution to its reference angle removes a physically irrelevant common angular offset; it does not verify preservation of absolute input slack angles.

## Fresh check on uploaded project (this audit environment)

- `python -m pytest -q`: **58 tests passed**.
- `python benchmark.py`: all four cases converged; local timings differ due to execution environment (14: 4.502 ms, 30: 12.232 ms, 57: 72.417 ms, 118: 180.408 ms).
- The PYPOWER reference comparison was not rerun in this environment because PYPOWER was unavailable; the above reference results are the user-supplied Windows output.

Times depend strongly on hardware, installed library versions and warm-up. Quote the Windows measurements if reporting performance on the owner's machine.
