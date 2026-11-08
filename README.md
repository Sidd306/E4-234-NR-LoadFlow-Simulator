# E4234 — Newton–Raphson Power System Load Flow Simulator

Desktop single-line-diagram (SLD) application for AC power-flow studies. The computational engine uses NumPy and SciPy sparse operations; the GUI uses PySide6. The solver is implemented within the project: PYPOWER is used only for independent validation, not as the solve engine.

## Requirements

- Python 3.10 or later (tested by the project owner on Windows with Python 3.14)
- Install project requirements as below
- Optional validation dependency: `PYPOWER`

## Installation on Windows (PowerShell)

Open a terminal **in the folder containing `pyproject.toml`**:

```powershell
py -3.14 -m pip install -e .
py -3.14 -m pip install pytest pypower
```

If Python 3.14 is unavailable, use `py -3.12` or `python` with a compatible installation.

## Launch the simulator

```powershell
py -3.14 -m loadflow.gui
```

Create a new network or import MATPOWER (`.m`) / IEEE CDF data. Use the element palette to add buses, lines, transformers, generators, loads, shunts and external-grid connections. Configure properties in the right-hand panel, then check the network and run the Newton–Raphson study. Results appear in the results dock. You can save/reopen editable JSON projects and export results and reports.

## Run tests and validation

```powershell
py -3.14 -m pytest -q
py -3.14 validate.py
py -3.14 benchmark.py
```

`validate.py` uses PYPOWER to compare the **same supplied MATPOWER case data** for IEEE 14-, 30-, 57- and 118-bus systems. Voltage angles are compared relative to the slack-bus angle; the IEEE 118-bus reference has an absolute slack angle of 30° whereas this solver uses 0°. The source network and options must match for fair comparisons.

## Data conventions

- Network power base: MVA; bus voltage magnitudes: p.u.; internal voltage angles: radians
- GUI displays voltage angles in degrees; bus nominal voltage is specified in kV where needed
- Line and transformer impedances used by the solver are in per unit on the system base
- Line charging is total susceptance in p.u.; transformer taps use the supported off-nominal side convention
- Generator and load active/reactive powers are expressed in MW / MVAr
- Line/transformer equipment ratings are in MVA; unassigned ratings must not be interpreted as zero permissible loading

## Architecture

- `src/loadflow/models.py`: network data classes and validation
- `src/loadflow/ybus.py`: sparse admittance matrix
- `src/loadflow/specifications.py`, `power.py`, `mismatch.py`, `jacobian.py`: power-flow equations
- `src/loadflow/solver.py`, `q_limits.py`: iterative NR solution and Q-limit switching
- `src/loadflow/branch_flows.py`, `generator_outputs.py`: outputs
- `src/loadflow/gui/`: single-line-diagram editor and application window
- `src/loadflow/project_io.py`: project JSON serialization
- `src/loadflow/matpower_import.py`, `matpower_export.py`, `ieee_cdf_import.py`: case conversion
- `src/loadflow/reporting.py`: result checks and HTML/PDF report generation
- `tests/`: automated tests

## Known limitations / final GUI checks

The latest source audit found that the README had not been populated, and several graphical requirements still need manual confirmation: right-click context menus, snap-to-grid, a Recent Files menu, an embedded convergence tab, and highlighting buses responsible for divergence. Generator output reporting can be aggregated by bus rather than independently dispatched for each generator. Changing frequency does not automatically rederive frequency-sensitive branch data. Check the requirements in `FINAL_AUDIT.md` before claiming full compliance.

## Submission

Keep Git history in the **original local repository**, make a final commit there, configure the existing GitHub remote and push. The submission ZIP should contain the project source and documentation but normally omit `.git`, caches, and generated `.egg-info`. Provide the instructor access to the private GitHub repository separately.
