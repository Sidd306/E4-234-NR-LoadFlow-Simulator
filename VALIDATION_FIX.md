# Corrected validation method

The previous `validate.py` compared local MATPOWER cases to pandapower bundled test cases, which are not necessarily the same network.

The revised validator reads each *identical* `.m` file into both the custom solver and pandapower with `pp.converter.from_mpc`.

Install (Python 3.14 on Windows):

```powershell
py -3.14 -m pip install -e .
py -3.14 -m pip install pandapower matpowercaseframes
py -3.14 validate.py
```

Important: this change fixes the reference-case mismatch but does NOT guarantee matching results. Remaining failures should be investigated for generator voltage setpoints, bus-index mapping, branch conversion, and power flow conventions.

Pandapower `.m` conversion uses `matpowercaseframes`; some complex MATPOWER scripts may require extra processing.
