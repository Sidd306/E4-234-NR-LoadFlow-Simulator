"""Synthetic fixed-column IEEE CDF examples to catch parsing offsets."""
import math
import pytest
from loadflow.ieee_cdf_import import parse_ieee_cdf


def record(fields, width=130):
    chars = [' '] * width
    for a, b, value in fields:
        s = str(value)
        assert len(s) <= b-a+1, (a, b, s)
        chars[a-1:b] = list(s.rjust(b-a+1))
    return ''.join(chars)


def bus(bid, typ, vm, pg=0, qg=0, pd=0, qd=0, basekv=110, target=0):
    return record([(1,4,bid), (25,26,typ), (28,33,vm), (34,40,0),
                   (41,49,pd), (50,59,qd), (60,67,pg), (68,75,qg),
                   (77,83,basekv), (85,90,target), (91,98,100),
                   (99,106,-100)])


def branch(f,t,kind,r,x,b=0,rate=100,tap=0):
    return record([(1,4,f), (6,9,t), (19,19,kind), (20,29,r),
                   (30,40,x), (41,50,b), (51,55,rate), (77,82,tap)])


def example():
    header = record([(32,37,100)], 80)
    return '\n'.join([header, 'BUS DATA FOLLOWS',
        bus(1,3,'1.06',pg=80,target='1.06'),
        bus(2,1,'1.0',pd=40,qd=20),
        bus(3,2,'1.04',pg=30,target='1.04'),
        '-999', 'BRANCH DATA FOLLOWS',
        branch(1,2,0,'.02','.06',b='.03'),
        branch(2,3,1,'.01','.08',tap='.98'),
        '-999', 'END OF DATA'])


def test_parse_cdf_network_with_tapped_transformer():
    net = parse_ieee_cdf(example())
    assert net.base_mva == 100
    assert [b.bus_type for b in net.buses] == ['Slack', 'PQ', 'PV']
    assert len(net.loads) == 1 and net.loads[0].p_mw == 40
    assert len(net.lines) == 1 and len(net.transformers) == 1
    assert math.isclose(net.lines[0].b_pu, .03)
    assert math.isclose(net.transformers[0].tap_ratio, .98)
    assert net.generators[1].voltage_setpoint_pu == 1.04
    net.validate()


def test_rejects_bad_bus_type_with_line_number():
    content = example().replace(bus(2,1,'1.0',pd=40,qd=20), bus(2,9,'1.0',pd=40,qd=20))
    with pytest.raises(ValueError, match='CDF line 4'):
        parse_ieee_cdf(content)


def test_rejects_missing_branch_section():
    content = example().split('BRANCH DATA FOLLOWS')[0]
    with pytest.raises(ValueError, match='BUS DATA and BRANCH DATA'):
        parse_ieee_cdf(content)


def test_rejects_remote_voltage_control():
    content = example()
    lines = content.splitlines()
    changed = list(lines[2])
    changed[123:127] = list('   2')
    lines[2] = ''.join(changed)
    with pytest.raises(ValueError, match='Remote voltage control'):
        parse_ieee_cdf('\n'.join(lines))
