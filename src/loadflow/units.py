"""Explicit power-system units; no implicit assumptions about physical data."""
import math

def impedance_base_ohm(base_kv,base_mva):
    """3-phase Zbase = (line-to-line kV)^2 / 3-phase MVA."""
    if not all(math.isfinite(float(x)) and float(x)>0 for x in (base_kv,base_mva)):
        raise ValueError('Base voltage (kV) and power (MVA) must be positive')
    return base_kv**2/base_mva

def line_ohm_to_pu(r_ohm,x_ohm,base_kv,base_mva):
    zbase=impedance_base_ohm(base_kv,base_mva)
    if not all(math.isfinite(float(v)) for v in (r_ohm,x_ohm)):
        raise ValueError('Line resistance and reactance must be finite')
    if r_ohm==0 and x_ohm==0:
        raise ValueError('Line impedance must not be zero')
    return r_ohm/zbase,x_ohm/zbase

def line_pu_to_ohm(r_pu,x_pu,base_kv,base_mva):
    zbase=impedance_base_ohm(base_kv,base_mva)
    return r_pu*zbase,x_pu*zbase


def transformer_nameplate_to_system_pu(z_percent, x_over_r, rated_mva,
                                       rated_hv_kv, system_mva, system_hv_kv):
    """Convert leakage %Z and positive X/R to R+jX on a system base.

    Both voltages are line-to-line values on the *same HV side* of the
    transformer. Conversion assumes the quoted impedance is referred to
    its rated HV winding. Off-nominal tap ratio is handled separately.
    """
    inputs = (z_percent, x_over_r, rated_mva, rated_hv_kv,
              system_mva, system_hv_kv)
    if not all(math.isfinite(float(v)) for v in inputs):
        raise ValueError('Transformer nameplate inputs must be finite')
    if not (z_percent > 0 and x_over_r > 0 and rated_mva > 0 and
            rated_hv_kv > 0 and system_mva > 0 and system_hv_kv > 0):
        raise ValueError('Transformer %Z, X/R, MVA and voltages must be positive')
    z_machine = z_percent / 100.0
    r_machine = z_machine / math.sqrt(1 + x_over_r**2)
    x_machine = r_machine * x_over_r
    factor = (system_mva / rated_mva) * (rated_hv_kv / system_hv_kv)**2
    return r_machine * factor, x_machine * factor


def transformer_system_pu_to_nameplate(r_pu, x_pu, rated_mva,
                                       rated_hv_kv, system_mva, system_hv_kv):
    """Inverse of transformer_nameplate_to_system_pu (positive R, X)."""
    vals = (r_pu, x_pu, rated_mva, rated_hv_kv, system_mva, system_hv_kv)
    if not all(math.isfinite(float(v)) for v in vals):
        raise ValueError('Transformer inputs must be finite')
    if r_pu <= 0 or x_pu <= 0 or min(rated_mva, rated_hv_kv, system_mva, system_hv_kv) <= 0:
        raise ValueError('Inverse conversion requires positive R, X and bases')
    factor = (system_mva / rated_mva) * (rated_hv_kv / system_hv_kv)**2
    return 100 * math.hypot(r_pu, x_pu) / factor, x_pu / r_pu
