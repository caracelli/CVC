#!/usr/bin/env python3
"""
Gera o report.json para CVC IAM Analytics — Fase 1.
Executar: python scripts/gerar_report_json.py
Saída:    CVC_IAM_ANALYTICS/POWER_BI/CVC_IAM_Analytics.Report/report.json
"""

import json
import random
import string
from pathlib import Path

# ── Helpers ────────────────────────────────────────────────────────────────

def uid():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=20))


def vc(x, y, z, w, h, cfg):
    """Cria um visual container (wrapper obrigatório do PBIP)."""
    return {
        "x": x, "y": y, "z": z,
        "width": w, "height": h,
        "config": json.dumps(cfg, ensure_ascii=False),
        "filters": "[]"
    }


def pos(x, y, z, w, h):
    return [{"id": 0, "position": {
        "x": x, "y": y, "z": z,
        "width": w, "height": h,
        "tabOrder": z
    }}]


# ── Primitivas visuais ─────────────────────────────────────────────────────

def shape(x, y, z, w, h, fill, border_show=False, border_color="#E0E0E0", border_w=1):
    return vc(x, y, z, w, h, {
        "name": uid(),
        "layouts": pos(x, y, z, w, h),
        "singleVisual": {
            "visualType": "shape",
            "objects": {
                "fill": [{"properties": {
                    "fillColor": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{fill}'"}}}}}
                }}],
                "line": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true" if border_show else "false"}}},
                    "lineColor": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{border_color}'"}}}}},
                    "weight": {"expr": {"Literal": {"Value": f"{border_w}D"}}}
                }}]
            }
        }
    })


def textbox(x, y, z, w, h, runs):
    """
    runs: lista de dicts — text, size, bold, color, italic, align
    Cada dict vira um parágrafo independente.
    """
    paras = []
    for r in runs:
        paras.append({
            "textRuns": [{
                "value": r["text"],
                "textStyle": {
                    "fontFamily": "Segoe UI",
                    "fontSize": str(r.get("size", 11)),
                    "bold": r.get("bold", False),
                    "italic": r.get("italic", False),
                    "color": r.get("color", "#333333")
                }
            }],
            "horizontalTextAlignment": r.get("align", "left")
        })
    return vc(x, y, z, w, h, {
        "name": uid(),
        "layouts": pos(x, y, z, w, h),
        "singleVisual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {
                "paragraphs": json.dumps(paras, ensure_ascii=False)
            }}]}
        }
    })


def card(x, y, z, w, h, table, measure, num_color, bg_color, label):
    src = table[0].lower()
    return vc(x, y, z, w, h, {
        "name": uid(),
        "layouts": pos(x, y, z, w, h),
        "singleVisual": {
            "visualType": "card",
            "projections": {
                "Values": [{"queryRef": f"{table}.{measure}", "active": True}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": src, "Entity": table, "Type": 0}],
                "Select": [{"Measure": {
                    "Expression": {"SourceRef": {"Source": src}},
                    "Property": measure
                }, "Name": f"{table}.{measure}"}]
            },
            "objects": {
                "labels": [{"properties": {
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{num_color}'"}}}}},
                    "fontSize": {"expr": {"Literal": {"Value": "28D"}}},
                    "fontFamily": {"expr": {"Literal": {"Value": "'Segoe UI'"}}}
                }}],
                "categoryLabels": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#555555'"}}}}},
                    "fontSize": {"expr": {"Literal": {"Value": "10D"}}}
                }}],
                "background": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{bg_color}'"}}}}}
                }}],
                "border": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "title": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "false"}}}
                }}]
            }
        }
    })


def slicer_tile(x, y, z, w, h, table, column):
    src = table[0].lower()
    return vc(x, y, z, w, h, {
        "name": uid(),
        "layouts": pos(x, y, z, w, h),
        "singleVisual": {
            "visualType": "slicer",
            "projections": {
                "Values": [{"queryRef": f"{table}.{column}", "active": True}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": src, "Entity": table, "Type": 0}],
                "Select": [{"Column": {
                    "Expression": {"SourceRef": {"Source": src}},
                    "Property": column
                }, "Name": f"{table}.{column}"}]
            },
            "objects": {
                "general": [{"properties": {
                    "orientation": {"expr": {"Literal": {"Value": "'Horizontal'"}}}
                }}],
                "selection": [{"properties": {
                    "selectAllCheckboxEnabled": {"expr": {"Literal": {"Value": "true"}}},
                    "singleSelect": {"expr": {"Literal": {"Value": "false"}}}
                }}],
                "items": [{"properties": {
                    "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#555555'"}}}}},
                    "background": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}},
                    "selectedColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#F5B800'"}}}}},
                    "selectedFontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#1F2D5C'"}}}}}
                }}],
                "background": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "false"}}}
                }}],
                "border": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
            }
        }
    })


