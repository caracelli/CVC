#!/usr/bin/env python3
"""
Gera o relatório CVC IAM Analytics no formato PBIR (Enhanced Report Format).
Power BI Desktop 2.153 / PBIR schema 2.8  (abril 2026).
Executar: python scripts/gerar_report_json.py
"""

import json
import random
import shutil
import string
from pathlib import Path

SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.8.0/schema.json"
SCHEMA_PAGE   = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
SCHEMA_PAGES  = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
SCHEMA_REPORT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.2.0/schema.json"
SCHEMA_VER    = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"


# ── Primitive helpers ─────────────────────────────────────────────────────────

def uid():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=20))


def bl(v):
    return {"expr": {"Literal": {"Value": "true" if v else "false"}}}


def num(n):
    return {"expr": {"Literal": {"Value": f"{n}D"}}}


def st(text):
    return {"expr": {"Literal": {"Value": f"'{text}'"}}}


def clr(hex_color):
    # Visual-level color property: same expr/Literal pattern as strings/numbers
    return {"expr": {"Literal": {"Value": f"'{hex_color}'"}}}


def paint(hex_color):
    # Page-level "paint" property (background/outspace) — PBI saves with solid.color wrapper
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_color}'"}}}}}


def col_field(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def msr_field(entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(entity, prop, kind="Column"):
    f = col_field(entity, prop) if kind == "Column" else msr_field(entity, prop)
    return {"field": f, "queryRef": f"{entity}.{prop}", "active": True}


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def vfile(x, y, z, w, h, visual_def, filter_cfg=None):
    name = uid()
    v = {
        "$schema": SCHEMA_VISUAL,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": visual_def,
    }
    if filter_cfg:
        v["filterConfig"] = filter_cfg
    return v


# ── Decorative visuals ────────────────────────────────────────────────────────

def shape_rect(x, y, z, w, h, fill, border=None, border_w=0):
    bc = border or fill
    return vfile(x, y, z, w, h, {
        "visualType": "shape",
        "objects": {
            "fill": [{"properties": {
                "show":      bl(True),
                "fillColor": clr(fill),
            }}],
            "line": [{"properties": {
                "show":      bl(True if border_w > 0 else False),
                "lineColor": clr(bc),
                "weight":    num(border_w),
            }}],
            "general": [{"properties": {"shapeType": st("rectangle")}}],
        },
    })


def para(text, size_pt, bold=False, color="#000000", font="Segoe UI", align="Left"):
    style = {"fontSize": f"{size_pt}pt", "fontFamily": font, "color": color}
    if bold:
        style["fontWeight"] = "Bold"
    return {
        "textRuns": [{"value": text, "textRunStyle": style}],
        "paragraphStyle": {"textAlignment": align},
    }


def textbox(x, y, z, w, h, paragraphs):
    return vfile(x, y, z, w, h, {
        "visualType": "textbox",
        "objects": {
            "general": [{"properties": {"paragraphs": paragraphs}}],
            "background": [{"properties": {"show": bl(False)}}],
        },
    })


# ── Data visuals ──────────────────────────────────────────────────────────────

def card(x, y, z, w, h, entity, measure, font_color="#222222", reject_highlight=False):
    fcfg = {"rejectHighlight": True} if reject_highlight else None
    return vfile(x, y, z, w, h, {
        "visualType": "card",
        "query": {"queryState": {
            "Values": {"projections": [proj(entity, measure, "Measure")]},
        }},
        "objects": {
            "labels": [{"properties": {
                "fontSize":   num(28),
                "fontFamily": st("Segoe UI"),
                "color":      clr(font_color),
            }}],
            "categoryLabels": [{"properties": {
                "show":     bl(True),
                "fontSize": num(10),
                "color":    clr("#555555"),
            }}],
            "border":     [{"properties": {"show": bl(False)}}],
            "title":      [{"properties": {"show": bl(False)}}],
            "background": [{"properties": {"show": bl(False)}}],
        },
    }, fcfg)


def slicer_tile(x, y, z, w, h, entity, column):
    return vfile(x, y, z, w, h, {
        "visualType": "slicer",
        "query": {"queryState": {
            "Values": {"projections": [proj(entity, column, "Column")]},
        }},
        "objects": {
            "general":   [{"properties": {"orientation": st("Horizontal")}}],
            "selection": [{"properties": {
                "selectAllCheckboxEnabled": bl(True),
                "singleSelect":            bl(False),
            }}],
        },
    })


def pivot_table(x, y, z, w, h, filter_type=None):
    visual_def = {
        "visualType": "pivotTable",
        "query": {"queryState": {
            "Rows": {"projections": [
                proj("Divergencias", "usuario", "Column"),
                proj("Divergencias", "id",      "Column"),
            ]},
            "Values": {"projections": [
                proj("Divergencias", "nome_usuario",        "Column"),
                proj("Divergencias", "matricula",           "Column"),
                proj("Divergencias", "tipo",                "Column"),
                proj("Divergencias", "perfil_encontrado",   "Column"),
                proj("Divergencias", "perfil_esperado",     "Column"),
                proj("Divergencias", "data_identificacao",  "Column"),
                proj("Divergencias", "resolvida",           "Column"),
            ]},
        }},
        "objects": {
            "rowHeaders": [{"properties": {
                "stepped":                  bl(True),
                "steppedLayoutIndentation": num(20),
                "fontColor":                clr("#FFFFFF"),
                "background":               clr("#1F2D5C"),
            }}],
            "subTotals": [{"properties": {
                "rowSubtotals":    bl(False),
                "columnSubtotals": bl(False),
            }}],
            "columnHeaders": [{"properties": {
                "fontColor":  clr("#FFFFFF"),
                "background": clr("#1F2D5C"),
                "fontBold":   bl(True),
            }}],
            "general": [{"properties": {"layout": st("Tabular")}}],
        },
    }
    filter_cfg = None
    if filter_type:
        filter_cfg = {"filters": [{
            "name": uid(),
            "field": col_field("Divergencias", "tipo"),
            "type": "Categorical",
            "filter": {
                "Version": 2,
                "From":  [{"Name": "d", "Entity": "Divergencias", "Type": 0}],
                "Where": [{"Condition": {"In": {
                    "Expressions": [{"Column": {
                        "Expression": {"SourceRef": {"Source": "d"}},
                        "Property": "tipo",
                    }}],
                    "Values": [[{"Literal": {"Value": f"'{filter_type}'"}}]],
                }}}],
            },
            "howCreated": "User",
        }]}
    return vfile(x, y, z, w, h, visual_def, filter_cfg)


def bar_chart_depto(x, y, z, w, h):
    """Mini bar chart por departamento — para sidebar."""
    return vfile(x, y, z, w, h, {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [proj("RH_Ativos",    "departamento",      "Column")]},
                "Y":        {"projections": [proj("Divergencias", "Total Divergências", "Measure")]},
            },
            "sortDefinition": {"sort": [{
                "field":     msr_field("Divergencias", "Total Divergências"),
                "direction": "Descending",
            }]},
        },
        "objects": {
            "title": [{"properties": {
                "show":       bl(True),
                "titleText":  st("Por Departamento"),
                "fontFamily": st("Segoe UI"),
                "fontSize":   num(10),
                "fontBold":   bl(True),
            }}],
            "valueAxis":    [{"properties": {"show": bl(False)}}],
            "categoryAxis": [{"properties": {"show": bl(True)}}],
            "labels": [{"properties": {"show": bl(True), "fontSize": num(9)}}],
            "background": [{"properties": {
                "show":  bl(True),
                "color": clr("#FFFFFF"),
            }}],
        },
    }, {"rejectHighlight": True})


