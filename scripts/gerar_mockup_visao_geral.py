"""Gera mockup HTML standalone da aba 'Visao Geral' do painel.

Le dados reais de CVC_IAM_ANALYTICS/DADOS/BANCO/iam_analytics.db e cospe
docs/mockup_visao_geral.html — abre em qualquer browser, offline, sem deps.

Uso:
    python scripts/gerar_mockup_visao_geral.py
"""
import datetime
import json
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "CVC_IAM_ANALYTICS" / "DADOS" / "BANCO" / "iam_analytics.db"
SAIDA = RAIZ / "docs" / "mockup_visao_geral.html"


def coletar():
    c = sqlite3.connect(str(DB))
    d = {}

    # KPIs
    d["pendentes"] = c.execute(
        "SELECT COUNT(*) FROM validacao_acessos WHERE situacao_acao='PENDENTE'"
    ).fetchone()[0]
    d["acessos_deslig"] = c.execute(
        "SELECT COUNT(*) FROM acessos_sistemas a "
        "JOIN rh_desligados d ON a.matricula_vinculada = d.matricula"
    ).fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM acessos_sistemas").fetchone()[0]
    vinc = c.execute(
        "SELECT COUNT(*) FROM acessos_sistemas "
        "WHERE matricula_vinculada IS NOT NULL "
        "AND metodo_vinculacao NOT IN ('NAO_VINCULADO','FUZZY','')"
    ).fetchone()[0]
    d["cobertura_pct"] = round(100 * vinc / total, 1) if total else 0
    d["total_acessos"] = total
    d["acessos_vinc"] = vinc
    # Quarentena ainda nao temos (tabela criada pelo visualizador) — mock 0
    d["quarentena_ativa"] = 0

    # Movimentacao RH (mockup: usar contagens estaticas — em prod viria da
    # tabela `historico` filtrada por data_snapshot)
    d["mov_admissoes"] = 42        # placeholder pra fase 1 — ainda nao calculamos
    d["mov_alteracoes"] = 78
    d["mov_desligamentos"] = 23

    # Chamados do mes — placeholder (em prod viria de validacao_acessos +
    # resolucoes filtradas por data)
    d["chamados_identificados"] = d["pendentes"]   # neste run, todos novos
    d["chamados_resolvidos"] = 0
    d["tempo_medio_resol_dias"] = 8                # placeholder

    # Divergencias por tipo
    d["div_tipos"] = dict(c.execute(
        "SELECT tipo, COUNT(*) FROM divergencias GROUP BY tipo"
    ).fetchall())

    # Concentracao por sistema
    d["div_sistemas"] = dict(c.execute(
        "SELECT sistema, COUNT(*) FROM divergencias GROUP BY sistema ORDER BY 2 DESC"
    ).fetchall())

    # Top 10 desligados recentes ainda com acesso ativo
    top = []
    for r in c.execute("""
        SELECT d.nome, d.data_desligamento, d.cargo_descricao,
               COUNT(DISTINCT a.sistema) AS sistemas, COUNT(*) AS perfis
        FROM rh_desligados d
        JOIN acessos_sistemas a ON a.matricula_vinculada = d.matricula
        WHERE d.data_desligamento IS NOT NULL
        GROUP BY d.matricula
        ORDER BY d.data_desligamento DESC LIMIT 10
    """):
        hoje = datetime.date.today()
        try:
            ddes = datetime.date.fromisoformat(r[1])
            dias = (hoje - ddes).days
        except Exception:
            dias = None
        top.append({
            "nome": r[0], "data": r[1], "dias": dias, "cargo": r[2],
            "sistemas": r[3], "perfis": r[4],
        })
    d["top_urgentes"] = top

    # Aging (placeholder — dataset atual nao tem variacao temporal)
    d["aging"] = {"0-7": d["pendentes"], "8-30": 0, "31-90": 0, "90+": 0}

    # Universo RH
    d["rh_ativos"] = c.execute("SELECT COUNT(*) FROM rh_ativos").fetchone()[0]
    d["rh_desligados"] = c.execute("SELECT COUNT(*) FROM rh_desligados").fetchone()[0]

    # Metadata
    d["dt_geracao"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    c.close()
    return d


def fmt(n):
    """Formata numero com separador de milhar (estilo BR)."""
    return f"{n:,}".replace(",", ".")


def donut_svg(d_tipos):
    """Devolve SVG de um donut com 3 segmentos (cores fixas)."""
    total = sum(d_tipos.values()) or 1
    cores = {
        "ACESSO_DESLIGADO": "#D14343",
        "ACESSO_SEM_VINCULO_RH": "#E08A1F",
        "PERFIL_INVALIDO": "#7B68EE",
    }
    rotulos = {
        "ACESSO_DESLIGADO": "Acesso de Desligado",
        "ACESSO_SEM_VINCULO_RH": "Sem Vínculo RH",
        "PERFIL_INVALIDO": "Perfil Inválido",
    }
    # circle: r=60, perimetro = 2πr ≈ 377
    perim = 377.0
    cx, cy = 80, 80
    r = 60
    inicio = -90  # comeca no topo
    arcs = []
    legenda = []
    for tipo, qtd in sorted(d_tipos.items(), key=lambda x: -x[1]):
        frac = qtd / total
        pct = frac * 100
        cor = cores.get(tipo, "#999")
        rot = rotulos.get(tipo, tipo)
        dash = frac * perim
        gap = perim - dash
        # offset (em SVG, stroke-dashoffset comeca em 0 mas o stroke comeca do
        # ponto 3 horas; rotacionamos -90 + inicio_acumulado pra comecar no topo)
        offset_visual = -inicio * (perim / 360)
        arcs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{cor}" '
            f'stroke-width="22" stroke-dasharray="{dash:.1f} {gap:.1f}" '
            f'stroke-dashoffset="{offset_visual:.1f}" '
            f'transform="rotate(-90 {cx} {cy})" />'
        )
        inicio += frac * 360
        legenda.append(
            f'<div class="leg-item"><span class="dot" style="background:{cor}"></span>'
            f'<span class="leg-label">{rot}</span>'
            f'<span class="leg-val">{fmt(qtd)} <small>({pct:.1f}%)</small></span></div>'
        )

    svg = (f'<svg viewBox="0 0 160 160" width="160" height="160">'
           f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#EEF1F6" '
           f'stroke-width="22" />'
           + "".join(arcs)
           + f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="22" '
           f'font-weight="700" fill="#1F2D5C">{fmt(total)}</text>'
           f'<text x="{cx}" y="{cy+14}" text-anchor="middle" font-size="9" '
           f'fill="#7A8294">divergências</text>'
           f'</svg>')
    return svg + '<div class="legenda">' + "".join(legenda) + "</div>"


