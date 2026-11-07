"""Benchmark our own NR solver on the four IEEE networks (no external solver)."""
from pathlib import Path
from time import perf_counter
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from loadflow.matpower_import import load_matpower_case
from loadflow.solver import solve_newton_raphson

print(f"{'Case':<18} {'Converged':<12} {'Updates':>8} {'Total ms':>12} {'ms/update':>12} {'Max mismatch':>16}")
for filename in ('case14.m', 'case_ieee30.m', 'case57.m', 'case118.m'):
    net = load_matpower_case(ROOT / 'data' / filename)
    result = solve_newton_raphson(net, tolerance=1e-8, enforce_q_limits=False)
    updates = result['iterations']
    mismatch = max(abs(x) for x in result['mismatch']) if len(result['mismatch']) else 0.0
    print(f"{filename:<18} {str(result['converged']):<12} {updates:>8} {result['solve_time_s']*1000:>12.3f} {result['solve_time_s']*1000/max(1, updates):>12.3f} {mismatch:>16.3e}")