def bar_chart_tipo(x, y, z, w, h):
    return vfile(x, y, z, w, h, {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [proj("Divergencias", "tipo",              "Column")]},
                "Y":        {"projections": [proj("Divergencias", "Total Divergências", "Measure")]},
            },
            "sortDefinition": {"sort": [{
                "field":     msr_field("Divergencias", "Total Divergências"),
                "direction": "Descending",
            }]},
        },
        "objects": {
            "title": [{"properties": {
                "show":       bl(True),
                "titleText":  st("Divergencias por Tipo"),
                "fontFamily": st("Segoe UI"),
                "fontSize":   num(11),
                "fontBold":   bl(True),
            }}],
            "valueAxis":    [{"properties": {"show": bl(True)}}],
            "categoryAxis": [{"properties": {"show": bl(True)}}],
            "labels": [{"properties": {"show": bl(True), "fontSize": num(9)}}],
            "background": [{"properties": {
                "show":  bl(True),
                "color": clr("#FFFFFF"),
            }}],
        },
    })


def donut_sistema(x, y, z, w, h):
    return vfile(x, y, z, w, h, {
        "visualType": "donutChart",
        "query": {"queryState": {
            "Category": {"projections": [proj("Divergencias", "sistema",            "Column")]},
            "Y":        {"projections": [proj("Divergencias", "Total Divergências", "Measure")]},
        }},
        "objects": {
            "title": [{"properties": {
                "show":       bl(True),
                "titleText":  st("Por Sistema"),
                "fontFamily": st("Segoe UI"),
                "fontSize":   num(11),
                "fontBold":   bl(True),
            }}],
            "background": [{"properties": {
                "show":  bl(True),
                "color": clr("#FFFFFF"),
            }}],
            "legend": [{"properties": {"show": bl(True)}}],
        },
    })


