"""
Mockup v2 — CVC IAM Analytics (cenário atual)
Gera dois PNGs:
  mockup_v2_visao_geral.png
  mockup_v2_acoes_pendentes.png
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

# ── Paleta ──────────────────────────────────────────────────────────
CVC_BLUE   = '#3757A2'
CVC_YELLOW = '#FEC805'
CVC_DARK   = '#1E3472'
CVC_LIGHT  = '#EEF2FF'
BG         = '#F4F6FB'
WHITE      = '#FFFFFF'
GRAY_LINE  = '#DADADA'
GRAY_TEXT  = '#777777'

RED_BG  = '#FDECEC'; RED_FG  = '#C0392B'
YLW_BG  = '#FFFBE6'; YLW_FG  = '#B7770D'
PUR_BG  = '#F5EEF8'; PUR_FG  = '#6C3483'
GRN_BG  = '#EAFAF1'; GRN_FG  = '#1E8449'
BLU_BG  = '#EEF2FF'; BLU_FG  = CVC_BLUE
ORG_BG  = '#FFF3E0'; ORG_FG  = '#E65100'


# ════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════
def add_header(fig, ref='Maio / 2026', updated='14/05/2026  10:48'):
    ax = fig.add_axes([0, 0.935, 1, 0.065])
    ax.set_facecolor(CVC_BLUE)
    ax.add_patch(FancyBboxPatch((0, 0), 0.005, 1, boxstyle='square,pad=0',
                 facecolor=CVC_YELLOW, edgecolor='none', transform=ax.transAxes))
    ax.text(0.016, 0.58, 'IAM Analytics', color=WHITE, fontsize=18,
            fontweight='bold', va='center', transform=ax.transAxes)
    ax.text(0.016, 0.22, 'Governança de Acessos — CVC Corp', color='#AAC0E8',
            fontsize=9, va='center', transform=ax.transAxes)
    ax.text(0.99, 0.58, f'Referência: {ref}', color=CVC_YELLOW,
            fontsize=9.5, fontweight='bold', va='center', ha='right', transform=ax.transAxes)
    ax.text(0.99, 0.22, f'Última atualização: {updated}', color='#AAC0E8',
            fontsize=8.5, va='center', ha='right', transform=ax.transAxes)
    ax.axis('off')


def add_tabs(fig, active_idx=0):
    labels = ['Visão Geral', 'Ações Pendentes', 'Lista de Divergências',
              'Desligados c/ Acesso', 'Sem Vínculo RH']
    ax = fig.add_axes([0, 0.9, 1, 0.037])
    ax.set_facecolor('#E2E8F4')
    tab_w = 0.175
    gap   = 0.01
    start = 0.01
    for i, label in enumerate(labels):
        x      = start + i * (tab_w + gap)
        active = (i == active_idx)
        bg  = WHITE      if active else '#E2E8F4'
        ec  = CVC_YELLOW if active else GRAY_LINE
        lw  = 2.5        if active else 0.5
        ax.add_patch(FancyBboxPatch((x, 0.06), tab_w, 0.88,
            boxstyle='round,pad=0.01', linewidth=lw,
            edgecolor=ec, facecolor=bg, transform=ax.transAxes))
        if active:
            ax.add_patch(FancyBboxPatch((x, 0.06), tab_w, 0.14,
                boxstyle='square,pad=0', facecolor=CVC_YELLOW,
                edgecolor='none', transform=ax.transAxes))
        col = CVC_DARK if active else GRAY_TEXT
        ax.text(x + tab_w / 2, 0.55, label, color=col, fontsize=8.5,
                fontweight='bold' if active else 'normal',
                va='center', ha='center', transform=ax.transAxes)
    ax.axis('off')


def add_slicer_row(fig, top, label, items, selected_idx=0):
    """Faixa de slicer (botões pill)."""
    ax = fig.add_axes([0.01, top, 0.98, 0.048])
    ax.set_facecolor(WHITE)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.7)
    ax.text(0.005, 0.55, label, color=CVC_DARK, fontsize=8.5,
            fontweight='bold', va='center', transform=ax.transAxes)
    sx = 0.14
    pill_w = 0.09
    for j, nome in enumerate(items):
        sel = (j == selected_idx)
        ax.add_patch(FancyBboxPatch((sx, 0.12), pill_w, 0.75,
            boxstyle='round,pad=0.02',
            facecolor=CVC_YELLOW if sel else '#F0F4FF',
            edgecolor=CVC_BLUE   if sel else GRAY_LINE,
            linewidth=1.2, transform=ax.transAxes))
        ax.text(sx + pill_w / 2, 0.55, nome,
                color=CVC_DARK if sel else '#555555',
                fontsize=8, fontweight='bold' if sel else 'normal',
                va='center', ha='center', transform=ax.transAxes)
        sx += pill_w + 0.012
    ax.axis('off')


def kpi_card(fig, x, y, w, h, title, value, color, bg):
    ax = fig.add_axes([x, y, w, h])
    ax.set_facecolor(bg)
    for sp in ax.spines.values():
        sp.set_edgecolor(color); sp.set_linewidth(2)
    ax.add_patch(FancyBboxPatch((0, 0.86), 1, 0.14,
        boxstyle='square,pad=0', facecolor=color,
        edgecolor='none', transform=ax.transAxes))
    ax.text(0.5, 0.56, value, color=color, fontsize=22,
            fontweight='bold', ha='center', va='center', transform=ax.transAxes)
    ax.text(0.5, 0.22, title, color='#444444', fontsize=8,
            ha='center', va='center', transform=ax.transAxes)
    ax.set_xticks([]); ax.set_yticks([])


def section_title(ax, text, sub=None):
    ax.text(0.008, 0.96, text, color=CVC_DARK, fontsize=10.5,
            fontweight='bold', va='top', transform=ax.transAxes)
    if sub:
        ax.text(0.008, 0.875, sub, color=GRAY_TEXT, fontsize=8,
                va='top', transform=ax.transAxes)


# ════════════════════════════════════════════════════════════════════
# PÁGINA 1 — VISÃO GERAL (redesenhada)
# ════════════════════════════════════════════════════════════════════
fig1 = plt.figure(figsize=(22, 14), facecolor=BG)
add_header(fig1)
add_tabs(fig1, active_idx=0)

# Slicer Sistema
add_slicer_row(fig1, 0.853, 'Filtrar por Sistema:',
               ['Todos', 'SYSTUR', 'SIGOT', 'SICA RA', 'SICA ESFERA', 'IC'],
               selected_idx=0)

# KPI Cards ─────────────────────────────────────────────────────────
kpis = [
    ('Funcionários Ativos',  '2.207',  CVC_BLUE,  BLU_BG),
    ('Ações Pendentes',      '1.041',  ORG_FG,    ORG_BG),
    ('Desligados c/ Acesso', '243',    RED_FG,    RED_BG),
    ('Sem Vínculo RH',       '4.957',  PUR_FG,    PUR_BG),
    ('Total Divergências',   '5.271',  GRN_FG,    GRN_BG),
]
card_w = 0.185; card_h = 0.115; card_y = 0.727
for i, (title, val, color, bg) in enumerate(kpis):
    kpi_card(fig1, 0.01 + i * 0.198, card_y, card_w, card_h, title, val, color, bg)

# ── Gráfico 1: Divergências por Tipo ────────────────────────────────
ax_bar = fig1.add_axes([0.01, 0.415, 0.36, 0.29])
ax_bar.set_facecolor(WHITE)
for sp in ax_bar.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.7)
tipos   = ['Sem Vínculo RH', 'Desligado c/ Acesso', 'Perfil Inválido']
valores = [4957, 243, 71]
cores   = [PUR_FG, RED_FG, YLW_FG]
bars = ax_bar.barh(tipos, valores, color=cores, height=0.45)
for bar, val in zip(bars, valores):
    ax_bar.text(bar.get_width() + 80, bar.get_y() + bar.get_height() / 2,
                f'{val:,}', va='center', fontsize=10, color='#333333', fontweight='bold')
section_title(ax_bar, 'Divergências por Tipo',
              'Distribuição das 5.271 divergências encontradas')
ax_bar.set_xlim(0, 6200)
ax_bar.spines['top'].set_visible(False)
ax_bar.spines['right'].set_visible(False)
ax_bar.tick_params(labelsize=9)
ax_bar.yaxis.set_tick_params(labelsize=9)

# ── Gráfico 2: Ações Pendentes por Status ────────────────────────────
ax_acoes = fig1.add_axes([0.395, 0.415, 0.28, 0.29])
ax_acoes.set_facecolor(WHITE)
for sp in ax_acoes.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.7)
ax_acoes.axis('off')
ax_acoes.set_xlim(0, 1); ax_acoes.set_ylim(0, 1)
section_title(ax_acoes, 'Ações Pendentes por Status',
              'Das 1.041 ações identificadas em Validação')

status_data = [
    ('Incluir Acesso',  '800', 'SEM_ACESSO',  ORG_FG,  ORG_BG),
    ('Alterar Perfil',  '180', 'DIVERGENTE',  YLW_FG,  YLW_BG),
    ('Em Análise',       '61', 'EM_ANALISE',  BLU_FG,  BLU_BG),
]
sy = 0.72
for title, count, tag, fg, bg in status_data:
    # Card horizontal
    ax_acoes.add_patch(FancyBboxPatch((0.04, sy - 0.13), 0.92, 0.16,
        boxstyle='round,pad=0.01', facecolor=bg,
        edgecolor=fg, linewidth=1.5, transform=ax_acoes.transAxes))
    ax_acoes.add_patch(FancyBboxPatch((0.04, sy - 0.13), 0.008, 0.16,
        boxstyle='square,pad=0', facecolor=fg, edgecolor='none',
        transform=ax_acoes.transAxes))
    ax_acoes.text(0.12, sy - 0.04, count, color=fg, fontsize=18,
                  fontweight='bold', va='center', transform=ax_acoes.transAxes)
    ax_acoes.text(0.12, sy - 0.10, title, color='#333333', fontsize=8.5,
                  va='center', transform=ax_acoes.transAxes)
    ax_acoes.text(0.95, sy - 0.05, tag, color=fg, fontsize=7.5,
                  fontweight='bold', va='center', ha='right',
                  style='italic', transform=ax_acoes.transAxes)
    sy -= 0.20

# ── Gráfico 3: Top 5 CCs com mais ações ─────────────────────────────
ax_cc = fig1.add_axes([0.695, 0.415, 0.295, 0.29])
ax_cc.set_facecolor(WHITE)
for sp in ax_cc.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.7)
ccs  = ['AGENCIAS-SP', 'CENTRAL-RJ', 'FRANQUIAS', 'OPERACOES', 'TI-SISTEMAS']
vals = [287, 234, 198, 165, 84]
colors_cc = [ORG_FG if v == max(vals) else '#6aaed6' for v in vals]
bars_cc = ax_cc.barh(ccs, vals, color=colors_cc, height=0.45)
for bar, val in zip(bars_cc, vals):
    ax_cc.text(bar.get_width() + 4, bar.get_y() + bar.get_height() / 2,
               str(val), va='center', fontsize=9, color='#333333', fontweight='bold')
section_title(ax_cc, 'Top 5 Centros de Custo',
              'Ações pendentes por CC (Validação)')
ax_cc.set_xlim(0, 340)
ax_cc.spines['top'].set_visible(False)
ax_cc.spines['right'].set_visible(False)
ax_cc.tick_params(labelsize=8.5)

# ── Tabela: Lista de Divergências ────────────────────────────────────
ax_t = fig1.add_axes([0.01, 0.01, 0.98, 0.385])
ax_t.set_facecolor(WHITE)
for sp in ax_t.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.7)
ax_t.axis('off')
ax_t.set_xlim(0, 1); ax_t.set_ylim(0, 1)

ax_t.text(0.005, 0.965, 'Lista de Divergências', color=CVC_DARK,
          fontsize=10.5, fontweight='bold', va='center')
ax_t.text(0.98, 0.965, 'Exibindo: 5.271 registros', color=GRAY_TEXT,
          fontsize=8, va='center', ha='right')

cols  = ['', 'Usuário', 'Nome Completo', 'Matrícula', 'Departamento', 'N° Div.', 'Tipos Encontrados', 'Sistema']
col_x = [0.002, 0.035, 0.165, 0.335, 0.435, 0.565, 0.625, 0.900]

ax_t.add_patch(FancyBboxPatch((0, 0.875), 1, 0.075,
    boxstyle='square,pad=0', facecolor=CVC_BLUE, edgecolor='none'))
for cx, col in zip(col_x, cols):
    ax_t.text(cx + 0.005, 0.912, col, color=WHITE, fontsize=8.5,
              fontweight='bold', va='center')

rows = [
    (True,  'JOAO.SILVA',    'João da Silva Santos',   '12345', 'Operações SP',  '3', 'DESLIGADO | PERFIL | SEM_VÍNCULO', 'SYSTUR'),
    (False, 'MARIA.SOUZA',   'Maria Aparecida Souza',  '67890', 'Agências RJ',   '2', 'DESLIGADO | PERFIL',               'SYSTUR'),
    (False, 'PEDRO.COSTA',   'Pedro Henrique Costa',   '11111', 'TI Sistemas',   '1', 'PERFIL_INVALIDO',                  'SYSTUR'),
    (False, 'ANA.FERREIRA',  'Ana Paula Ferreira',     '22222', 'Franquias SP',  '1', 'ACESSO_SEM_VINCULO_RH',            'SYSTUR'),
    (False, 'CARLOS.LIMA',   'Carlos Eduardo Lima',    '33333', 'Central RJ',    '1', 'ACESSO_SEM_VINCULO_RH',            'SYSTUR'),
]
children = [
    ('ACESSO_DESLIGADO',     'Funcionário desligado com acesso ativo no sistema',    RED_BG, RED_FG),
    ('PERFIL_INVALIDO',      'Perfil "CONSULTA" não permitido — esperado: OPERADOR', YLW_BG, YLW_FG),
    ('ACESSO_SEM_VINCULO_RH','CPF não localizado na base de RH ativa',              PUR_BG, PUR_FG),
]

y = 0.870; row_h = 0.082; child_h = 0.070
for idx, (expanded, usr, nome, mat, dept, qtd, tipos, sis) in enumerate(rows):
    btn = '▼' if expanded else '+'
    bg  = CVC_LIGHT if idx % 2 == 0 else WHITE
    ax_t.add_patch(FancyBboxPatch((0, y - row_h + 0.004), 1, row_h - 0.004,
        boxstyle='square,pad=0', facecolor=bg, edgecolor=GRAY_LINE, linewidth=0.3))
    if expanded:
        ax_t.add_patch(FancyBboxPatch((0, y - row_h + 0.004), 0.003, row_h - 0.004,
            boxstyle='square,pad=0', facecolor=CVC_YELLOW, edgecolor='none'))

    vals_row = [btn, usr, nome, mat, dept, qtd, tipos, sis]
    clrs_row = [CVC_BLUE, CVC_DARK, '#333333', '#555555', '#555555', CVC_BLUE, '#666666', '#333333']
    fws_row  = ['bold', 'bold', 'normal', 'normal', 'normal', 'bold', 'normal', 'normal']
    for cx, v, c, fw in zip(col_x, vals_row, clrs_row, fws_row):
        ax_t.text(cx + 0.006, y - row_h / 2, v, color=c, fontsize=8.2,
                  fontweight=fw, va='center', clip_on=True)
    y -= row_h

    if expanded:
        for (ctipo, cdesc, cbg, ccolor) in children:
            ax_t.add_patch(FancyBboxPatch((0.028, y - child_h + 0.004), 0.97, child_h - 0.004,
                boxstyle='square,pad=0', facecolor=cbg, edgecolor=GRAY_LINE, linewidth=0.3))
            ax_t.add_patch(FancyBboxPatch((0.028, y - child_h + 0.004), 0.003, child_h - 0.004,
                boxstyle='square,pad=0', facecolor=ccolor, edgecolor='none'))
            ax_t.text(0.042, y - child_h / 2, ctipo, color=ccolor, fontsize=8,
                      fontweight='bold', va='center', style='italic')
            ax_t.text(0.23,  y - child_h / 2, cdesc, color='#444444', fontsize=8,
                      va='center')
            y -= child_h

ax_t.plot([0, 1], [0.025, 0.025], color=GRAY_LINE, linewidth=0.8)
ax_t.text(0.5, 0.012, '← Anterior   1  2  3  ...  41   Próxima →',
          color=GRAY_TEXT, fontsize=8.5, ha='center', va='center')

out1 = r'c:\Users\user\OneDrive\Backup Note\Projetos\Antlia\cvc\CVC\scripts\mockup_v2_visao_geral.png'
plt.savefig(out1, dpi=150, bbox_inches='tight', facecolor=BG)
plt.close(fig1)
print(f'Salvo: {out1}')


# ════════════════════════════════════════════════════════════════════
# PÁGINA 2 — AÇÕES PENDENTES (nova)
# ════════════════════════════════════════════════════════════════════
fig2 = plt.figure(figsize=(22, 14), facecolor=BG)
add_header(fig2)
add_tabs(fig2, active_idx=1)

# Slicers
add_slicer_row(fig2, 0.853, 'Status:',
               ['Todos', 'Sem Acesso', 'Divergente', 'Em Análise'],
               selected_idx=0)
add_slicer_row(fig2, 0.800, 'Filtrar por Sistema:',
               ['Todos', 'SYSTUR', 'SIGOT', 'SICA RA', 'SICA ESFERA', 'IC'],
               selected_idx=0)

# KPI Cards (3 centrais + 1 info)
acao_kpis = [
    ('Incluir Acesso',  '800',  ORG_FG,  ORG_BG),
    ('Alterar Perfil',  '180',  YLW_FG,  YLW_BG),
    ('Em Análise',       '61',  BLU_FG,  BLU_BG),
    ('Acesso Manual',    '23',  GRN_FG,  GRN_BG),
    ('Total c/ Ação', '1.041',  PUR_FG,  PUR_BG),
]
card_w2 = 0.185; card_h2 = 0.115; card_y2 = 0.672
for i, (title, val, color, bg) in enumerate(acao_kpis):
    kpi_card(fig2, 0.01 + i * 0.198, card_y2, card_w2, card_h2, title, val, color, bg)

# Tabela Ações Pendentes ─────────────────────────────────────────────
ax_v = fig2.add_axes([0.01, 0.01, 0.98, 0.638])
ax_v.set_facecolor(WHITE)
for sp in ax_v.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.7)
ax_v.axis('off')
ax_v.set_xlim(0, 1); ax_v.set_ylim(0, 1)

ax_v.text(0.005, 0.975, 'Ações Pendentes — Validação de Acessos', color=CVC_DARK,
          fontsize=11, fontweight='bold', va='center')
ax_v.text(0.98, 0.975, '1.041 registros com ação pendente', color=GRAY_TEXT,
          fontsize=8.5, va='center', ha='right')
ax_v.text(0.005, 0.950, 'Apenas funcionários ativos com status SEM_ACESSO, DIVERGENTE ou EM_ANALISE',
          color=GRAY_TEXT, fontsize=8, va='center')

# Legenda de status
leg_items = [
    ('SEM_ACESSO — Incluir Acesso',  ORG_FG, ORG_BG),
    ('DIVERGENTE — Alterar Perfil',  YLW_FG, YLW_BG),
    ('EM_ANALISE — Revisar c/ Gestor', BLU_FG, BLU_BG),
]
lx = 0.005
for lbl, fg, bg in leg_items:
    ax_v.add_patch(FancyBboxPatch((lx, 0.916), 0.19, 0.022,
        boxstyle='round,pad=0.005', facecolor=bg, edgecolor=fg, linewidth=1.2))
    ax_v.add_patch(FancyBboxPatch((lx, 0.916), 0.004, 0.022,
        boxstyle='square,pad=0', facecolor=fg, edgecolor='none'))
    ax_v.text(lx + 0.01, 0.927, lbl, color=fg, fontsize=7.5,
              fontweight='bold', va='center')
    lx += 0.20

# Cabeçalho da tabela
vcols  = ['Matrícula', 'Nome', 'CPF', 'Centro de Custo', 'Sistema',
          'Perfil Esperado', 'Perfil Atual', 'Status', 'Manual']
vcol_x = [0.005, 0.065, 0.195, 0.295, 0.415, 0.515, 0.655, 0.790, 0.920]

ax_v.add_patch(FancyBboxPatch((0, 0.867), 1, 0.040,
    boxstyle='square,pad=0', facecolor=CVC_BLUE, edgecolor='none'))
for cx, col in zip(vcol_x, vcols):
    ax_v.text(cx + 0.004, 0.887, col, color=WHITE, fontsize=8,
              fontweight='bold', va='center')

# Linhas de dados
vrows = [
    ('12345', 'João da Silva Santos',   '123.456.789-00', 'Operações SP',  'SYSTUR', 'OPERADOR', 'CONSULTA',  'DIVERGENTE', 'Não'),
    ('67890', 'Maria Aparecida Souza',  '234.567.890-11', 'Agências RJ',   'SYSTUR', 'GERENTE',  '—',         'SEM_ACESSO', 'Não'),
    ('11111', 'Pedro Henrique Costa',   '345.678.901-22', 'TI Sistemas',   'SYSTUR', 'ADMIN',    'CONSULTA',  'DIVERGENTE', 'Sim'),
    ('22222', 'Ana Paula Ferreira',     '456.789.012-33', 'Franquias SP',  'SYSTUR', 'CONSULTA', '—',         'SEM_ACESSO', 'Não'),
    ('33333', 'Carlos Eduardo Lima',    '567.890.123-44', 'Central RJ',    'SYSTUR', 'OPERADOR', 'OPERADOR',  'EM_ANALISE', 'Não'),
    ('44444', 'Fernanda Costa Ribeiro', '678.901.234-55', 'Franquias RJ',  'SYSTUR', 'GERENTE',  '—',         'SEM_ACESSO', 'Não'),
    ('55555', 'Lucas Mendes Oliveira',  '789.012.345-66', 'Operações RJ',  'SYSTUR', 'CONSULTA', 'ADMIN',     'DIVERGENTE', 'Não'),
    ('66666', 'Patrícia Alves Sousa',   '890.123.456-77', 'TI Sistemas',   'SYSTUR', 'OPERADOR', '—',         'SEM_ACESSO', 'Sim'),
    ('77777', 'Roberto Teixeira Neto',  '901.234.567-88', 'Agências SP',   'SYSTUR', 'GERENTE',  'CONSULTA',  'DIVERGENTE', 'Não'),
    ('88888', 'Sandra Lima Pereira',    '012.345.678-99', 'Operações SP',  'SYSTUR', 'ADMIN',    'OPERADOR',  'EM_ANALISE', 'Não'),
]

status_colors = {
    'SEM_ACESSO': (ORG_FG, ORG_BG),
    'DIVERGENTE': (YLW_FG, YLW_BG),
    'EM_ANALISE': (BLU_FG, BLU_BG),
}

vy = 0.860; vrow_h = 0.072
for idx, (mat, nome, cpf, cc, sis, pesp, patu, status, manual) in enumerate(vrows):
    sfg, sbg = status_colors.get(status, ('#333333', WHITE))
    base_bg = sbg if idx % 2 == 0 else WHITE
    ax_v.add_patch(FancyBboxPatch((0, vy - vrow_h + 0.004), 1, vrow_h - 0.004,
        boxstyle='square,pad=0', facecolor=base_bg, edgecolor=GRAY_LINE, linewidth=0.3))
    ax_v.add_patch(FancyBboxPatch((0, vy - vrow_h + 0.004), 0.003, vrow_h - 0.004,
        boxstyle='square,pad=0', facecolor=sfg, edgecolor='none'))

    vvals = [mat, nome, cpf, cc, sis, pesp, patu, '', manual]
    vclrs = [CVC_DARK, CVC_DARK, '#555', '#555', '#555', GRN_FG, RED_FG if patu not in ('—','') else '#888', sfg, '#555']
    vfws  = ['bold', 'bold', 'normal', 'normal', 'normal', 'bold', 'bold', 'bold', 'normal']

    for cx, v, c, fw in zip(vcol_x, vvals, vclrs, vfws):
        ax_v.text(cx + 0.005, vy - vrow_h / 2, v, color=c, fontsize=7.8,
                  fontweight=fw, va='center', clip_on=True)

    # Badge de status
    sx_badge = vcol_x[7]
    ax_v.add_patch(FancyBboxPatch((sx_badge, vy - vrow_h * 0.65), 0.115, vrow_h * 0.52,
        boxstyle='round,pad=0.008', facecolor=sbg, edgecolor=sfg, linewidth=1.0))
    ax_v.text(sx_badge + 0.057, vy - vrow_h * 0.38, status,
              color=sfg, fontsize=7, fontweight='bold', va='center', ha='center')

    vy -= vrow_h

ax_v.plot([0, 1], [0.022, 0.022], color=GRAY_LINE, linewidth=0.8)
ax_v.text(0.5, 0.011, '← Anterior   1  2  3  ...  105   Próxima →',
          color=GRAY_TEXT, fontsize=8.5, ha='center', va='center')

out2 = r'c:\Users\user\OneDrive\Backup Note\Projetos\Antlia\cvc\CVC\scripts\mockup_v2_acoes_pendentes.png'
plt.savefig(out2, dpi=150, bbox_inches='tight', facecolor=BG)
plt.close(fig2)
print(f'Salvo: {out2}')
