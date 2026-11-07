"""GUI-independent result checks and HTML/PDF report creation."""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
import math


def collect_violations(network, results, vmin=0.95, vmax=1.05):
    """Return violations with stable keys. Unrated branches are not overloaded."""
    if not results or not results.get('converged'):
        return []
    issues = []
    for i, bus in enumerate(network.buses):
        v = float(results['voltage_mag'][i])
        low = getattr(bus, 'vmin_pu', vmin)
        high = getattr(bus, 'vmax_pu', vmax)
        if v < low or v > high:
            issues.append({'kind':'Voltage','element':f'Bus {bus.bus_id}',
                           'value':v, 'limit':low if v < low else high,
                           'severity':'Low' if v < low else 'High'})
    for branch in results.get('branch_flows', []):
        loading = branch.get('loading_percent')
        if loading is None or not math.isfinite(float(loading)):
            continue
        if float(loading) >= 80:
            issues.append({'kind':'Loading',
                           'element':f"{branch['element_type']} {branch['from_bus']}-{branch['to_bus']}",
                           'value':float(loading), 'limit':100.0,
                           'severity':'Overload' if float(loading)>100 else 'Warning'})
    return issues


def report_tables(network, results):
    if not results or not results.get('converged'):
        raise ValueError('A converged load-flow result is required')
    base=network.base_mva
    bus_rows=[]
    for i,bus in enumerate(network.buses):
        kv = getattr(bus,'nominal_kv',None)
        bus_rows.append([bus.bus_id,bus.bus_type,
            round(float(results['voltage_mag'][i]),6),
            '' if not kv else round(float(results['voltage_mag'][i])*kv,4),
            round(math.degrees(float(results['voltage_angle'][i])),5),
            round(float(results['P_calc'][i])*base,5),
            round(float(results['Q_calc'][i])*base,5)])
    branches=[]
    for x in results.get('branch_flows',[]):
        branches.append([x['element_type'],x['from_bus'],x['to_bus'],
            round(float(x['P_from_mw']),5),round(float(x['Q_from_mvar']),5),
            round(float(x['P_to_mw']),5),round(float(x['Q_to_mvar']),5),
            '' if x['loading_percent'] is None else round(float(x['loading_percent']),2)])
    summary=results.get('system_summary',{})
    return {
      'Bus results': (['Bus','Type','V (pu)','V (kV)','Angle (deg)','P inj (MW)','Q inj (MVAr)'],bus_rows),
      'Branch results': (['Type','From','To','P from (MW)','Q from (MVAr)','P to (MW)','Q to (MVAr)','Loading (%)'],branches),
      'System summary': (['Parameter','Value'],[[k,v] for k,v in summary.items()]),
      'Violations': (['Kind','Element','Value','Limit','Severity'],[[v[k] for k in ('kind','element','value','limit','severity')] for v in collect_violations(network,results)]),
    }


def _report_title(network,results):
    return (f'AC Load Flow Report | {len(network.buses)} buses | '
            f'Base {network.base_mva:g} MVA | '
            f"Iterations {results.get('iterations','?')}")


def export_html_report(path,network,results,diagram_path=None):
    tables=report_tables(network,results)
    css='''body{font-family:Arial,sans-serif;margin:32px;color:#223}h1{color:#18354d}table{border-collapse:collapse;width:100%;margin-bottom:24px;font-size:12px}th,td{border:1px solid #cad3dc;padding:6px;text-align:left}th{background:#e8f0f6}tr:nth-child(even){background:#f7f9fb}'''
    parts=['<!doctype html><html><head><meta charset="utf-8"><title>AC Load Flow Report</title>',
           f'<style>{css}</style></head><body>',f'<h1>{escape(_report_title(network,results))}</h1>',
           f'<p>Generated {escape(datetime.now().strftime("%Y-%m-%d %H:%M"))}</p>']
    if diagram_path:
        import base64
        raw=Path(diagram_path).read_bytes()
        encoded=base64.b64encode(raw).decode('ascii')
        parts.append(f'<h2>Single-line diagram</h2><img alt="Single-line diagram" style="max-width:100%" src="data:image/png;base64,{encoded}">')
    for name,(headers,rows) in tables.items():
        parts.append(f'<h2>{escape(name)}</h2><table><thead><tr>')
        parts.extend(f'<th>{escape(str(h))}</th>' for h in headers)
        parts.append('</tr></thead><tbody>')
        for row in rows:
            parts.append('<tr>')
            parts.extend(f'<td>{escape(str(v))}</td>' for v in row)
            parts.append('</tr>')
        parts.append('</tbody></table>')
    parts.append('</body></html>')
    Path(path).write_text(''.join(parts),encoding='utf-8')


def export_pdf_report(path,network,results,diagram_path=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
    styles=getSampleStyleSheet()
    doc=SimpleDocTemplate(str(path),pagesize=landscape(A4),leftMargin=15*mm,
        rightMargin=15*mm,topMargin=14*mm,bottomMargin=14*mm)
    story=[Paragraph(escape(_report_title(network,results)),styles['Title']),Spacer(1,6*mm)]
    usable=landscape(A4)[0]-30*mm
    if diagram_path:
        from reportlab.lib.utils import ImageReader
        im = ImageReader(str(diagram_path))
        iw, ih = im.getSize()
        ratio = min(usable / iw, 100*mm / ih, 1.0)
        story.extend([Paragraph('Single-line diagram', styles['Heading2']),
                      Image(str(diagram_path),width=iw*ratio,height=ih*ratio),Spacer(1,5*mm)])
    for title,(headers,rows) in report_tables(network,results).items():
        story.append(Paragraph(escape(title),styles['Heading2']))
        max_rows=2000
        if len(rows)>max_rows:
            rows=rows[:max_rows]
        data=[[str(v)[:36] for v in headers]]+[[str(v)[:36] for v in row] for row in rows]
        if len(data)==1:
            data.append(['']*len(headers))
        widths=[usable/len(headers)]*len(headers)
        tbl=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f0f6')),
            ('GRID',(0,0),(-1,-1),0.25,colors.HexColor('#cbd5e1')),
            ('FONTSIZE',(0,0),(-1,-1),7),('LEADING',(0,0),(-1,-1),9),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),
            ('RIGHTPADDING',(0,0),(-1,-1),4),
        ]))
        story.extend([tbl,Spacer(1,5*mm)])
    doc.build(story)