def line_chart_evolucao(x, y, z, w, h):
    return vfile(x, y, z, w, h, {
        "visualType": "lineChart",
        "query": {"queryState": {
            "Category": {"projections": [proj("Divergencias", "data_identificacao", "Column")]},
            "Y":        {"projections": [proj("Divergencias", "Total Divergências", "Measure")]},
        }},
        "objects": {
            "title": [{"properties": {
                "show":       bl(True),
                "titleText":  st("Evolucao Historica"),
                "fontFamily": st("Segoe UI"),
                "fontSize":   num(11),
                "fontBold":   bl(True),
            }}],
            "background": [{"properties": {
                "show":  bl(True),
                "color": clr("#FFFFFF"),
            }}],
        },
    })


def table_detalhe(x, y, z, w, h):
    return vfile(x, y, z, w, h, {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": [
            proj("Divergencias", "tipo",               "Column"),
            proj("Divergencias", "perfil_encontrado",  "Column"),
            proj("Divergencias", "perfil_esperado",    "Column"),
            proj("Divergencias", "descricao",          "Column"),
            proj("Divergencias", "data_identificacao", "Column"),
            proj("Divergencias", "resolvida",          "Column"),
        ]}}},
        "objects": {
            "title": [{"properties": {
                "show":      bl(True),
                "titleText": st("Detalhe da Divergencia Selecionada"),
            }}],
        },
    })


# ── Layout constants ──────────────────────────────────────────────────────────

# Header: Y=0, H=70
# Nav bar: Y=70, H=40
# Filter bar: Y=110, H=44  (label + slicer)
# Content: Y=158 onwards

_HEADER_H  = 70
_NAV_H     = 40
_FILTER_H  = 44
_CONTENT_Y = _HEADER_H + _NAV_H + _FILTER_H   # = 154

_NAV_PAGES = [
    ("Visao Geral",         "ReportSection_VisaoGeral"),
    ("Lista Divergencias",  "ReportSection_ListaDiv"),
    ("Perfis Invalidos",    "ReportSection_PerfisInv"),
    ("Sem Vinculo RH",      "ReportSection_SemVinculo"),
]
_TAB_W   = 183
_TAB_GAP = 4

_SIDEBAR_W  = 210   # sidebar width
_MAIN_X     = _SIDEBAR_W + 8   # main panel X start
_MAIN_W     = 1440 - _MAIN_X - 8  # main panel width


# ── Shared zones ──────────────────────────────────────────────────────────────

def build_header(page_section):
    title_map = {s: n for n, s in _NAV_PAGES}
    page_label = title_map.get(page_section, "")
    return [
        # Blue header bar
        shape_rect(0, 0, 100, 1440, _HEADER_H, "#1F2D5C"),
        # Yellow left accent strip
        shape_rect(0, 0, 110, 6, _HEADER_H, "#F5B800"),
        # Title
        textbox(18,  8, 120, 400, 28,
                [para("IAM Analytics", 18, bold=True, color="#FFFFFF")]),
        # Subtitle
        textbox(18, 40, 120, 500, 20,
                [para("Governanca de Acessos - CVC Corp", 10, color="#B0BEC5")]),
        # Right: page indicator
        textbox(1090,  8, 120, 330, 28,
                [para(page_label, 13, bold=True, color="#F5B800", align="Right")]),
        # Right: date ref
        textbox(1090, 40, 120, 330, 20,
                [para("Referencia: Abril / 2026", 9, color="#B0BEC5", align="Right")]),
    ]


def build_nav(active_section):
    visuals = [
        # Gray nav background
        shape_rect(0, _HEADER_H, 200, 1440, _NAV_H, "#EAECF0"),
    ]
    x = 16
    for name, section in _NAV_PAGES:
        active = (section == active_section)
        bg = "#F5B800" if active else "#FFFFFF"
        fc = "#1F2D5C" if active else "#555555"
        visuals.append(shape_rect(x, _HEADER_H + 4, 210, _TAB_W, _NAV_H - 8, bg))
        visuals.append(textbox(
            x, _HEADER_H + 6, 220, _TAB_W, _NAV_H - 12,
            [para(name, 10, bold=active, color=fc, align="Center")],
        ))
        x += _TAB_W + _TAB_GAP
    return visuals