def matrix_visual(x, y, z, w, h):
    """Matrix com hierarquia usuario→id nas linhas e todos os campos nos valores."""
    return vc(x, y, z, w, h, {
        "name": uid(),
        "layouts": pos(x, y, z, w, h),
        "singleVisual": {
            "visualType": "matrix",
            "projections": {
                "Rows": [
                    {"queryRef": "Divergencias.usuario", "active": True},
                    {"queryRef": "Divergencias.id",      "active": True}
                ],
                "Values": [
                    {"queryRef": "RH_Ativos.nome",                   "active": True},
                    {"queryRef": "Divergencias.matricula",           "active": True},
                    {"queryRef": "RH_Ativos.departamento",           "active": True},
                    {"queryRef": "RH_Ativos.cargo_descricao",        "active": True},
                    {"queryRef": "Divergencias.tipo",                "active": True},
                    {"queryRef": "Divergencias.perfil_encontrado",   "active": True},
                    {"queryRef": "Divergencias.perfil_esperado",     "active": True},
                    {"queryRef": "Divergencias.data_identificacao",  "active": True},
                    {"queryRef": "Divergencias.resolvida",           "active": True}
                ]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [
                    {"Name": "d", "Entity": "Divergencias", "Type": 0},
                    {"Name": "r", "Entity": "RH_Ativos",    "Type": 0}
                ],
                "Select": [
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "usuario"},           "Name": "Divergencias.usuario"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "id"},                "Name": "Divergencias.id"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "r"}}, "Property": "nome"},              "Name": "RH_Ativos.nome"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "matricula"},         "Name": "Divergencias.matricula"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "r"}}, "Property": "departamento"},      "Name": "RH_Ativos.departamento"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "r"}}, "Property": "cargo_descricao"},   "Name": "RH_Ativos.cargo_descricao"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "tipo"},              "Name": "Divergencias.tipo"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "perfil_encontrado"}, "Name": "Divergencias.perfil_encontrado"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "perfil_esperado"},   "Name": "Divergencias.perfil_esperado"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "data_identificacao"},"Name": "Divergencias.data_identificacao"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "resolvida"},         "Name": "Divergencias.resolvida"}
                ]
            },
            "objects": {
                "grid": [{"properties": {
                    "gridVertical":          {"expr": {"Literal": {"Value": "false"}}},
                    "gridHorizontalWeight":  {"expr": {"Literal": {"Value": "1D"}}},
                    "outlineColor":          {"solid": {"color": {"expr": {"Literal": {"Value": "'#E0E0E0'"}}}}},
                    "outlineWeight":         {"expr": {"Literal": {"Value": "1D"}}},
                    "rowPadding":            {"expr": {"Literal": {"Value": "3D"}}}
                }}],
                "columnHeaders": [{"properties": {
                    "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}},
                    "backColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#1F2D5C'"}}}}},
                    "fontSize":  {"expr": {"Literal": {"Value": "10D"}}},
                    "fontFamily":{"expr": {"Literal": {"Value": "'Segoe UI'"}}}
                }}],
                "rowHeaders": [{"properties": {
                    "fontColor":               {"solid": {"color": {"expr": {"Literal": {"Value": "'#333333'"}}}}},
                    "fontSize":                {"expr": {"Literal": {"Value": "11D"}}},
                    "fontFamily":              {"expr": {"Literal": {"Value": "'Segoe UI'"}}},
                    "stepped":                 {"expr": {"Literal": {"Value": "true"}}},
                    "steppedLayoutIndentation":{"expr": {"Literal": {"Value": "20D"}}}
                }}],
                "values": [{"properties": {
                    "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#333333'"}}}}},
                    "fontSize":  {"expr": {"Literal": {"Value": "11D"}}},
                    "fontFamily":{"expr": {"Literal": {"Value": "'Segoe UI'"}}}
                }}],
                "subTotals": [{"properties": {
                    "rowSubtotals":    {"expr": {"Literal": {"Value": "false"}}},
                    "columnSubtotals": {"expr": {"Literal": {"Value": "false"}}}
                }}],
                "background": [{"properties": {
                    "show":  {"expr": {"Literal": {"Value": "true"}}},
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}}
                }}],
                "border": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "title": [{"properties": {
                    "show":       {"expr": {"Literal": {"Value": "true"}}},
                    "titleText":  {"expr": {"Literal": {"Value": "'Divergências — Detalhamento'"}}},
                    "fontColor":  {"solid": {"color": {"expr": {"Literal": {"Value": "'#1F2D5C'"}}}}},
                    "fontSize":   {"expr": {"Literal": {"Value": "12D"}}},
                    "fontFamily": {"expr": {"Literal": {"Value": "'Segoe UI'"}}}
                }}]
            }
        }
    })


