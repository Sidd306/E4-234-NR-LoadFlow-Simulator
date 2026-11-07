# Load-flow simulator — corrections and limits

## Corrected files

- `src/loadflow/models.py`: revalidate numerical quantities after GUI edits, branch impedances, generator limits, bus references, network connectivity, and online PV generators.
- `src/loadflow/solver.py`: perform PV-to-PQ Q-limit transitions on a **deep copy** of the input network; report final effective bus types, check correction finiteness and voltage validity, and apply non-default generator setpoints to regulated buses.
- `src/loadflow/generator_outputs.py`: include the implicit external-grid source at a slack bus with no online generator record, so totals and the power balance include this source.
- `src/loadflow/gui/window.py`: reject non-finite editable values, zero line/transformer impedance and negative ratings, update slack-bus setpoint when its generator changes, and display the effective bus type and source classification in results.
- `tests/test_q_limit_integration.py`: changed the old test that expected permanent mutation of the input network.
- `tests/test_regressions.py`: new tests for disconnected buses, invalid branch edits, external grid reporting, regulated voltage, and non-destructive Q limits.

All other computation files remain as supplied, because these tests did not establish a mathematical defect in their equations.

## Known limitations / decisions

1. **Generator setpoint ambiguity:** legacy Generator objects default to 1.0 p.u. This implementation treats that default as *unspecified* when the associated regulated bus explicitly has a different initialized voltage. A generator setpoint different from 1.0 p.u. overrides the bus voltage. If you need to specify exactly 1.0 p.u. while the bus is different, set the bus to 1.0 p.u. too. A future model version should use `None` for an unspecified setpoint.
2. **Reactive limits:** PV-to-PQ switching enforces aggregate bus generator limits after initial convergence. Automatic PQ-to-PV reversal and detailed individual-machine reactive dispatch are not implemented. The input network now remains unchanged.
3. **Island handling:** one slack and one connected network are supported. Separate islands require partitioning into independent studies.
4. **Power units:** generator/load values are MW and MVAr. Branch impedances and shunts are p.u. on the common system base; the GUI does not convert ohms to p.u. because it has no reliable base-kV specification for every branch.
5. **Output classification:** a slack bus with no explicit generator represents an external grid, and source power is computed from its solved injection and any local load. Per-bus generation is still aggregated when multiple generators share a bus.
6. **Independent verification:** the regression tests establish convergence, consistency, and power balance. They do not replace reference comparisons to MATPOWER or pandapower for every case.
7. **GUI testing:** source code compiles, but the graphical interface was not interactively exercised here.

## Run

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest -q
python -m loadflow.gui
```

Run commands from the project root. For local testing without editable installation, use `PYTHONPATH=src python -m pytest -q` on Linux/macOS, or `$env:PYTHONPATH="src"; python -m pytest -q` in PowerShell.