def build_filter():
    fy = _HEADER_H + _NAV_H
    return [
        shape_rect(0, fy, 300, 1440, _FILTER_H, "#F2F4F7"),
        textbox(16, fy + 12, 310, 100, 22,
                [para("Filtrar por Sistema:", 10, bold=True, color="#333333")]),
        slicer_tile(120, fy + 8, 320, 1100, 30, "Divergencias", "sistema"),
    ]


def make_page_json(name, display_name):
    return {
        "$schema":       SCHEMA_PAGE,
        "name":          name,
        "displayName":   display_name,
        "displayOption": "ActualSize",
        "height": 900,
        "width":  1440,
        "objects": {
            "background": [{"properties": {"color": paint("#F2F4F7")}}],
        },
    }


# ── Page: Lista de Divergências (primary — matches mockup) ────────────────────

def page_lista_divergencias():
    """
    Layout fiel ao mockup:
      Sidebar (210px): 5 KPI cards + mini bar chart departamento
      Main panel: pivot table + detail table below
    """
    v = build_header("ReportSection_ListaDiv")
    v += build_nav("ReportSection_ListaDiv")
    v += build_filter()

    page_h  = 900
    avail_h = page_h - _CONTENT_Y   # 746

    # ── SIDEBAR ──────────────────────────────────────────────────────────────
    # White background for sidebar
    v.append(shape_rect(0, _CONTENT_Y, 350, _SIDEBAR_W, avail_h, "#FFFFFF",
                        "#E0E0E0", 1))

    cards_cfg = [
        ("RH_Ativos",    "Total Funcionários Ativos", "#2980B9", "#EBF5FB", "#D5E8F5"),
        ("SYSTUR",       "Total Usuários SYSTUR",     "#2471A3", "#EBF5FB", "#D5E8F5"),
        ("Divergencias", "Perfis Inválidos",           "#E67E22", "#FEF3E2", "#F9D5A7"),
        ("Divergencias", "Sem Vínculo RH",             "#7D3C98", "#F5EEF8", "#D7BDE2"),
        ("Divergencias", "Total Divergências",         "#1E8449", "#EAFAF1", "#A9DFBF"),
    ]
    cy = _CONTENT_Y + 10
    for entity, msr, fc, bg, border in cards_cfg:
        v.append(shape_rect(6, cy, 360, _SIDEBAR_W - 12, 72, bg, border, 1))
        # Left colored accent bar on card
        v.append(shape_rect(6, cy, 365, 4, 72, fc))
        v.append(card(10, cy, 370, _SIDEBAR_W - 16, 72, entity, msr, fc, reject_highlight=True))
        cy += 80

    # Mini bar chart (Por Departamento) — fills remaining sidebar space
    chart_y = cy + 6
    chart_h = page_h - chart_y - 10
    if chart_h > 60:
        v.append(shape_rect(6, chart_y, 360, _SIDEBAR_W - 12, chart_h,
                            "#FFFFFF", "#E0E0E0", 1))
        v.append(bar_chart_depto(6, chart_y, 370, _SIDEBAR_W - 12, chart_h))

    # ── MAIN PANEL ───────────────────────────────────────────────────────────
    main_top    = _CONTENT_Y
    detail_h    = 160
    detail_gap  = 8
    matrix_h    = avail_h - detail_h - detail_gap - 10
    detail_y    = main_top + matrix_h + detail_gap
    main_w      = 1440 - _MAIN_X - 6

    # White background main panel
    v.append(shape_rect(_MAIN_X - 2, main_top, 350, main_w + 4, avail_h - 4,
                        "#FFFFFF", "#E0E0E0", 1))

    # Main pivot table (expandable matrix)
    v.append(pivot_table(_MAIN_X, main_top + 4, 400, main_w, matrix_h))

    # Detail table (cross-filter)
    v.append(shape_rect(_MAIN_X - 2, detail_y, 350, main_w + 4, detail_h,
                        "#FFFFFF", "#E0E0E0", 1))
    v.append(table_detalhe(_MAIN_X, detail_y + 4, 410, main_w, detail_h - 4))

    return "ReportSection_ListaDiv", "Lista de Divergências", v


# ── Page: Visão Geral ─────────────────────────────────────────────────────────