def table_detalhe(x, y, z, w, h):
    """Tabela de detalhe — recebe cross-filter da Matrix."""
    return vc(x, y, z, w, h, {
        "name": uid(),
        "layouts": pos(x, y, z, w, h),
        "singleVisual": {
            "visualType": "tableEx",
            "projections": {
                "Values": [
                    {"queryRef": "Divergencias.tipo",               "active": True},
                    {"queryRef": "Divergencias.perfil_encontrado",  "active": True},
                    {"queryRef": "Divergencias.perfil_esperado",    "active": True},
                    {"queryRef": "Divergencias.descricao",          "active": True},
                    {"queryRef": "Divergencias.data_identificacao", "active": True},
                    {"queryRef": "Divergencias.resolvida",          "active": True}
                ]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "d", "Entity": "Divergencias", "Type": 0}],
                "Select": [
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "tipo"},               "Name": "Divergencias.tipo"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "perfil_encontrado"},  "Name": "Divergencias.perfil_encontrado"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "perfil_esperado"},    "Name": "Divergencias.perfil_esperado"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "descricao"},          "Name": "Divergencias.descricao"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "data_identificacao"}, "Name": "Divergencias.data_identificacao"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "resolvida"},          "Name": "Divergencias.resolvida"}
                ]
            },
            "objects": {
                "grid": [{"properties": {
                    "gridVertical":  {"expr": {"Literal": {"Value": "false"}}},
                    "outlineColor":  {"solid": {"color": {"expr": {"Literal": {"Value": "'#E0E0E0'"}}}}}
                }}],
                "columnHeaders": [{"properties": {
                    "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}},
                    "backColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#2C3E6B'"}}}}},
                    "fontSize":  {"expr": {"Literal": {"Value": "9D"}}}
                }}],
                "values": [{"properties": {
                    "fontSize":  {"expr": {"Literal": {"Value": "10D"}}},
                    "backColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#F8FBFF'"}}}}}
                }}],
                "background": [{"properties": {
                    "show":  {"expr": {"Literal": {"Value": "true"}}},
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#F8FBFF'"}}}}}
                }}],
                "border": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "title": [{"properties": {
                    "show":       {"expr": {"Literal": {"Value": "true"}}},
                    "titleText":  {"expr": {"Literal": {"Value": "'Detalhe do Usuário Selecionado'"}}},
                    "fontColor":  {"solid": {"color": {"expr": {"Literal": {"Value": "'#1F2D5C'"}}}}},
                    "fontSize":   {"expr": {"Literal": {"Value": "11D"}}}
                }}]
            }
        }
    })


def bar_chart_depto(x, y, z, w, h):
    """Barras horizontais — divergências por departamento."""
    return vc(x, y, z, w, h, {
        "name": uid(),
        "layouts": pos(x, y, z, w, h),
        "singleVisual": {
            "visualType": "clusteredBarChart",
            "projections": {
                "Category": [{"queryRef": "RH_Ativos.departamento",         "active": True}],
                "Y":        [{"queryRef": "Divergencias.Total Divergências", "active": True}]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [
                    {"Name": "r", "Entity": "RH_Ativos",    "Type": 0},
                    {"Name": "d", "Entity": "Divergencias", "Type": 0}
                ],
                "Select": [
                    {"Column":  {"Expression": {"SourceRef": {"Source": "r"}}, "Property": "departamento"},  "Name": "RH_Ativos.departamento"},
                    {"Measure": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Total Divergências"}, "Name": "Divergencias.Total Divergências"}
                ],
                "OrderBy": [{"Direction": 2, "Expression": {
                    "Measure": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Total Divergências"}
                }}]
            },
            "objects": {
                "dataPoint": [{"properties": {
                    "defaultColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#2980B9'"}}}}}
                }}],
                "categoryAxis": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "fontSize": {"expr": {"Literal": {"Value": "9D"}}}
                }}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "labels": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "fontSize": {"expr": {"Literal": {"Value": "9D"}}},
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#333333'"}}}}}
                }}],
                "background": [{"properties": {
                    "show":  {"expr": {"Literal": {"Value": "true"}}},
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}}
                }}],
                "border": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "title": [{"properties": {
                    "show":       {"expr": {"Literal": {"Value": "true"}}},
                    "titleText":  {"expr": {"Literal": {"Value": "'Por Departamento'"}}},
                    "fontColor":  {"solid": {"color": {"expr": {"Literal": {"Value": "'#1F2D5C'"}}}}},
                    "fontSize":   {"expr": {"Literal": {"Value": "10D"}}}
                }}]
            }
        }
    })


