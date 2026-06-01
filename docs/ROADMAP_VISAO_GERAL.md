# Roadmap — Visão Geral (dashboard)

Decisões e cardápio de evolução da aba **Visão Geral**. Princípio acordado:
**corrige confusão = agora; adiciona capacidade = roadmap guiado pelo feedback
do cliente.** Não construir métricas/visualizações no escuro.

## Natureza e propósito
- A VG é um **dashboard operacional**: o usuário **acompanha os chamados**
  (pendências identificadas × resolvidas, aging, backlog).
- **No fim do projeto os chamados serão abertos no Jira** (Cards 25-26 —
  Integração Jira + Automação). Logo, toda a parte rica de chamado
  (SLA, status, ciclo de vida, aging por estado) deve nascer **do modelo do
  Jira**, não inventada antes — senão vira retrabalho. Lugar natural desse
  enriquecimento: **a fase Jira**.
- A VG **já é multi-sistema por design**: filtro de sistema paramétrico
  (sem filtro = todos), e "Concentração por Sistema" é cross-system. Hoje
  escopada a SYSTUR via `<visualizador><sistema>`; expande por **config**
  conforme os sistemas entram (Cards 8-14), **sem rework do painel**.

## Já entregue (2.1.x)
- Chamados em **janela móvel de 30 dias** (não mês-calendário — zerava no dia 1).
  Constante `VG_JANELA_DIAS` prepara a parametrização.
- **Resolvidos recalculados ao vivo** (dobrado + rede), não congelados no cache.
- VG **resiliente** a schema antigo (degrada o bloco + loga, não zera tudo).
- **Polimento visual** (commit isolado): paleta semântica colorblind-safe
  (vermelho=risco, âmbar=atenção, azul=neutro), aging em rampa de severidade,
  números arredondados. Tudo **2D flat**.

## Cardápio de evolução (guiado por feedback)

### Parametrização
- **Janela de tempo parametrizável**: seletor "últimos N dias" (presets
  7/15/30/60/90 + custom) e/ou âncora "até <data>" para navegar períodos.
  Hoje fixo em `VG_JANELA_DIAS=30`.
- **Metas/thresholds parametrizáveis** no `config.xml` (`<metas>`), todas
  opcionais. Para acompanhar chamados, as que importam são **operacionais**:
  - `aging_alerta_dias` (SLA — pendência mais velha vira vermelho)
  - saldo entrou×resolveu (backlog cresce/cai) — sem número, só ▲▼
  - `sla_resolucao_dias`, `cobertura_meta_pct`, `acessos_desligado_meta` (opcionais)

### Métrica / critério por tipo de informação
- **Evento** (segue o período): chamados identificados/resolvidos, movimentação RH.
- **Estado/foto** (posição atual; não recalcula pro passado sem histórico):
  cobertura, divergências por tipo, concentração por sistema, top desligados,
  aging, pendências abertas. Marcar com selo "posição atual".
- **Snapshot histórico no Processador** (gravar uma foto por execução) destrava
  tendências (sparklines) também nas métricas de "foto". Pré-requisito p/ trends.

### Conceitos de dashboard a aplicar (pesquisa Few/Tufte/2026)
- **Contexto em cada KPI**: comparação vs período anterior / meta + selo de status.
- **KPI × KRI**: separar desempenho (% resolvido, tempo) de risco (acessos de
  desligado, órfãos). Agrupar painéis por **Risco / Operação / Posição**.
- **Bullet graph** em métricas com meta (cobertura × alvo) no lugar de número solto.
- **Sparklines** de tendência nos tiles (precisa do snapshot histórico).
- Cor = semântica (nunca vermelho/verde juntos), **2D flat sempre** (3D distorce),
  sombra só de elevação de card (nunca no dado), arredondar (data-ink).

### Visual (trends 2026 — opcional)
- **Dark mode** (baseline 2026, mas trabalho extra).
- **Bento grid** (restyle de layout).
- **Glassmorphism**: NÃO recomendado p/ ferramenta de auditoria (reduz contraste).

## Não fazer agora (evita retrabalho)
- Não inventar SLA/status de chamado antes do Jira (Cards 25-26).
- Não criar caso especial "1 sistema" (a VG já contempla N sistemas).
- Não adicionar 3D / efeitos pesados (pioram leitura).
