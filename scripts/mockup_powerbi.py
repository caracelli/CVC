import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe

# CVC brand colors
CVC_BLUE   = '#3757A2'
CVC_YELLOW = '#FEC805'
CVC_DARK   = '#1E3472'
CVC_LIGHT  = '#EEF2FF'
BG         = '#F4F6FB'
WHITE      = '#FFFFFF'
GRAY_LINE  = '#DADADA'

fig = plt.figure(figsize=(22, 14), facecolor=BG)

# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════
ax_h = fig.add_axes([0, 0.92, 1, 0.08])
ax_h.set_facecolor(CVC_BLUE)
ax_h.add_patch(FancyBboxPatch((0,0), 0.006, 1, boxstyle='square,pad=0',
               facecolor=CVC_YELLOW, edgecolor='none', transform=ax_h.transAxes))
ax_h.text(0.018, 0.54, 'IAM Analytics', color=WHITE, fontsize=20,
          fontweight='bold', va='center', transform=ax_h.transAxes)
ax_h.text(0.018, 0.20, 'Governança de Acessos — CVC Corp', color='#AAC0E8',
          fontsize=10, va='center', transform=ax_h.transAxes)
ax_h.text(0.99, 0.54, 'Referência: Abril / 2026', color=CVC_YELLOW,
          fontsize=10, fontweight='bold', va='center', ha='right', transform=ax_h.transAxes)
ax_h.text(0.99, 0.20, 'Última atualização: 12/05/2026  14:33', color='#AAC0E8',
          fontsize=9, va='center', ha='right', transform=ax_h.transAxes)
ax_h.axis('off')

# ═══════════════════════════════════════════════════════════════
# TAB BAR
# ═══════════════════════════════════════════════════════════════
ax_tabs = fig.add_axes([0, 0.885, 1, 0.037])
ax_tabs.set_facecolor('#E2E8F4')
tabs = [
    ('Visão Geral',          0.01, True),
    ('Lista de Divergências', 0.165, False),
    ('Desligados c/ Acesso', 0.335, False),
    ('Perfis Inválidos',     0.495, False),
    ('Sem Vínculo RH',       0.645, False),
]
for label, x, active in tabs:
    w = 0.14
    bg  = WHITE      if active else '#E2E8F4'
    ec  = CVC_YELLOW if active else GRAY_LINE
    lw  = 2.5        if active else 0.5
    ax_tabs.add_patch(FancyBboxPatch((x, 0.06), w, 0.88,
        boxstyle='round,pad=0.01', linewidth=lw,
        edgecolor=ec, facecolor=bg, transform=ax_tabs.transAxes))
    if active:
        ax_tabs.add_patch(FancyBboxPatch((x, 0.06), w, 0.14,
            boxstyle='square,pad=0', facecolor=CVC_YELLOW, edgecolor='none',
            transform=ax_tabs.transAxes))
    col = CVC_DARK if active else '#777777'
    ax_tabs.text(x + w/2, 0.55, label, color=col, fontsize=9,
                 fontweight='bold' if active else 'normal',
                 va='center', ha='center', transform=ax_tabs.transAxes)
ax_tabs.axis('off')

# ═══════════════════════════════════════════════════════════════
# FILTRO POR SISTEMAS (slicer)
# ═══════════════════════════════════════════════════════════════
ax_f = fig.add_axes([0.01, 0.80, 0.98, 0.075])
ax_f.set_facecolor(WHITE)
for sp in ax_f.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.8)
ax_f.text(0.005, 0.72, 'Filtrar por Sistema:', color=CVC_DARK,
          fontsize=9, fontweight='bold', va='center', transform=ax_f.transAxes)

