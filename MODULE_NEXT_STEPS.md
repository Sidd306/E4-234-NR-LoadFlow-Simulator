# Module A1 — ZIP / constant-impedance loads

This update implements the assignment's second load model requirement without changing the default `Load` behavior.

## How to use it in Python

```python
from loadflow.models import Load

pq = Load(bus_id=3, p_mw=50, q_mvar=20)  # legacy constant PQ
constant_z = Load(bus_id=3, p_mw=50, q_mvar=20, model="Z")
zip_load = Load(bus_id=3, p_mw=50, q_mvar=20, model="ZIP",
                p_zip=(0.3, 0.2, 0.5), q_zip=(0.1, 0.3, 0.6))
```

ZIP coefficients are ordered (constant-impedance Z, constant-current I, constant-power P); each vector must sum to one. P and Q in MW/MVAr denote load at 1 pu voltage. Each operating voltage uses:

P(V) = P0 * (zP * V**2 + iP * V + pP)
Q(V) = Q0 * (zQ * V**2 + iQ * V + pQ)

The mismatch is updated each iteration, and the NR Jacobian includes the voltage derivative of specified power. Generator output, reactive limit checks, and system balance use actual voltage-dependent demand.

## Local workflow (Windows PowerShell)

1. Back up your Git-tracked project folder first.
2. Copy the six changed code files and new test file into your existing repository, keeping the directory structure; DO NOT copy a .git directory.
3. From the original repository root:

```powershell
py -3.14 -m pip install -e .
py -3.14 -m pytest -q
py -3.14 validate.py
```

4. Check that all four IEEE cases still PASS, since their original PQ models must remain unchanged.
5. Commit this module separately:

```powershell
git add src/loadflow/models.py src/loadflow/specifications.py src/loadflow/solver.py src/loadflow/generator_outputs.py src/loadflow/q_limits.py tests/test_zip_loads.py MODULE_NEXT_STEPS.md
git commit -m "Module A1: Add ZIP and constant impedance load models"
```

## Current scope

- The backend accepts PQ, Z, ZIP. **GUI load editor controls have not been updated yet**; this is the next separate GUI module.
- PQ->PV back-switching and user-settable study controls are separate pending assignment features.
- This package has been verified with pytest (22 tests); PYPOWER validation could not be rerun in the packaging environment because the dependency was absent.