def nav_button(x, y, z, w, h, label, target_page, active=False):
    bg = '#F5B800' if active else '#EAECF0'
    fc = '#1F2D5C' if active else '#555555'
    return vc(x, y, z, w, h, {
        "name": uid(),
        "layouts": pos(x, y, z, w, h),
        "singleVisual": {
            "visualType": "actionButton",
            "objects": {
                "general": [{"properties": {
                    "text": {"expr": {"Literal": {"Value": f"'{label}'"}}}
                }}],
                "background": [{"properties": {
                    "show":  {"expr": {"Literal": {"Value": "true"}}},
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{bg}'"}}}}}
                }}],
                "fontSettings": [{"properties": {
                    "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": f"'{fc}'"}}}}},
                    "fontSize":  {"expr": {"Literal": {"Value": "11D"}}},
                    "fontFamily":{"expr": {"Literal": {"Value": "'Segoe UI'"}}},
                    "bold": {"expr": {"Literal": {"Value": "true" if active else "false"}}}
                }}],
                "action": [{"properties": {
                    "enable": {"expr": {"Literal": {"Value": "true"}}},
                    "type":   {"expr": {"Literal": {"Value": "'PageNavigation'"}}},
                    "navigationPage": {"expr": {"Literal": {"Value": f"'{target_page}'"}}}
                }}]
            }
        }
    })


# ── Header + abas comuns ───────────────────────────────────────────────────

PAGES = [
    ("ReportSection_VisaoGeral",    "Visão Geral"),
    ("ReportSection_ListaDiv",      "Lista de Divergências"),
    ("ReportSection_PerfisInv",     "Perfis Inválidos"),
    ("ReportSection_SemVinculo",    "Sem Vínculo RH"),
]


def header_visuals(active_label):
    v = []
    # Fundo da página
    v.append(shape(0, 0, 100, 1440, 900, '#F2F4F7'))
    # Header
    v.append(shape(0, 0, 200, 1440, 70, '#1F2D5C'))
    # Acento amarelo
    v.append(shape(0, 0, 300, 6, 70, '#F5B800'))
    # Título
    v.append(textbox(26, 8, 400, 340, 30, [
        {"text": "IAM Analytics", "size": 22, "bold": True, "color": "#FFFFFF"}
    ]))
    # Subtítulo
    v.append(textbox(26, 38, 410, 500, 22, [
        {"text": "Governança de Acessos — CVC Corp", "size": 11, "color": "#B0BEC5"}
    ]))
    # Referência
    v.append(textbox(1080, 8, 420, 350, 22, [
        {"text": "Referência: Maio / 2026", "size": 12, "bold": True, "color": "#F5B800", "align": "right"}
    ]))
    # Última atualização
    v.append(textbox(1080, 34, 421, 350, 18, [
        {"text": "Última atualização: 13/05/2026", "size": 9, "color": "#B0BEC5", "align": "right"}
    ]))
    # Abas de navegação
    tab_x = 20
    for page_name, label in PAGES:
        v.append(nav_button(tab_x, 75, 500, 158, 36, label, page_name, label == active_label))
        tab_x += 162
    # Barra de filtro — fundo
    v.append(shape(0, 111, 590, 1440, 42, '#EBEBEB'))
    # Label filtro
    v.append(textbox(20, 118, 700, 130, 28, [
        {"text": "Filtrar por Sistema:", "size": 10, "bold": True, "color": "#333333"}
    ]))
    # Slicer de sistema
    v.append(slicer_tile(152, 115, 800, 560, 36, 'SYSTUR', 'sistema'))
    return v


# ── Páginas ────────────────────────────────────────────────────────────────