sistemas = [
    ('Todos',      True),
    ('SYSTUR',     False),
    ('SIGOT',      False),
    ('SICA RA',    False),
    ('SICA ESFERA',False),
    ('IC',         False),
]
sx = 0.14
for nome, sel in sistemas:
    bg  = CVC_YELLOW if sel else '#F0F4FF'
    ec  = CVC_BLUE   if sel else GRAY_LINE
    tc  = CVC_DARK   if sel else '#555555'
    fw  = 'bold'     if sel else 'normal'
    ax_f.add_patch(FancyBboxPatch((sx, 0.15), 0.10, 0.68,
        boxstyle='round,pad=0.02', facecolor=bg, edgecolor=ec, linewidth=1.2,
        transform=ax_f.transAxes))
    ax_f.text(sx + 0.05, 0.52, nome, color=tc, fontsize=9,
              fontweight=fw, va='center', ha='center', transform=ax_f.transAxes)
    sx += 0.13
ax_f.axis('off')

# ═══════════════════════════════════════════════════════════════
# KPI CARDS
# ═══════════════════════════════════════════════════════════════
kpis = [
    ('Usuários Analisados', '14.212', CVC_BLUE,   '#EEF2FF', '▲ 0%'),
    ('Desligados c/ Acesso','243',    '#C0392B',  '#FDECEC', '▲ novo'),
    ('Perfis Inválidos',    '367',    '#B7770D',  '#FFFBE6', '▲ novo'),
    ('Sem Vínculo RH',      '4.957',  '#6C3483',  '#F5EEF8', '▲ novo'),
    ('Total Divergências',  '5.567',  '#1E8449',  '#EAFAF1', '▲ novo'),
]
for i, (title, value, color, bg, trend) in enumerate(kpis):
    x    = 0.01 + i * 0.198
    ax_k = fig.add_axes([x, 0.66, 0.185, 0.125])
    ax_k.set_facecolor(bg)
    for sp in ax_k.spines.values():
        sp.set_edgecolor(color); sp.set_linewidth(2)
    ax_k.add_patch(FancyBboxPatch((0,0.88), 1, 0.12,
        boxstyle='square,pad=0', facecolor=color, edgecolor='none',
        transform=ax_k.transAxes))
    ax_k.text(0.5, 0.60, value, color=color, fontsize=23,
              fontweight='bold', ha='center', va='center', transform=ax_k.transAxes)
    ax_k.text(0.5, 0.24, title, color='#444444', fontsize=8.5,
              ha='center', va='center', transform=ax_k.transAxes)
    ax_k.set_xticks([]); ax_k.set_yticks([])

# ═══════════════════════════════════════════════════════════════
# BAR CHART — por tipo
# ═══════════════════════════════════════════════════════════════
ax_bar = fig.add_axes([0.01, 0.35, 0.42, 0.295])
ax_bar.set_facecolor(WHITE)
for sp in ax_bar.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.8)
tipos   = ['Sem Vínculo RH', 'Perfil Inválido', 'Desligado c/ Acesso']
valores = [4957, 367, 243]
cores   = ['#6C3483', '#B7770D', '#C0392B']
bars = ax_bar.barh(tipos, valores, color=cores, height=0.48)
for bar, val in zip(bars, valores):
    ax_bar.text(bar.get_width() + 60, bar.get_y() + bar.get_height()/2,
                f'{val:,}', va='center', fontsize=10, color='#333333', fontweight='bold')
ax_bar.set_title('Divergências por Tipo', fontsize=11, fontweight='bold',
                 color=CVC_DARK, pad=10, loc='left')
ax_bar.set_xlim(0, 6200)
ax_bar.spines['top'].set_visible(False)
ax_bar.spines['right'].set_visible(False)
ax_bar.tick_params(labelsize=9)
ax_bar.set_facecolor(WHITE)