def page_visao_geral():
    v = build_header("ReportSection_VisaoGeral")
    v += build_nav("ReportSection_VisaoGeral")
    v += build_filter()

    avail_h = 900 - _CONTENT_Y  # 746

    # 5 KPI cards row
    cards_cfg = [
        ("RH_Ativos",    "Total Funcionários Ativos", "#2980B9", "#EBF5FB", "#D5E8F5"),
        ("SYSTUR",       "Total Usuários SYSTUR",     "#2471A3", "#EBF5FB", "#D5E8F5"),
        ("Divergencias", "Perfis Inválidos",           "#E67E22", "#FEF3E2", "#F9D5A7"),
        ("Divergencias", "Sem Vínculo RH",             "#7D3C98", "#F5EEF8", "#D7BDE2"),
        ("Divergencias", "Total Divergências",         "#1E8449", "#EAFAF1", "#A9DFBF"),
    ]
    cw = 270
    cx = 12
    cy = _CONTENT_Y + 6
    for entity, msr, fc, bg, border in cards_cfg:
        v.append(shape_rect(cx, cy, 490, cw, 84, bg, border, 1))
        v.append(shape_rect(cx, cy, 495, 4, 84, fc))
        v.append(card(cx + 4, cy, 500, cw - 4, 84, entity, msr, fc, reject_highlight=True))
        cx += cw + 8

    # 3 charts row
    chart_y = cy + 84 + 10
    chart_h = 205
    v.append(shape_rect(12,  chart_y, 590, 430, chart_h, "#FFFFFF", "#E0E0E0", 1))
    v.append(bar_chart_tipo(  12,  chart_y, 600, 430, chart_h))
    v.append(shape_rect(452, chart_y, 590, 300, chart_h, "#FFFFFF", "#E0E0E0", 1))
    v.append(donut_sistema(   452, chart_y, 600, 300, chart_h))
    v.append(shape_rect(762, chart_y, 590, 658, chart_h, "#FFFFFF", "#E0E0E0", 1))
    v.append(line_chart_evolucao(762, chart_y, 600, 658, chart_h))

    # Matrix fills remaining space
    matrix_y = chart_y + chart_h + 10
    matrix_h = 900 - matrix_y - 8
    if matrix_h > 100:
        v.append(pivot_table(12, matrix_y, 700, 1416, matrix_h))

    return "ReportSection_VisaoGeral", "Visão Geral", v


# ── Page: Skeleton (pre-filtered) ────────────────────────────────────────────

def page_skeleton(section_name, display_name, filter_type):
    v = build_header(section_name)
    v += build_nav(section_name)
    v += build_filter()

    avail_h = 900 - _CONTENT_Y - 8
    v.append(pivot_table(8, _CONTENT_Y + 4, 400, 1424, avail_h, filter_type))

    return section_name, display_name, v


# ── Writer ────────────────────────────────────────────────────────────────────

def write_report(report_dir: Path):
    pages_dir = report_dir / "definition" / "pages"

    legacy = report_dir / "report.json"
    if legacy.exists():
        legacy.unlink()
        print("  removido: report.json (PBIR-Legacy)")

    if pages_dir.exists():
        shutil.rmtree(pages_dir)

    write_json(report_dir / "definition" / "report.json", {
        "$schema": SCHEMA_REPORT,
        "themeCollection": {},
    })
    write_json(report_dir / "definition" / "version.json", {
        "$schema": SCHEMA_VER,
        "version": "2.0.0",
    })

    pages_data = [
        page_lista_divergencias(),   # active page first — matches mockup
        page_visao_geral(),
        page_skeleton("ReportSection_PerfisInv",  "Perfis Inválidos", "PERFIL_INVALIDO"),
        page_skeleton("ReportSection_SemVinculo", "Sem Vínculo RH",   "ACESSO_SEM_VINCULO_RH"),
    ]

    page_order = []
    total_v = 0
    for section_name, display_name, visuals in pages_data:
        page_dir = pages_dir / section_name
        write_json(page_dir / "page.json", make_page_json(section_name, display_name))
        for vis in visuals:
            write_json(page_dir / "visuals" / vis["name"] / "visual.json", vis)
        page_order.append(section_name)
        total_v += len(visuals)
        print(f"    [{display_name}]  {len(visuals)} visuais")

    write_json(pages_dir / "pages.json", {
        "$schema": SCHEMA_PAGES,
        "pageOrder": page_order,
        "activePageName": page_order[0],
    })

    print(f"\nPBIR gerado -> {report_dir / 'definition'}")
    print(f"  {len(pages_data)} paginas  |  {total_v} visuais no total")


def main():
    report_dir = (Path(__file__).parent.parent /
                  "CVC_IAM_ANALYTICS/POWER_BI/CVC_IAM_Analytics.Report")
    write_report(report_dir)


if __name__ == "__main__":
    main()