def barras_horizontais(dados, cor="#1F2D5C"):
    """Barras horizontais (sistema -> qtd)."""
    if not dados:
        return ""
    maximo = max(dados.values())
    out = ['<div class="bars">']
    for label, qtd in dados.items():
        pct = 100 * qtd / maximo
        out.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{label}</span>'
            f'<div class="bar-track"><div class="bar-fill" '
            f'style="width:{pct:.1f}%;background:{cor}"></div></div>'
            f'<span class="bar-val">{fmt(qtd)}</span>'
            f'</div>'
        )
    out.append('</div>')
    return "".join(out)


def render_html(d):
    donut = donut_svg(d["div_tipos"])
    sistemas = barras_horizontais(d["div_sistemas"], cor="#1F2D5C")
    saldo = d["chamados_identificados"] - d["chamados_resolvidos"]
    saldo_sinal = "+" if saldo >= 0 else ""
    saldo_classe = "saldo-pos" if saldo > 0 else "saldo-neg" if saldo < 0 else ""

    # Top urgentes
    linhas_top = []
    for t in d["top_urgentes"]:
        dias_str = f"{t['dias']}d atrás" if t["dias"] is not None else "?"
        risco = "risco-alto" if t["perfis"] > 50 else "risco-medio" if t["perfis"] > 10 else "risco-baixo"
        linhas_top.append(
            f'<tr>'
            f'<td>{t["nome"]}</td>'
            f'<td><span class="dias">{dias_str}</span></td>'
            f'<td>{t["cargo"]}</td>'
            f'<td>{t["sistemas"]}</td>'
            f'<td><span class="badge {risco}">{t["perfis"]}</span></td>'
            f'<td><button class="btn-acao">Resolver</button></td>'
            f'</tr>'
        )
    top_html = "".join(linhas_top)

    # Movimentacao RH
    mov_total = d["mov_admissoes"] + d["mov_alteracoes"] + d["mov_desligamentos"] or 1
    mov_admis_pct = 100 * d["mov_admissoes"] / mov_total
    mov_alter_pct = 100 * d["mov_alteracoes"] / mov_total
    mov_desli_pct = 100 * d["mov_desligamentos"] / mov_total

    # Aging
    aging_html = ""
    aging_max = max(d["aging"].values()) or 1
    for faixa, qtd in d["aging"].items():
        pct = 100 * qtd / aging_max
        cor_aging = ("#7B68EE" if faixa == "0-7"
                     else "#3B8FF5" if faixa == "8-30"
                     else "#E08A1F" if faixa == "31-90"
                     else "#D14343")
        aging_html += (
            f'<div class="bar-row">'
            f'<span class="bar-label">{faixa} dias</span>'
            f'<div class="bar-track"><div class="bar-fill" '
            f'style="width:{pct:.1f}%;background:{cor_aging}"></div></div>'
            f'<span class="bar-val">{fmt(qtd)}</span>'
            f'</div>'
        )

    chamados_max = max(d["chamados_identificados"], d["chamados_resolvidos"], 1)
    chamados_id_pct = 100 * d["chamados_identificados"] / chamados_max
    chamados_re_pct = 100 * d["chamados_resolvidos"] / chamados_max

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<title>CVC IAM Analytics — Visão Geral (mockup)</title>
<style>
:root {{
  --azul: #1F2D5C;
  --azul-claro: #3B5189;
  --bg: #F5F6FA;
  --card: #FFFFFF;
  --texto: #1A1F36;
  --texto-soft: #6E7686;
  --verde: #2B7A2B;
  --amarelo: #E08A1F;
  --vermelho: #D14343;
  --linha: #E7EBF2;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, "Segoe UI", Arial, sans-serif;
  background: var(--bg);
  color: var(--texto);
  padding: 20px 32px 40px;
  min-height: 100vh;
}}
.header {{
  display: flex; justify-content: space-between; align-items: flex-end;
  padding-bottom: 16px; border-bottom: 1px solid var(--linha); margin-bottom: 20px;
}}
.brand-block {{ display: flex; flex-direction: column; gap: 4px; }}
.brand {{ color: var(--azul); font-size: 11.5px; font-weight: 700; letter-spacing: .12em; }}
h1 {{ color: var(--azul); font-size: 24px; font-weight: 700; }}
.tabs {{ display: flex; gap: 4px; }}
.tab {{
  padding: 8px 16px; font-size: 13px; font-weight: 600; color: var(--texto-soft);
  background: transparent; border: none; cursor: pointer; border-bottom: 3px solid transparent;
}}
.tab.active {{ color: var(--azul); border-bottom-color: var(--azul); }}
.banner {{
  background: var(--card); padding: 10px 16px; border-radius: 8px;
  margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;
  font-size: 12.5px; color: var(--texto-soft); border-left: 3px solid var(--azul);
}}
.banner b {{ color: var(--azul); }}

