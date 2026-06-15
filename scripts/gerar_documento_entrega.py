# -*- coding: utf-8 -*-
"""Gera o documento de entrega (.docx) da Fase 1 — SYSTUR.

Saida: ENTREGA/CVC_IAM_Analytics_Entrega_SYSTUR_v1.0.docx

Uso:  python scripts/gerar_documento_entrega.py
"""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Inches

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "ENTREGA" / "CVC_IAM_Analytics_Entrega_SYSTUR_v1.0.docx"

NAVY = RGBColor(0x1F, 0x2D, 0x5C)
TEAL = RGBColor(0x16, 0xA0, 0x85)
CINZA = RGBColor(0x5A, 0x63, 0x77)
NAVY_HEX = "1F2D5C"
TEAL_HEX = "16A085"
CLARO_HEX = "EAF1F4"


def _shade(cell, hex_cor):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_cor)
    tcpr.append(shd)


def _set_cell(cell, texto, *, bold=False, branco=False, size=10):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    run = p.add_run(str(texto))
    run.font.size = Pt(size)
    run.font.bold = bold
    if branco:
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def tabela(doc, cabecalho, linhas, larguras=None):
    t = doc.add_table(rows=1, cols=len(cabecalho))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    for i, c in enumerate(cabecalho):
        cell = t.rows[0].cells[i]
        _set_cell(cell, c, bold=True, branco=True)
        _shade(cell, NAVY_HEX)
    for r, linha in enumerate(linhas):
        cells = t.add_row().cells
        for i, val in enumerate(linha):
            _set_cell(cells[i], val)
            if r % 2 == 1:
                _shade(cells[i], CLARO_HEX)
    if larguras:
        for row in t.rows:
            for i, w in enumerate(larguras):
                row.cells[i].width = Inches(w)
    doc.add_paragraph()
    return t


def h1(doc, texto):
    p = doc.add_heading(level=1)
    run = p.add_run(texto)
    run.font.color.rgb = NAVY
    run.font.size = Pt(16)
    return p


def h2(doc, texto):
    p = doc.add_heading(level=2)
    run = p.add_run(texto)
    run.font.color.rgb = TEAL
    run.font.size = Pt(13)
    return p


def par(doc, texto, *, italico=False, cor=None, size=10.5):
    p = doc.add_paragraph()
    run = p.add_run(texto)
    run.font.size = Pt(size)
    run.italic = italico
    if cor:
        run.font.color.rgb = cor
    return p