# ═══════════════════════════════════════════════════════════════
# DONUT — por sistema
# ═══════════════════════════════════════════════════════════════
ax_pie = fig.add_axes([0.455, 0.35, 0.25, 0.295])
ax_pie.set_facecolor(WHITE)
ax_pie.pie(
    [5567], labels=['SYSTUR'],
    colors=[CVC_BLUE], startangle=90,
    wedgeprops=dict(width=0.52),
    autopct=lambda p: f'{p:.0f}%',
    textprops={'fontsize': 9},
)
ax_pie.add_patch(plt.Circle((0,0), 0.48, fc=WHITE))
ax_pie.text(0, 0, '5.567', ha='center', va='center',
            fontsize=16, fontweight='bold', color=CVC_DARK)
ax_pie.set_title('Por Sistema', fontsize=11, fontweight='bold',
                 color=CVC_DARK, pad=10)

# ═══════════════════════════════════════════════════════════════
# LINE — evolução histórica
# ═══════════════════════════════════════════════════════════════
ax_ln = fig.add_axes([0.73, 0.35, 0.26, 0.295])
ax_ln.set_facecolor(WHITE)
for sp in ax_ln.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.8)
meses = ['Jan', 'Fev', 'Mar', 'Abr']
vals  = [0, 0, 0, 5567]
ax_ln.plot(meses, vals, color=CVC_BLUE, linewidth=2.5, marker='o',
           markersize=7, markerfacecolor=CVC_YELLOW, markeredgecolor=CVC_BLUE)
ax_ln.fill_between(meses, vals, alpha=0.12, color=CVC_BLUE)
ax_ln.set_title('Evolução Histórica', fontsize=11, fontweight='bold',
                color=CVC_DARK, pad=10)
ax_ln.spines['top'].set_visible(False)
ax_ln.spines['right'].set_visible(False)
ax_ln.tick_params(labelsize=9)
ax_ln.set_ylim(0, 7000)
ax_ln.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x):,}'))

# ═══════════════════════════════════════════════════════════════
# TABELA HIERÁRQUICA — Lista de Divergências
# ═══════════════════════════════════════════════════════════════
ax_t = fig.add_axes([0.01, 0.01, 0.98, 0.325])
ax_t.set_facecolor(WHITE)
for sp in ax_t.spines.values():
    sp.set_edgecolor(GRAY_LINE); sp.set_linewidth(0.8)
ax_t.axis('off')
ax_t.set_xlim(0, 1)
ax_t.set_ylim(0, 1)

# Título da seção
ax_t.text(0.005, 0.95, 'Lista de Divergências', color=CVC_DARK,
          fontsize=11, fontweight='bold', va='center', transform=ax_t.transAxes)
ax_t.text(0.98, 0.95, 'Exibindo: 5.567 registros', color='#888888',
          fontsize=8.5, va='center', ha='right', transform=ax_t.transAxes)

# Cabeçalho da tabela
cols  = [' ', 'Usuário', 'Nome Completo', 'Matrícula', 'N° Diverg.', 'Tipos Encontrados', 'Sistema']
col_x = [0.005, 0.045, 0.195, 0.375, 0.485, 0.590, 0.870]
col_w = [0.03,  0.14,  0.17,  0.10,  0.09,  0.27,  0.10]

ax_t.add_patch(FancyBboxPatch((0, 0.825), 1, 0.095,
    boxstyle='square,pad=0', facecolor=CVC_BLUE, edgecolor='none',
    transform=ax_t.transAxes))
for cx, col in zip(col_x, cols):
    ax_t.text(cx + 0.005, 0.872, col, color=WHITE, fontsize=8.5,
              fontweight='bold', va='center', transform=ax_t.transAxes)