/* Grid */
.row {{ display: grid; gap: 16px; margin-bottom: 18px; }}
.row.cols-4 {{ grid-template-columns: repeat(4, 1fr); }}
.row.cols-2 {{ grid-template-columns: 1fr 1fr; }}
.row.cols-3-2 {{ grid-template-columns: 3fr 2fr; }}
.row.cols-2-3 {{ grid-template-columns: 2fr 3fr; }}

.card {{
  background: var(--card); border-radius: 10px; padding: 18px 20px;
  box-shadow: 0 2px 8px rgba(31,45,92,.06);
}}
.card h3 {{
  color: var(--texto-soft); font-size: 11.5px; text-transform: uppercase;
  letter-spacing: .08em; margin-bottom: 10px; font-weight: 600;
}}
.card h2 {{ color: var(--azul); font-size: 14.5px; margin-bottom: 14px; font-weight: 700; }}

/* KPI cards */
.kpi {{ display: flex; flex-direction: column; gap: 6px; }}
.kpi-valor {{
  font-size: 30px; font-weight: 700; color: var(--azul); line-height: 1.1;
}}
.kpi-sub {{
  font-size: 11.5px; color: var(--texto-soft); display: flex; gap: 6px; align-items: center;
}}
.delta {{ font-weight: 600; padding: 1px 6px; border-radius: 4px; font-size: 11px; }}
.delta-bom {{ color: var(--verde); background: #E5F3E5; }}
.delta-ruim {{ color: var(--vermelho); background: #FBE5E5; }}
.kpi.alerta .kpi-valor {{ color: var(--vermelho); }}
.kpi.atencao .kpi-valor {{ color: var(--amarelo); }}
.kpi.ok .kpi-valor {{ color: var(--verde); }}

/* Chamados / movimentacao */
.chamado-row {{
  display: grid; grid-template-columns: 140px 1fr 60px; gap: 10px;
  align-items: center; padding: 8px 0;
}}
.chamado-label {{ font-size: 12.5px; color: var(--texto-soft); font-weight: 500; }}
.chamado-track {{ background: var(--bg); height: 22px; border-radius: 4px; overflow: hidden; }}
.chamado-fill {{ height: 100%; border-radius: 4px; display: flex; align-items: center;
  padding-left: 8px; color: white; font-size: 11.5px; font-weight: 600; }}
.chamado-val {{ font-weight: 700; color: var(--azul); font-size: 13.5px; text-align: right; }}
.saldo {{
  margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--linha);
  display: flex; justify-content: space-between; font-size: 12.5px;
}}
.saldo-pos {{ color: var(--vermelho); font-weight: 700; }}
.saldo-neg {{ color: var(--verde); font-weight: 700; }}
.saldo-info {{ color: var(--texto-soft); font-size: 11.5px; }}

/* Donut */
.donut-wrap {{ display: flex; gap: 20px; align-items: center; }}
.legenda {{ flex: 1; display: flex; flex-direction: column; gap: 8px; }}
.leg-item {{
  display: grid; grid-template-columns: 14px 1fr auto; gap: 8px; align-items: center;
  font-size: 12.5px; padding: 4px 0;
}}
.dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.leg-label {{ color: var(--texto); }}
.leg-val {{ font-weight: 700; color: var(--azul); }}
.leg-val small {{ color: var(--texto-soft); font-weight: 500; }}

/* Bars */
.bars {{ display: flex; flex-direction: column; gap: 8px; }}
.bar-row {{
  display: grid; grid-template-columns: 90px 1fr 80px; gap: 10px; align-items: center;
  font-size: 12.5px;
}}
.bar-label {{ color: var(--texto-soft); font-weight: 500; }}
.bar-track {{ background: var(--bg); height: 22px; border-radius: 4px; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 4px; transition: width .4s; }}
.bar-val {{ text-align: right; font-weight: 700; color: var(--azul); font-size: 13px; }}

/* Tabela top */
table.top-tab {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
table.top-tab th, table.top-tab td {{
  padding: 9px 10px; text-align: left; border-bottom: 1px solid var(--linha);
}}
table.top-tab th {{
  color: var(--texto-soft); text-transform: uppercase; font-size: 10.5px;
  letter-spacing: .06em; background: var(--bg);
}}
table.top-tab td:first-child {{ font-weight: 600; color: var(--azul); }}
.dias {{ color: var(--texto-soft); font-size: 11.5px; }}
.badge {{
  display: inline-block; min-width: 28px; padding: 2px 8px; border-radius: 4px;
  font-weight: 700; text-align: center; font-size: 11.5px;
}}
.risco-alto {{ background: #FBE5E5; color: var(--vermelho); }}
.risco-medio {{ background: #FBF1E5; color: var(--amarelo); }}
.risco-baixo {{ background: #E5F3E5; color: var(--verde); }}
.btn-acao {{
  background: var(--azul); color: white; border: none; padding: 5px 12px;
  border-radius: 4px; font-size: 11.5px; font-weight: 600; cursor: pointer;
}}
.btn-acao:hover {{ background: var(--azul-claro); }}
.ver-todos {{
  text-align: right; padding-top: 10px; margin-top: 8px;
  border-top: 1px solid var(--linha);
}}
.ver-todos a {{ color: var(--azul); text-decoration: none; font-size: 12.5px; font-weight: 600; }}

/* Movimentacao RH bar empilhada */
.mov-bar {{ display: flex; height: 28px; border-radius: 4px; overflow: hidden; margin-bottom: 10px; }}
.mov-seg {{ display: flex; align-items: center; justify-content: center; color: white;
  font-size: 12px; font-weight: 700; }}
.mov-leg {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; }}
.mov-leg span {{ display: flex; align-items: center; gap: 6px; color: var(--texto-soft); }}
.mov-leg .dot {{ width: 10px; height: 10px; border-radius: 2px; }}

/* Sugestoes */
.sug-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 14px; }}
.sug {{
  background: var(--bg); padding: 10px 12px; border-radius: 6px; font-size: 12px;
  cursor: pointer; border-left: 3px solid var(--azul);
}}
.sug:hover {{ background: #E7EBF2; }}
.sug b {{ color: var(--azul); }}

/* Footer */
.foot {{
  margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--linha);
  text-align: center; color: var(--texto-soft); font-size: 11px;
}}
</style></head><body>

<div class="header">
  <div class="brand-block">
    <div class="brand">CVC · IAM ANALYTICS</div>
    <h1>Visão Geral</h1>
  </div>
  <div class="tabs">
    <button class="tab active">Visão Geral</button>
    <button class="tab">Consulta</button>
    <button class="tab">Quarentena</button>
    <button class="tab">Histórico</button>
  </div>
</div>

<div class="banner">
  <div>🕒 <b>Última atualização:</b> {d["dt_geracao"]} · banco gerado pelo Processador ·
    {fmt(d["rh_ativos"])} ativos · {fmt(d["rh_desligados"])} desligados · {fmt(d["total_acessos"])} acessos</div>
  <div><button class="btn-acao">Atualizar</button></div>
</div>

<!-- LINHA 1 — 4 KPIs -->
<div class="row cols-4">
  <div class="card kpi alerta">
    <h3>🔴 Pendências Abertas</h3>
    <div class="kpi-valor">{fmt(d["pendentes"])}</div>
    <div class="kpi-sub">
      Itens com situação <b style="color:var(--vermelho)">PENDENTE</b>
      <span class="delta delta-bom">▼ 12%</span>
    </div>
  </div>
  <div class="card kpi alerta">
    <h3>⚠️ Acessos de Desligado</h3>
    <div class="kpi-valor">{fmt(d["acessos_deslig"])}</div>
    <div class="kpi-sub">
      Acessos ativos de pessoas já desligadas
      <span class="delta delta-ruim">▲ 5%</span>
    </div>
  </div>
  <div class="card kpi ok">
    <h3>📊 Cobertura RH</h3>
    <div class="kpi-valor">{d["cobertura_pct"]}%</div>
    <div class="kpi-sub">
      {fmt(d["acessos_vinc"])} de {fmt(d["total_acessos"])} acessos vinculados
      <span class="delta delta-bom">▲ 2.3pp</span>
    </div>
  </div>
  <div class="card kpi">
    <h3>⏱️ Em Quarentena</h3>
    <div class="kpi-valor">{fmt(d["quarentena_ativa"])}</div>
    <div class="kpi-sub">
      Usuários aguardando resolução
    </div>
  </div>
</div>

<!-- LINHA 2 — Chamados & Movimentacao RH -->
<div class="row cols-2">
  <div class="card">
    <h2>📨 Chamados do Mês</h2>
    <div class="chamado-row">
      <span class="chamado-label">Identificados</span>
      <div class="chamado-track">
        <div class="chamado-fill" style="width:{chamados_id_pct:.1f}%;background:var(--azul-claro)">
          {fmt(d["chamados_identificados"])}
        </div>
      </div>
      <span class="chamado-val">{fmt(d["chamados_identificados"])}</span>
    </div>
    <div class="chamado-row">
      <span class="chamado-label">Resolvidos</span>
      <div class="chamado-track">
        <div class="chamado-fill" style="width:{chamados_re_pct:.1f}%;background:var(--verde)">
          {fmt(d["chamados_resolvidos"])}
        </div>
      </div>
      <span class="chamado-val">{fmt(d["chamados_resolvidos"])}</span>
    </div>
    <div class="saldo">
      <span>Saldo aberto: <span class="{saldo_classe}">{saldo_sinal}{fmt(saldo)}</span></span>
      <span class="saldo-info">Tempo médio de resolução: <b>{d["tempo_medio_resol_dias"]} dias</b></span>
    </div>
  </div>

  <div class="card">
    <h2>👥 Movimentação RH (últimos 30 dias)</h2>
    <div class="mov-bar">
      <div class="mov-seg" style="width:{mov_admis_pct:.1f}%;background:var(--verde)" title="Admissões">{d["mov_admissoes"]}</div>
      <div class="mov-seg" style="width:{mov_alter_pct:.1f}%;background:var(--azul-claro)" title="Alterações">{d["mov_alteracoes"]}</div>
      <div class="mov-seg" style="width:{mov_desli_pct:.1f}%;background:var(--vermelho)" title="Desligamentos">{d["mov_desligamentos"]}</div>
    </div>
    <div class="mov-leg">
      <span><div class="dot" style="background:var(--verde)"></div> Admissões: <b>{d["mov_admissoes"]}</b></span>
      <span><div class="dot" style="background:var(--azul-claro)"></div> Alterações cargo/CC: <b>{d["mov_alteracoes"]}</b></span>
      <span><div class="dot" style="background:var(--vermelho)"></div> Desligamentos: <b>{d["mov_desligamentos"]}</b></span>
    </div>
    <p style="margin-top:14px;font-size:11.5px;color:var(--texto-soft)">
      → Essa movimentação gerou aproximadamente <b>{int(0.65 * (d["mov_admissoes"]+d["mov_alteracoes"]+d["mov_desligamentos"]))}</b>
      itens de ação esta semana.
    </p>
  </div>
</div>

<!-- LINHA 3 — Divergencias por tipo (donut) + Concentracao por sistema (barras) -->
<div class="row cols-2-3">
  <div class="card">
    <h2>🥧 Divergências por Tipo</h2>
    <div class="donut-wrap">
      {donut}
    </div>
  </div>
  <div class="card">
    <h2>📊 Concentração por Sistema</h2>
    {sistemas}
    <p style="margin-top:12px;font-size:11.5px;color:var(--texto-soft)">
      → Clique num sistema para abrir a aba Consulta filtrada.
    </p>
  </div>
</div>

<!-- LINHA 4 — Aging + Acoes imediatas -->
<div class="row cols-2-3">
  <div class="card">
    <h2>⏳ Aging das Pendências</h2>
    {aging_html}
    <p style="margin-top:12px;font-size:11px;color:var(--texto-soft)">
      A faixa <b style="color:var(--vermelho)">90+ dias</b> é o alarme silencioso —
      precisam ser resolvidas ou justificadas formalmente.
    </p>
  </div>
  <div class="card">
    <h2>🚨 Ação Imediata — Recém-desligados ainda com Acesso (Top 10)</h2>
    <table class="top-tab">
      <thead><tr>
        <th>Nome</th><th>Desligamento</th><th>Cargo</th>
        <th>Sistemas</th><th>Perfis</th><th></th>
      </tr></thead>
      <tbody>{top_html}</tbody>
    </table>
    <div class="ver-todos">
      <a href="#">Ver todos os {fmt(d["acessos_deslig"])} acessos de desligado →</a>
    </div>
  </div>
</div>

<!-- LINHA 5 — Sugestoes de exploracao -->
<div class="row">
  <div class="card">
    <h2>💡 Atalhos de Exploração</h2>
    <p style="font-size:12.5px;color:var(--texto-soft)">
      Cliques que respondem perguntas comuns sem precisar montar filtros.
    </p>
    <div class="sug-grid">
      <div class="sug">📈 <b>Funcionários com mais de 100 perfis</b> · explorar concentração de acesso</div>
      <div class="sug">⏰ <b>Acessos de desligados há mais de 90 dias</b> · risco regulatório</div>
      <div class="sug">🤝 <b>Cargos sem matriz de perfil definida</b> · auditoria da matriz</div>
      <div class="sug">🔎 <b>Vinculações por FUZZY ou NOME</b> · revisar manualmente (baixa confiança)</div>
      <div class="sug">🏨 <b>Família ACESSO_HOTEL_* (SIG)</b> · módulo hotelaria</div>
      <div class="sug">🚗 <b>Família ACESSO_CARRO_* (SIG)</b> · módulo locação</div>
    </div>
  </div>
</div>

<div class="foot">
  Mockup gerado a partir do banco real em {d["dt_geracao"]} ·
  CVC IAM Analytics — Fase 1 (SYSTUR + SIG) ·
  Dados fictícios apenas para visualização do layout
</div>

</body></html>
"""


def main():
    if not DB.exists():
        print(f"FALHA: banco nao existe em {DB}")
        print("Rode o Processador antes (python scripts/rodar_pipeline_headless.py)")
        return 1
    d = coletar()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(render_html(d), encoding="utf-8")
    print(f"OK -> {SAIDA}  ({SAIDA.stat().st_size/1024:.1f} KB)")
    print(f"\nAbra no navegador:")
    print(f"  start \"\" \"{SAIDA}\"   (Windows)")
    print(f"  xdg-open \"{SAIDA}\"    (Linux)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
