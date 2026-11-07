import math
from pathlib import Path
import pytest
from loadflow.models import Network, Bus, Line, Load
from loadflow.solver import solve_newton_raphson
from loadflow.units import impedance_base_ohm, line_ohm_to_pu, line_pu_to_ohm
from loadflow.reporting import collect_violations, export_html_report, export_pdf_report


def test_line_impedance_conversion():
    assert impedance_base_ohm(11, 100) == pytest.approx(1.21)
    r, x = line_ohm_to_pu(0.121, 0.242, 11, 100)
    assert (r, x) == pytest.approx((0.1, 0.2))
    assert line_pu_to_ohm(r,x,11,100) == pytest.approx((0.121, 0.242))
    with pytest.raises(ValueError):
        line_ohm_to_pu(0,0,11,100)


def small_network():
    net=Network()
    net.add_bus(Bus(1, bus_type='Slack',nominal_kv=11))
    net.add_bus(Bus(2,nominal_kv=11,vmin_pu=0.999,vmax_pu=1.001))
    net.add_line(Line(1,2,0.01,0.1, rate_mva=1))
    net.add_load(Load(2,p_mw=10,q_mvar=4))
    return net


def test_report_and_violations(tmp_path):
    net=small_network()
    res=solve_newton_raphson(net,enforce_q_limits=False)
    assert res['converged']
    issues=collect_violations(net,res)
    assert any(x['kind']=='Loading' for x in issues)
    assert any(x['kind']=='Voltage' for x in issues)
    h=tmp_path/'report.html'
    p=tmp_path/'report.pdf'
    export_html_report(h,net,res)
    export_pdf_report(p,net,res)
    assert 'Bus results' in h.read_text()
    assert 'V (kV)' in h.read_text()
    assert p.read_bytes()[:4] == b'%PDF'


def test_unrated_branch_not_violation():
    net=small_network()
    net.lines[0].rate_mva=0
    result=solve_newton_raphson(net,enforce_q_limits=False)
    assert all(x['kind'] != 'Loading' for x in collect_violations(net,result))