# Dados de linhas
rows = [
    # (expandido, usuario, nome, matricula, qtd, tipos, sistema)
    (True,  'JOAO.SILVA',   'João da Silva Santos',    '12345', '3', 'DESLIGADO | PERFIL | SEM_VÍNCULO', 'SYSTUR'),
    (False, 'MARIA.SOUZA',  'Maria Aparecida Souza',   '67890', '2', 'DESLIGADO | PERFIL',               'SYSTUR'),
    (False, 'PEDRO.COSTA',  'Pedro Henrique Costa',    '11111', '1', 'PERFIL_INVALIDO',                  'SYSTUR'),
    (False, 'ANA.FERREIRA', 'Ana Paula Ferreira',      '22222', '1', 'ACESSO_SEM_VINCULO_RH',            'SYSTUR'),
]
children = [
    ('ACESSO_DESLIGADO',    'Funcionário desligado com acesso ativo no sistema',  '#FDECEC', '#C0392B'),
    ('PERFIL_INVALIDO',     'Perfil "CONSULTA" não permitido — esperado: OPERADOR', '#FFFBE6', '#B7770D'),
    ('ACESSO_SEM_VINCULO_RH','CPF 123.456.789-00 não localizado na base RH',       '#F5EEF8', '#6C3483'),
]

y = 0.80
row_h = 0.092
child_h = 0.080

for idx, (expanded, usr, nome, mat, qtd, tipos, sis) in enumerate(rows):
    btn = '▼' if expanded else '+'
    bg  = CVC_LIGHT if idx % 2 == 0 else WHITE
    ax_t.add_patch(FancyBboxPatch((0, y - row_h + 0.005), 1, row_h - 0.005,
        boxstyle='square,pad=0', facecolor=bg, edgecolor=GRAY_LINE, linewidth=0.4,
        transform=ax_t.transAxes))

    # Yellow left bar for expanded row
    if expanded:
        ax_t.add_patch(FancyBboxPatch((0, y - row_h + 0.005), 0.004, row_h - 0.005,
            boxstyle='square,pad=0', facecolor=CVC_YELLOW, edgecolor='none',
            transform=ax_t.transAxes))

    vals_row = [btn, usr, nome, mat, qtd, tipos, sis]
    clrs_row = [CVC_BLUE, CVC_DARK, '#333333', '#555555', CVC_BLUE, '#666666', '#333333']
    fws_row  = ['bold', 'bold', 'normal', 'normal', 'bold', 'normal', 'normal']
    for cx, v, c, fw in zip(col_x, vals_row, clrs_row, fws_row):
        ax_t.text(cx + 0.007, y - row_h/2, v, color=c, fontsize=8.5,
                  fontweight=fw, va='center', clip_on=True, transform=ax_t.transAxes)
    y -= row_h

    if expanded:
        for (ctipo, cdesc, cbg, ccolor) in children:
            ax_t.add_patch(FancyBboxPatch((0.03, y - child_h + 0.005), 0.97, child_h - 0.005,
                boxstyle='square,pad=0', facecolor=cbg, edgecolor=GRAY_LINE, linewidth=0.3,
                transform=ax_t.transAxes))
            ax_t.add_patch(FancyBboxPatch((0.03, y - child_h + 0.005), 0.004, child_h - 0.005,
                boxstyle='square,pad=0', facecolor=ccolor, edgecolor='none',
                transform=ax_t.transAxes))
            ax_t.text(0.045, y - child_h/2, ctipo, color=ccolor, fontsize=8,
                      fontweight='bold', va='center', style='italic', transform=ax_t.transAxes)
            ax_t.text(0.24, y - child_h/2, cdesc, color='#444444', fontsize=8,
                      va='center', transform=ax_t.transAxes)
            y -= child_h

# Footer line
ax_t.plot([0, 1], [0.02, 0.02], color=GRAY_LINE, linewidth=0.8, transform=ax_t.transAxes)
ax_t.text(0.5, 0.01, '← Anterior   1  2  3  ...  42   Próxima →',
          color='#888888', fontsize=8.5, ha='center', va='center', transform=ax_t.transAxes)

out = r'c:\Users\user\OneDrive\Backup Note\Projetos\Antlia\cvc\CVC\scripts\mockup_powerbi.png'
plt.savefig(out, dpi=160, bbox_inches='tight', facecolor=BG)
print(f'Imagem salva: {out}')