def page_lista_divergencias():
    v = header_visuals("Lista de Divergências")

    # ── Sidebar ──
    sidebar_cards = [
        ('RH_Ativos',    'Total Funcionários Ativos', '#2980B9', '#EBF5FB', 'Funcionários Ativos'),
        ('SYSTUR',       'Total Usuários SYSTUR',     '#2471A3', '#EBF5FB', 'Usuários SYSTUR'),
        ('Divergencias', 'Perfis Inválidos',           '#E67E22', '#FEF3E2', 'Perfis Inválidos'),
        ('Divergencias', 'Sem Vínculo RH',             '#7D3C98', '#F5EEF8', 'Sem Vínculo RH'),
        ('Divergencias', '% Resolvidas',               '#1E8449', '#EAFAF1', '% Resolvidas'),
    ]
    card_y = 160
    for tbl, msr, nc, bg, lbl in sidebar_cards:
        v.append(card(20, card_y, 900, 196, 76, tbl, msr, nc, bg, lbl))
        card_y += 84

    # Barra de acento esquerda dos cards (4px amarelo)
    for i in range(len(sidebar_cards)):
        v.append(shape(20, 160 + i * 84, 901, 4, 76, '#F5B800'))

    # Gráfico de barras por departamento
    v.append(bar_chart_depto(20, card_y + 4, 910, 196, 900 - card_y - 4 - 16))

    # ── Main panel ──
    main_x, main_w = 228, 1192

    # Título da seção (caixa de texto acima da matrix)
    v.append(textbox(main_x, 156, 950, 400, 20, [
        {"text": "Divergências — Detalhamento", "size": 13, "bold": True, "color": "#1F2D5C"}
    ]))

    # Matrix principal (usuario → id)
    v.append(matrix_visual(main_x, 178, 1000, main_w, 530))

    # Acento amarelo — separador do painel de detalhe
    v.append(shape(main_x, 714, 1090, main_w, 3, '#F5B800'))

    # Tabela de detalhe
    v.append(table_detalhe(main_x, 718, 1100, main_w, 164))

    return {
        "name":          "ReportSection_ListaDiv",
        "displayName":   "Lista de Divergências",
        "config":        json.dumps({"defaultDrillFilterOtherVisuals": True}, ensure_ascii=False),
        "displayOption": 0,
        "width":  1440,
        "height":  900,
        "visualContainers": v
    }


def page_visao_geral():
    v = header_visuals("Visão Geral")

    # KPI cards em linha (5 cards)
    cards_cfg = [
        ('RH_Ativos',    'Total Funcionários Ativos', '#2980B9', '#EBF5FB', 'Funcionários Ativos'),
        ('SYSTUR',       'Total Usuários SYSTUR',     '#2471A3', '#EBF5FB', 'Usuários SYSTUR'),
        ('Divergencias', 'Perfis Inválidos',           '#E67E22', '#FEF3E2', 'Perfis Inválidos'),
        ('Divergencias', 'Sem Vínculo RH',             '#7D3C98', '#F5EEF8', 'Sem Vínculo RH'),
        ('Divergencias', '% Resolvidas',               '#1E8449', '#EAFAF1', '% Resolvidas'),
    ]
    cx = 20
    for tbl, msr, nc, bg, lbl in cards_cfg:
        v.append(card(cx, 162, 900, 270, 90, tbl, msr, nc, bg, lbl))
        v.append(shape(cx, 162, 901, 4, 90, {
            '#2980B9': '#2980B9', '#2471A3': '#2471A3',
            '#E67E22': '#E67E22', '#7D3C98': '#7D3C98', '#1E8449': '#1E8449'
        }[nc]))
        cx += 280

    # Gráfico de barras por departamento
    v.append(bar_chart_depto(20, 270, 950, 430, 300))

    return {
        "name":          "ReportSection_VisaoGeral",
        "displayName":   "Visão Geral",
        "config":        json.dumps({"defaultDrillFilterOtherVisuals": True}, ensure_ascii=False),
        "displayOption": 0,
        "width":  1440,
        "height":  900,
        "visualContainers": v
    }