def code_block(doc, texto):
    """Bloco monoespacado (Consolas) com fundo claro — para a arvore de pastas."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(6); pf.space_before = Pt(4)
    # sombreamento do paragrafo
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), CLARO_HEX)
    pPr.append(shd)
    for i, linha in enumerate(texto.split("\n")):
        if i:
            p.add_run().add_break()
        run = p.add_run(linha)
        run.font.name = "Consolas"
        run.font.size = Pt(8.5)
        run.font.color.rgb = NAVY
    return p


def bullet(doc, texto, *, neg=None):
    p = doc.add_paragraph(style="List Bullet")
    if neg:
        r = p.add_run(neg + " ")
        r.font.bold = True
        r.font.size = Pt(10.5)
    r2 = p.add_run(texto)
    r2.font.size = Pt(10.5)
    return p


def construir():
    doc = Document()
    # margens
    for s in doc.sections:
        s.top_margin = Inches(0.8); s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.9); s.right_margin = Inches(0.9)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)

    # ---- CAPA ----
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(80)
    r = p.add_run("CVC IAM Analytics"); r.font.size = Pt(30); r.font.bold = True
    r.font.color.rgb = NAVY
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Governança e Análise de Acessos"); r.font.size = Pt(14)
    r.font.color.rgb = CINZA
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(30)
    r = p.add_run("Documento de Entrega — Fase 1 (SYSTUR)")
    r.font.size = Pt(18); r.font.bold = True; r.font.color.rgb = TEAL
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Versão 1.0.0")
    r.font.size = Pt(13); r.font.color.rgb = CINZA
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    r = p.add_run(date.today().strftime("Inclusão e Alteração de Acessos · %d/%m/%Y"))
    r.font.size = Pt(11); r.font.color.rgb = CINZA
    doc.add_page_break()

    # ---- 1. SUMARIO EXECUTIVO ----
    h1(doc, "1. Sumário Executivo")
    par(doc, "O CVC IAM Analytics é a solução de governança de acessos (IAM) da CVC "
             "Corp. Ela processa as bases de RH e os extratos de acesso dos sistemas "
             "corporativos, cruza com as matrizes de perfis esperados por cargo e "
             "evidencia, por usuário, as divergências de acesso — apontando o que "
             "precisa ser incluído, alterado ou analisado.")
    par(doc, "Esta primeira entrega cobre o sistema SYSTUR no fluxo de Inclusão e "
             "Alteração de acessos. Ela já é a fundação multiusuário e multi-sistema "
             "sobre a qual as próximas fases (demais sistemas, desligados, "
             "transferidos e integração Jira) serão acopladas por configuração, sem "
             "retrabalho.")
    par(doc, "Princípio de leitura dos números: o sistema conta USUÁRIOS a tratar, "
             "não acessos. Um usuário com várias opções de perfil ou vários acessos "
             "conta como uma pessoa — o foco é \"quantas pessoas preciso tratar\".",
        italico=True, cor=NAVY)

    # ---- 2. ESCOPO ----
    h1(doc, "2. O que esta entrega contempla")
    h2(doc, "2.1. Sistema e bases")
    par(doc, "Escopo da Fase 1: sistema SYSTUR (Sistema de Turismo), fluxo de "
             "Inclusão/Alteração. O Processador consome quatro insumos:")
    tabela(doc,
           ["Insumo", "Conteúdo", "Pasta de entrada"],
           [["RH Ativos", "Funcionários ativos (matrícula, nome, cargo, centro de custo)", "ENTRADA/RH/ATIVOS"],
            ["Mapeamento CCO/CSC", "De-para organizacional (centro de custo × gestor)", "ENTRADA/MATRIZES/ORGANIZACIONAL"],
            ["Matriz SYSTUR", "Perfis esperados por cargo no SYSTUR", "ENTRADA/MATRIZES/PERFIS_SISTEMAS"],
            ["Extrato SYSTUR", "Acessos atuais dos usuários no SYSTUR", "ENTRADA/SISTEMAS/SYSTUR"]],
           larguras=[1.5, 3.2, 2.0])

    h2(doc, "2.2. O que o sistema identifica")
    par(doc, "Cada usuário é classificado pelo cruzamento entre o acesso atual e o "
             "perfil esperado para o cargo:")
    tabela(doc,
           ["Classificação", "Significado", "Ação"],
           [["Aderente", "O acesso bate com o perfil esperado", "Nenhuma (conforme)"],
            ["Incluir Acesso", "O cargo exige acesso que o usuário não tem", "Incluir o acesso"],
            ["Alterar Perfil", "O usuário tem acesso, mas com perfil divergente", "Ajustar o perfil"],
            ["Em Análise", "O cargo admite mais de um perfil possível", "Análise manual"],
            ["Não Mapeado", "Acesso de quem não está na base de RH ativa", "Investigar vínculo"]],
           larguras=[1.6, 3.4, 1.7])

    h2(doc, "2.3. Fora do escopo desta fase")
    par(doc, "Para manter a Fase 1 enxuta e sem ruído, ficam desativados por "
             "configuração (serão ligados nas fases seguintes):")
    bullet(doc, "revogação de acesso é um fluxo separado (fase de desligados).", neg="Desligados:")
    bullet(doc, "aguardam a definição da regra de espelho.", neg="Terceiros:")
    bullet(doc, "SIGOT, SICA RA, SICA ESFERA, IC, SIG, Oracle EBS, Opera entram nas próximas fases.", neg="Demais sistemas:")
    bullet(doc, "acesso a MAIS do que o cargo exige ainda não é sinalizado (em avaliação).", neg="Perfil excessivo:")

    # ---- 3. APLICATIVOS ----
    h1(doc, "3. Os dois aplicativos")
    tabela(doc,
           ["Aplicativo", "Para que serve", "Quem usa"],
           [["Processador.exe",
             "Lê as bases de ENTRADA, padroniza, cruza com as matrizes, grava o banco "
             "(iam_analytics.db) e consolida as interações. Roda sob demanda.",
             "Responsável pelo processamento"],
            ["visualizador.exe",
             "Abre o painel no navegador lendo o banco ao vivo. É onde o time acompanha "
             "e trata as pendências.",
             "Todos os usuários"]],
           larguras=[1.5, 4.0, 1.7])

    # ---- 4. ARQUITETURA ----
    h1(doc, "4. Arquitetura multiusuário")
    par(doc, "A base e os dados ficam em uma raiz de rede compartilhada. Vários "
             "usuários abrem o Visualizador ao mesmo tempo, com segurança:")
    bullet(doc, "o Processador grava o banco na rede; cada Visualizador copia o banco para um cache local no startup (mais rápido e sem ler durante a escrita).")
    bullet(doc, "as ações de cada usuário (quarentena, resolução) são gravadas em arquivos por usuário na pasta INTERACOES/ — seguro sobre rede.")
    bullet(doc, "a cada execução, o Processador consolida essas interações no banco.")
    bullet(doc, "os executáveis se auto-atualizam: comparam a versão local com a da rede e se copiam sozinhos quando há versão nova.")

    # ---- 5. COMO UTILIZAR ----
    h1(doc, "5. Como utilizar")

    h2(doc, "5.1. Estrutura de pastas")
    par(doc, "Ao extrair o pacote, esta é a estrutura. As pastas em destaque são as "
             "que você usa no dia a dia (ENTRADA para depositar, DADOS para os "
             "resultados):")
    code_block(doc,
        "CVC_IAM_ANALYTICS/\n"
        "├── ENTRADA/                      <- você COLOCA os arquivos aqui\n"
        "│   ├── RH/\n"
        "│   │   ├── ATIVOS/               <- base de RH (funcionários ativos)\n"
        "│   │   └── DESLIGADOS/           (próxima fase)\n"
        "│   ├── MATRIZES/\n"
        "│   │   ├── ORGANIZACIONAL/       <- Mapeamento CCO/CSC\n"
        "│   │   └── PERFIS_SISTEMAS/      <- matriz de perfil por cargo (SYSTUR)\n"
        "│   └── SISTEMAS/\n"
        "│       ├── SYSTUR/               <- extrato de acessos do SYSTUR\n"
        "│       ├── IC/ SIGOT/ SICA_RA/ ...   (próximas fases)\n"
        "├── DADOS/                        <- o sistema GERA os resultados aqui\n"
        "│   ├── BANCO/                    -> iam_analytics.db (gerado)\n"
        "│   ├── PROCESSADOS/              -> arquivos já importados\n"
        "│   ├── ERROS/                    -> arquivos rejeitados\n"
        "│   ├── SAIDAS/                   -> relatórios\n"
        "│   └── LOGS/                     -> logs de cada execução\n"
        "├── EXECUTAVEIS/                  <- Processador.exe, visualizador.exe,\n"
        "│                                    CONFIG/, REPORT/, launcher/\n"
        "└── INTERACOES/                   <- ações dos usuários (automático)")

    h2(doc, "5.2. Onde colocar cada arquivo")
    par(doc, "Para a Fase 1 (SYSTUR) são quatro arquivos. Cada um vai na sua pasta. "
             "Os importadores aceitam .xlsx e .csv. As colunas esperadas são "
             "configuráveis em EXECUTAVEIS/CONFIG/config.xml:")
    tabela(doc,
           ["Arquivo (exemplo)", "Pasta de destino", "Colunas esperadas"],
           [["Base de RH ativos\n(ex.: PROJETOIAM.csv)",
             "ENTRADA/RH/ATIVOS",
             "MATRICULA, NOME, CPF, CARGO_CODIGO, CARGO_DESCRICAO, DEPARTAMENTO, CENTRO_CUSTO, DATA_ADMISSAO, EMAIL, SITUACAO"],
            ["Mapeamento CCO/CSC\n(ex.: Mapeamento CCO_CSC.xlsx)",
             "ENTRADA/MATRIZES/ORGANIZACIONAL",
             "CARGO_CODIGO, CARGO_DESCRICAO, DEPARTAMENTO, CENTRO_CUSTO"],
            ["Matriz de perfil SYSTUR\n(ex.: MATRIZ DE PERFIL ... SYSTUR.xlsx)",
             "ENTRADA/MATRIZES/PERFIS_SISTEMAS",
             "CARGO_CODIGO, SISTEMA, PERFIL"],
            ["Extrato de acessos SYSTUR\n(ex.: relatorio systur.xlsx)",
             "ENTRADA/SISTEMAS/SYSTUR",
             "USUARIO, NOME, PERFIL, SITUACAO, DATA_CRIACAO, ULTIMO_ACESSO"]],
           larguras=[2.1, 2.0, 3.0])
    par(doc, "Dica: pode colocar mais de um arquivo na mesma pasta — o Processador lê "
             "todos. Após importar, cada arquivo é movido para uma subpasta "
             "PROCESSADOS dentro da própria pasta de origem.", italico=True, cor=CINZA)

    h2(doc, "5.3. Passo a passo")
    passos = [
        ("Preparar a rede (uma vez)",
         "Extrair o pacote e copiar a pasta CVC_IAM_ANALYTICS para a raiz de rede "
         "(ex.: Z:\\CVC\\). O banco nasce vazio."),
        ("Depositar os arquivos",
         "Colocar os quatro arquivos nas pastas de ENTRADA conforme a tabela 5.2."),
        ("Rodar o Processador",
         "Executar EXECUTAVEIS\\Processador.exe uma vez. Ao final: o banco "
         "iam_analytics.db é criado em DADOS/BANCO, os arquivos lidos vão para "
         "PROCESSADOS e o log fica em DADOS/LOGS. Arquivos com problema vão para ERROS."),
        ("Instalar o Visualizador em cada máquina",
         "Copiar a pasta EXECUTAVEIS para a máquina do usuário (ex.: C:\\CVC\\) e rodar "
         "o visualizador.exe de lá. Ele se auto-atualiza a partir da rede."),
        ("Abrir o painel",
         "O visualizador.exe abre o painel no navegador (http://127.0.0.1:8800/). "
         "Acompanhar e tratar as pendências pelas seis abas."),
        ("Atualizar o cenário",
         "Sempre que houver bases novas, repetir os passos 2 e 3 (depositar + "
         "Processador). Mudanças só no painel NÃO exigem reprocessar — basta "
         "reabrir/atualizar o Visualizador."),
    ]
    for i, (titulo, desc) in enumerate(passos, 1):
        p = doc.add_paragraph()
        r = p.add_run(f"Passo {i} — {titulo}. ")
        r.font.bold = True; r.font.size = Pt(10.5); r.font.color.rgb = NAVY
        r2 = p.add_run(desc); r2.font.size = Pt(10.5)

    # ---- 6. PAINEIS ----
    h1(doc, "6. Resumo dos painéis")
    par(doc, "O Visualizador tem seis abas:")
    tabela(doc,
           ["Aba", "O que mostra"],
           [["Visão Geral",
             "Dashboard operacional: KPIs por classificação (sempre por usuário), "
             "evolução de chamados (identificados × resolvidos × aderentes na janela "
             "de 30 dias), tempo de tratamento do ciclo (Pendência→Resolvido→Aderente) "
             "e movimentação de RH."],
            ["Consulta",
             "Busca por usuário (matrícula, nome, login, CPF) com a visão consolidada "
             "de acessos, pendências e atalhos para as demais abas."],
            ["Pendências",
             "Grid de tratamento: por usuário, os acessos a Incluir/Alterar/Analisar, "
             "com filtros, agrupamento e exportação Excel."],
            ["Aderentes",
             "Usuários conformes, com a trilha de datas do ciclo e o tempo total de "
             "tratamento."],
            ["Histórico",
             "Trilha de movimentações: admissões, alterações de RH e o ciclo de vida "
             "de cada acesso (pendência, resolução, aderência)."],
            ["Quarentena",
             "Acessos colocados em observação por prazo (90 dias), com acompanhamento "
             "do tempo restante."]],
           larguras=[1.4, 5.7])

    # ---- 7. FLUXO DE ATENDIMENTO ----
    h1(doc, "7. Fluxo de atendimento")
    par(doc, "Cada acesso pendente segue um ciclo de vida de três estágios, com "
             "registro de data em cada marco (a trilha fica no Histórico):")
    tabela(doc,
           ["Estágio", "Quando acontece"],
           [["1. Pendência", "O Processador identifica a divergência (Incluir/Alterar/Em Análise)."],
            ["2. Resolvido", "O analista trata o caso sob um ticket do Jira e marca como resolvido."],
            ["3. Aderente", "Em um próximo processamento, o acesso passa a bater com o esperado."]],
           larguras=[1.7, 5.4])
    par(doc, "Observações do fluxo:")
    bullet(doc, "a resolução é feita por usuário, sempre vinculada a um ticket do Jira (com descrição).")
    bullet(doc, "o tempo de tratamento é medido em cada etapa de forma independente (Pendência→Resolvido, Resolvido→Aderente e Pendência→Aderente), inclusive liberações feitas fora do sistema.")
    bullet(doc, "a quarentena permite colocar um acesso em observação por prazo antes de uma decisão definitiva.")
    bullet(doc, "toda exportação para Excel reflete exatamente a grid (mesmas colunas, valores e formatação), respeitando os filtros aplicados.")

    # ---- 8. ROADMAP ----
    h1(doc, "8. O que ainda será entregue (roadmap)")
    par(doc, "As próximas fases acoplam-se a esta fundação. Sequenciamento previsto:")
    tabela(doc,
           ["Fase / Card", "Entrega", "Janela"],
           [["Cards 8-13", "Demais sistemas: IC, SICA RA, SIGOT, Oracle EBS, SIG, SICA Esfera", "jun/2026"],
            ["Card 14", "Consolidação multi-sistema dos acessos", "jun/2026"],
            ["Cards 15-17", "Matrizes organizacionais e motor de divergências completo", "jul/2026"],
            ["Cards 19-21", "Motor de desligados (revogação) e auditoria", "jul/2026"],
            ["Cards 22-24", "Movimentações e revalidação pós-transferência", "jul-ago/2026"],
            ["Cards 25-26", "Integração Jira: abertura automática de chamados e fechamento", "ago/2026"]],
           larguras=[1.4, 4.3, 1.4])
    par(doc, "Quando um sistema entra, ele é ativado por configuração — o painel já é "
             "multi-sistema e não precisa de reescrita.", italico=True, cor=CINZA)

    # ---- 9. SUGESTOES ----
    h1(doc, "9. Sugestões e recomendações")
    par(doc, "Itens que recomendamos definir com o cliente para extrair mais valor da "
             "ferramenta e preparar as próximas fases:")
    bullet(doc, "definir a periodicidade de extração das bases e do processamento (ex.: mensal/quinzenal), para que os números reflitam um ciclo previsível.", neg="Periodicidade:")
    bullet(doc, "definir o responsável por tratar cada classificação (Incluir, Alterar, Analisar, Não Mapeado) e o prazo-alvo (SLA) de cada um.", neg="Responsáveis e SLA:")
    bullet(doc, "padronizar o uso do ticket do Jira na resolução (todo tratamento sob um chamado) — isso já prepara a automação dos Cards 25-26.", neg="Disciplina de ticket:")
    bullet(doc, "estabelecer o prazo e o critério de saída da quarentena (hoje 90 dias) e quem decide.", neg="Política de quarentena:")
    bullet(doc, "rotina de backup do iam_analytics.db (a base guarda o histórico e o ciclo de vida).", neg="Backup:")
    bullet(doc, "a trilha do Histórico serve como evidência para auditoria (SOX/LGPD); vale definir o período de retenção.", neg="Evidência para auditoria:")
    bullet(doc, "avaliar a sinalização de acesso excessivo (mais do que o cargo exige) — hoje fora de escopo, mas relevante para risco.", neg="Perfil excessivo:")
    bullet(doc, "revisar as matrizes de perfil por cargo periodicamente, já que elas definem o \"esperado\" — matriz desatualizada gera divergência falsa.", neg="Curadoria das matrizes:")
    bullet(doc, "a Visão Geral é um dashboard operacional; o enriquecimento (metas/SLA, tendências) será guiado pelo uso e pela fase Jira — sugestões do time são bem-vindas.", neg="Evolução da Visão Geral:")

    # ---- 10. GLOSSARIO ----
    h1(doc, "10. Glossário")
    tabela(doc,
           ["Termo", "Definição"],
           [["Aderente", "Usuário cujo acesso está conforme o perfil esperado."],
            ["Pendência", "Divergência identificada que precisa de tratamento."],
            ["Em Análise", "Cargo com mais de um perfil possível — exige decisão manual."],
            ["Não Mapeado", "Acesso de quem não está na base de RH ativa."],
            ["Quarentena", "Acesso colocado em observação por prazo antes da decisão."],
            ["Matriz de perfil", "Tabela que define o perfil esperado por cargo em cada sistema."],
            ["Mapeamento CCO/CSC", "De-para que liga centro de custo e gestor ao acesso esperado."]],
           larguras=[1.8, 5.3])

    par(doc, "")
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("CVC IAM Analytics · v1.0.0 · Documento de entrega — Fase 1 (SYSTUR)")
    r.font.size = Pt(8); r.font.color.rgb = CINZA

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(SAIDA)
    print(f"OK -> {SAIDA}")
    print(f"  {SAIDA.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    construir()