def page_skeleton(section_name, display_name, filter_type=None):
    """Páginas de detalhe por tipo — header + slicer + matrix filtrada."""
    v = header_visuals(display_name)

    # Matrix filtrada (o filtro de tipo é aplicado no campo filters do container)
    filters = "[]"
    if filter_type:
        f = [{
            "name": uid(),
            "type": "Categorical",
            "expression": {
                "Column": {
                    "Expression": {"SourceRef": {"Table": "Divergencias"}},
                    "Property": "tipo"
                }
            },
            "filter": {
                "Version": 2,
                "From": [{"Name": "d", "Entity": "Divergencias", "Type": 0}],
                "Where": [{"Condition": {"In": {
                    "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "tipo"}}],
                    "Values": [[{"Literal": {"Value": f"'{filter_type}'"}}]]
                }}}]
            }
        }]
        filters = json.dumps(f, ensure_ascii=False)

    mx = vc(228, 162, 1000, 1192, 560, {
        "name": uid(),
        "layouts": pos(228, 162, 1000, 1192, 560),
        "singleVisual": {
            "visualType": "matrix",
            "projections": {
                "Rows": [
                    {"queryRef": "Divergencias.usuario", "active": True},
                    {"queryRef": "Divergencias.id",      "active": True}
                ],
                "Values": [
                    {"queryRef": "RH_Ativos.nome",                  "active": True},
                    {"queryRef": "Divergencias.matricula",          "active": True},
                    {"queryRef": "RH_Ativos.departamento",          "active": True},
                    {"queryRef": "Divergencias.tipo",               "active": True},
                    {"queryRef": "Divergencias.perfil_encontrado",  "active": True},
                    {"queryRef": "Divergencias.perfil_esperado",    "active": True},
                    {"queryRef": "Divergencias.data_identificacao", "active": True},
                    {"queryRef": "Divergencias.resolvida",          "active": True}
                ]
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [
                    {"Name": "d", "Entity": "Divergencias", "Type": 0},
                    {"Name": "r", "Entity": "RH_Ativos",    "Type": 0}
                ],
                "Select": [
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "usuario"},           "Name": "Divergencias.usuario"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "id"},                "Name": "Divergencias.id"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "r"}}, "Property": "nome"},              "Name": "RH_Ativos.nome"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "matricula"},         "Name": "Divergencias.matricula"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "r"}}, "Property": "departamento"},      "Name": "RH_Ativos.departamento"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "tipo"},              "Name": "Divergencias.tipo"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "perfil_encontrado"}, "Name": "Divergencias.perfil_encontrado"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "perfil_esperado"},   "Name": "Divergencias.perfil_esperado"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "data_identificacao"},"Name": "Divergencias.data_identificacao"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "resolvida"},         "Name": "Divergencias.resolvida"}
                ]
            },
            "objects": {
                "columnHeaders": [{"properties": {
                    "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}},
                    "backColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#1F2D5C'"}}}}},
                    "fontSize":  {"expr": {"Literal": {"Value": "10D"}}}
                }}],
                "rowHeaders": [{"properties": {
                    "stepped": {"expr": {"Literal": {"Value": "true"}}},
                    "steppedLayoutIndentation": {"expr": {"Literal": {"Value": "20D"}}}
                }}],
                "subTotals": [{"properties": {
                    "rowSubtotals":    {"expr": {"Literal": {"Value": "false"}}},
                    "columnSubtotals": {"expr": {"Literal": {"Value": "false"}}}
                }}],
                "background": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}}
                }}]
            }
        }
    })
    mx["filters"] = filters
    v.append(mx)

    return {
        "name":          section_name,
        "displayName":   display_name,
        "config":        json.dumps({"defaultDrillFilterOtherVisuals": True}, ensure_ascii=False),
        "displayOption": 0,
        "width":  1440,
        "height":  900,
        "visualContainers": v
    }


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    report = {
        "config": json.dumps({
            "version": "5.37",
            "themeCollection": {},
            "activeSectionIndex": 1,
            "linguisticSchemaSyncVersion": 2
        }, ensure_ascii=False),
        "layoutOptimization": 0,
        "report": {},
        "sections": [
            page_visao_geral(),
            page_lista_divergencias(),
            page_skeleton("ReportSection_PerfisInv",  "Perfis Inválidos",  "PERFIL_INVALIDO"),
            page_skeleton("ReportSection_SemVinculo", "Sem Vínculo RH",    "ACESSO_SEM_VINCULO_RH"),
        ]
    }

    out = Path(__file__).parent.parent / \
          "CVC_IAM_ANALYTICS/POWER_BI/CVC_IAM_Analytics.Report/report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    total_v = sum(len(s["visualContainers"]) for s in report["sections"])
    print(f"report.json gerado -> {out}")
    print(f"  {len(report['sections'])} páginas  |  {total_v} visuais no total")
    for s in report["sections"]:
        print(f"    [{s['displayName']}]  {len(s['visualContainers'])} visuais")


if __name__ == "__main__":
    main()
