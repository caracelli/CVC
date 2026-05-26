# -*- coding: utf-8 -*-
"""Gera docs/DOCUMENTACAO_PAINEL.docx com o conteudo do painel IAM Analytics.
Mesmo material do DOCUMENTACAO_PAINEL.md, formatado para Word.

Uso:
    pip install python-docx
    python scripts/gerar_doc_painel.py
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


OUT = Path(__file__).resolve().parent.parent / "docs" / "DOCUMENTACAO_PAINEL.docx"


COR_AZUL = RGBColor(0x1F, 0x2D, 0x5C)
COR_CINZA = RGBColor(0x5A, 0x64, 0x78)
COR_TEXTO = RGBColor(0x2C, 0x33, 0x40)


def shade(cell, hex_color):
    """Pinta o fundo de uma celula de tabela."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def h1(doc, texto):
    p = doc.add_heading(texto, level=1)
    for run in p.runs:
        run.font.color.rgb = COR_AZUL


def h2(doc, texto):
    p = doc.add_heading(texto, level=2)
    for run in p.runs:
        run.font.color.rgb = COR_AZUL


def h3(doc, texto):
    p = doc.add_heading(texto, level=3)
    for run in p.runs:
        run.font.color.rgb = COR_AZUL


def p(doc, texto, italic=False, bold=False):
    par = doc.add_paragraph()
    r = par.add_run(texto)
    r.italic = italic
    r.bold = bold
    r.font.size = Pt(10)
    r.font.color.rgb = COR_TEXTO
    return par


def tabela(doc, headers, rows, larguras_cm=None):
    """Cria tabela com header em azul + linhas alternadas."""
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.style = "Light Grid Accent 1"
    tbl.autofit = False
    hdr = tbl.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        par = hdr[i].paragraphs[0]
        r = par.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(9.5)
        shade(hdr[i], "1F2D5C")
        if larguras_cm and i < len(larguras_cm):
            hdr[i].width = Cm(larguras_cm[i])
    for ri, row in enumerate(rows):
        row_cells = tbl.add_row().cells
        for ci, val in enumerate(row):
            row_cells[ci].text = ""
            par = row_cells[ci].paragraphs[0]
            r = par.add_run(str(val))
            r.font.size = Pt(9)
            r.font.color.rgb = COR_TEXTO
            if ri % 2 == 1:
                shade(row_cells[ci], "F5F6FA")
            if larguras_cm and ci < len(larguras_cm):
                row_cells[ci].width = Cm(larguras_cm[ci])
    doc.add_paragraph()  # espaco
    return tbl


def main():
    doc = Document()

    # Margens
    for sec in doc.sections:
        sec.left_margin = Cm(2)
        sec.right_margin = Cm(2)
        sec.top_margin = Cm(2)
        sec.bottom_margin = Cm(2)

    # Capa
    titulo = doc.add_paragraph()
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = titulo.add_run("CVC IAM ANALYTICS")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = COR_AZUL
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Documentação do Painel")
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = COR_AZUL
    versao = doc.add_paragraph()
    versao.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = versao.add_run("Versão v2.0.1")
    r.italic = True
    r.font.size = Pt(11)
    r.font.color.rgb = COR_CINZA
    doc.add_paragraph()

    # 1. Visão geral
    h1(doc, "1. Visão geral do produto")
    p(doc,
      "O IAM Analytics confronta a base de RH da CVC com os extratos de "
      "acesso dos sistemas corporativos (SYSTUR na Fase 1; SIGOT, SICA RA, "
      "SICA Esfera, IC nas fases seguintes) e gera pendências de acesso "
      "quando há divergência entre o que o cargo do funcionário exige "
      "(matriz) e o que ele de fato possui.")
    p(doc,
      "O painel apresenta essas pendências em uma interface de "
      "governança — não edita o banco diretamente: ações do usuário "
      "(enviar para quarentena, resolver pendência sob ticket Jira) são "
      "registradas como interações que o Processador consolida na "
      "próxima execução.")

    # 2. Abas
    h1(doc, "2. Abas (navegação principal)")
    tabela(doc,
        ["Aba", "Função"],
        [
            ["Visão Geral", "KPIs e gráficos resumindo as pendências do "
                            "sistema em escopo."],
            ["Pendências", "Grade detalhada de todas as pendências "
                            "(uma linha por funcionário/usuário)."],
            ["Consulta", "(Em construção) Consulta livre por filtros."],
            ["Histórico", "Trilha de auditoria das resoluções de pendências."],
            ["Quarentena", "Funcionários em quarentena (ativos e finalizados)."],
        ],
        larguras_cm=[3.5, 13])
    p(doc, "Trocar de aba força a releitura do banco — a grid sempre "
           "reflete o estado mais recente.")

    # 3. Cabeçalho
    h1(doc, "3. Cabeçalho do painel")
    tabela(doc,
        ["Item", "Significado"],
        [
            ["Referência", "Mês/ano da data mais recente em "
                          "bi_divergencias.data_identificacao. Indica o "
                          "\"fechamento\" do cenário atualmente carregado."],
            ["Última atualização", "Mesma data acima, com hora — reflete "
                                   "quando o Processador rodou pela última vez."],
            ["Logo CVC", "Volta para a aba Visão Geral."],
        ],
        larguras_cm=[4, 12.5])

    # 4. Visão Geral
    h1(doc, "4. Aba Visão Geral")
    h2(doc, "KPIs (cards superiores)")
    p(doc, "Cinco cards no topo da página:")
    tabela(doc,
        ["Card", "O que conta", "Cor de barra"],
        [
            ["Incluir Acesso",
             "Funcionários sem o acesso que a matriz exige (status=SEM_ACESSO)",
             "Azul claro #2980B9"],
            ["Alterar Perfil",
             "Funcionários com perfil diferente do esperado "
             "(status=DIVERGENTE)",
             "Azul escuro #154360"],
            ["Em Análise",
             "Cargos com mais de um perfil possível na matriz "
             "(status=EM_ANALISE) — requer decisão humana",
             "Laranja #E67E22"],
            ["Total Não Mapeados",
             "Usuários no SYSTUR sem matrícula correspondente no RH ativo "
             "(tipo=ACESSO_SEM_VINCULO_RH)",
             "Roxo #7D3C98"],
            ["Total c/ Ação",
             "Soma dos quatro acima — pendências totais",
             "Verde #1E8449"],
        ],
        larguras_cm=[3.5, 9.5, 3.5])
    h2(doc, "Gráficos")
    tabela(doc,
        ["Gráfico", "O que mostra"],
        [
            ["Por Sistema", "Quantidade de pendências por sistema "
                            "(Fase 1: SYSTUR)."],
            ["Por Ação", "Distribuição dos quatro tipos de ação: "
                          "Incluir Acesso, Alterar Perfil, Em Análise, "
                          "Não Mapeado."],
        ],
        larguras_cm=[3.5, 13])

    # 5. Pendências
    h1(doc, "5. Aba Pendências")
    p(doc, "Grid principal. Cada linha é um funcionário ou usuário com "
           "uma ou mais pendências.")
    h2(doc, "Colunas da grid")
    tabela(doc,
        ["#", "Coluna", "Conteúdo", "Observações"],
        [
            ["1", "Quarentena", "Botão de ação (ícone)",
             "Envia o usuário para a aba Quarentena."],
            ["2", "(expandir)", "+ / −",
             "Expande detalhes quando há mais de uma pendência."],
            ["3", "Vínculo", "Funcionário ou Terceiro",
             "Hoje todos vêm como Funcionário; Terceiro entra com a "
             "integração da base de Terceiros (futura)."],
            ["4", "Usuário/Acesso", "Login do usuário no sistema",
             "Para Não Mapeado, é o identificador do SYSTUR (ex.: "
             "EXMP0001)."],
            ["5", "Qtd", "Número de pendências do usuário",
             "Maior que 1 → linha agrupada com expand."],
            ["6", "Nome", "Nome completo",
             "Vem do RH (Funcionário) ou do SYSTUR (Não Mapeado)."],
            ["7", "Matrícula", "Matrícula RH",
             "Vazia para Não Mapeado."],
            ["8", "Departamento", "Departamento do funcionário",
             "Vem da matriz organizacional (CCO)."],
            ["9", "Cargo", "Cargo do funcionário",
             "Vem da base RH."],
            ["10", "Tipo", "Badge com o tipo da pendência",
             "Ver tabela em \"Badges, cores e significados\"."],
            ["11", "Perfil Encontrado", "Perfil que o usuário TEM no sistema",
             "Vazio em Sem Acesso."],
            ["12", "Perfil Esperado", "Perfil que a matriz EXIGE",
             "Múltiplos separados por | em Em Análise."],
            ["13", "Data", "Quando a pendência foi identificada",
             "dd/mm/aaaa hh:mm:ss"],
            ["14", "Status", "Badge Pendente ou Resolvido",
             "Resolvido = quem já passou pelo fluxo de Resolução."],
            ["15", "Origem", "Matriz <SISTEMA> ou Matriz CCO ou —",
             "Indica de qual fonte veio o perfil esperado."],
        ],
        larguras_cm=[0.7, 3, 5, 7])

    h2(doc, "Ações nas linhas")
    tabela(doc,
        ["Ação", "Quando aparece", "O que faz"],
        [
            ["Lupa (🔍)", "Pendência já resolvida",
             "Abre modal com os dados da resolução (ticket Jira, "
             "descrição, quem resolveu)."],
            ["Botão ⊕ (Resolver)", "Pendência pendente",
             "Abre modal pra registrar a resolução sob ticket do Jira."],
            ["Botão Quarentena", "Sempre",
             "Envia o usuário para a aba Quarentena por 90 dias "
             "(configurável)."],
        ],
        larguras_cm=[4, 4, 8.5])

    h2(doc, "Filtros e ordenação na grid")
    p(doc, "• Clique no nome da coluna: ordena (clica de novo inverte).")
    p(doc, "• Funil (ao lado do nome): filtro de valores tipo Excel "
           "(caixinhas marcáveis, busca por valor).")
    p(doc, "• Filtros laterais: ver seção 9.")

    # 6. Quarentena
    h1(doc, "6. Aba Quarentena")
    p(doc, "Dois sub-modos, controlados pela barra de toolbar no topo "
           "da página: Ativas e Histórico.")
    h2(doc, "Ativas")
    tabela(doc,
        ["Coluna", "Significado"],
        [
            ["Usuário", "Login/matrícula"],
            ["Nome", "Nome do funcionário"],
            ["Sistema", "Sistema do acesso (SYSTUR)"],
            ["Origem", "\"Inclusão / Alteração\" (de onde veio)"],
            ["Data início", "Quando entrou na quarentena"],
            ["Data fim", "Quando sai automaticamente (início + 90 dias)"],
            ["Criado por", "Usuário do Windows que executou a ação"],
            ["Ação", "Botão Retirar da quarentena — encerra antes da data"],
        ],
        larguras_cm=[3.5, 13])
    h2(doc, "Histórico")
    p(doc, "Quarentenas encerradas. Colunas adicionais:")
    tabela(doc,
        ["Coluna", "Significado"],
        [
            ["Data saída", "Quando saiu da quarentena"],
            ["Motivo", "\"Resolvido\" (saiu por ação manual)"],
            ["Encerrado por", "Quem retirou"],
        ],
        larguras_cm=[3.5, 13])

    # 7. Histórico
    h1(doc, "7. Aba Histórico")
    p(doc, "Trilha de auditoria das resoluções de pendências. Cada "
           "resolução gera DUAS linhas:")
    tabela(doc,
        ["Movimentação", "Significado"],
        [
            ["Pendência identificada",
             "Quando a divergência apareceu pela primeira vez "
             "(MIN(data_identificacao) em bi_divergencias da matrícula)."],
            ["Pendência resolvida",
             "Quando o usuário registrou a resolução sob ticket Jira "
             "(resolucoes.resolvido_em)."],
        ],
        larguras_cm=[5, 11.5])
    p(doc, "Regra de coerência: Pendência resolvida é sempre posterior "
           "a Pendência identificada.", italic=True)
    h2(doc, "Colunas")
    tabela(doc,
        ["Coluna", "Conteúdo"],
        [
            ["(expandir)", "Mostra detalhes adicionais quando agrupado "
                            "por funcionário"],
            ["Matrícula", "Matrícula do funcionário"],
            ["Nome", "Nome completo"],
            ["Movimentação", "Pendência identificada ou Pendência "
                              "resolvida (badge colorido)"],
            ["Data", "Data do evento"],
            ["Detalhe", "Ticket Jira (resolvida) ou \"ver detalhes\" "
                        "(lupa para abrir modal completo)"],
        ],
        larguras_cm=[3.5, 13])
    h2(doc, "Badges de movimentação")
    tabela(doc,
        ["Badge", "Cor", "Significado"],
        [
            ["Pendência identificada", "Cinza",
             "Linha que abre a trilha."],
            ["Pendência resolvida", "Verde",
             "Fecha a trilha sob ticket Jira."],
            ["Admitido (reservado)", "Azul",
             "Movimentação cadastral RH (atualmente não exibida)."],
            ["Alterado (reservado)", "Amarelo",
             "Movimentação cadastral RH (atualmente não exibida)."],
        ],
        larguras_cm=[4.5, 2.5, 9.5])
    p(doc, "Botão Exportar Excel exporta o histórico com a mesma "
           "estrutura (agrupamentos por funcionário, mesma formatação "
           "visual da grid).")

    # 8. Consulta
    h1(doc, "8. Aba Consulta")
    p(doc, "Em construção. Será uma grade de consulta livre com filtros "
           "adicionais. Os filtros serão definidos junto com o cliente.")

    # 9. Filtros laterais
    h1(doc, "9. Filtros laterais")
    p(doc, "Painel lateral esquerdo (todas as abas exceto Consulta). "
           "Funciona em conjunto com a grid atual. Cinco filtros "
           "independentes:")
    tabela(doc,
        ["Filtro", "Valores possíveis"],
        [
            ["Vínculo", "Funcionário, Terceiro"],
            ["Ação", "Incluir Acesso, Alterar Perfil, Em Análise, "
                      "Não Mapeado"],
            ["Status", "Pendente, Resolvido"],
            ["Tipo", "Sem Acesso, Divergente, Em Análise, Sem Vínculo RH"],
            ["Sistema", "SYSTUR (Fase 1); outros nas fases seguintes"],
        ],
        larguras_cm=[3, 13.5])
    h2(doc, "Comportamento dos filtros")
    p(doc, "\"Clique isola o valor · Ctrl+clique combina\"", italic=True)
    p(doc, "• Clique simples: filtra só por esse valor, descarta os outros.")
    p(doc, "• Ctrl+clique: adiciona/remove o valor da seleção atual "
           "(multi-seleção).")
    p(doc, "• Sem nada marcado: tudo é mostrado.")

    # 10. Tooltips
    h1(doc, "10. Tooltips (textos do ícone (i))")
    p(doc, "Aparecem nos filtros laterais e nos cards de pendência "
           "(modais). Passar o mouse sobre o (i) exibe o texto:")
    h2(doc, "Ação")
    tabela(doc,
        ["Valor", "Tooltip"],
        [
            ["Incluir Acesso",
             "Funcionário sem o acesso que a matriz do cargo exige — "
             "precisa incluir o perfil."],
            ["Alterar Perfil",
             "Funcionário com perfil diferente do permitido para o cargo — "
             "precisa alterar."],
            ["Em Análise",
             "O cargo tem mais de um perfil possível na matriz — requer "
             "análise manual."],
            ["Não Mapeado",
             "Acesso no sistema sem funcionário correspondente na base "
             "de RH ativa."],
        ],
        larguras_cm=[3.5, 13])
    h2(doc, "Tipo (mesma classificação, rótulo usado na grid)")
    tabela(doc,
        ["Valor", "Tooltip"],
        [
            ["Sem Acesso",
             "Funcionário sem o acesso que a matriz do cargo exige — "
             "precisa incluir o perfil."],
            ["Divergente",
             "Funcionário com perfil diferente do permitido para o cargo — "
             "precisa alterar."],
            ["Sem Vínculo RH",
             "Acesso no sistema sem funcionário correspondente na base "
             "de RH ativa."],
        ],
        larguras_cm=[3.5, 13])
    h2(doc, "Status")
    tabela(doc,
        ["Valor", "Tooltip"],
        [
            ["Pendente", "Pendência ainda não tratada."],
            ["Resolvido", "Pendência já tratada e resolvida."],
        ],
        larguras_cm=[3.5, 13])

    # 11. Badges
    h1(doc, "11. Badges, cores e significados")
    h2(doc, "Badges de Tipo (coluna Tipo da grid Pendências)")
    tabela(doc,
        ["Badge", "Cor", "Origem na base"],
        [
            ["Sem Acesso", "Azul claro",
             "bi_divergencias.tipo='SEM_ACESSO'"],
            ["Divergente", "Azul escuro",
             "bi_divergencias.tipo='DIVERGENTE'"],
            ["Em Análise", "Laranja",
             "bi_divergencias.tipo='EM_ANALISE'"],
            ["Sem Vínculo RH", "Roxo",
             "bi_divergencias.tipo='ACESSO_SEM_VINCULO_RH'"],
        ],
        larguras_cm=[3.5, 3.5, 9.5])
    h2(doc, "Badges de Status")
    tabela(doc,
        ["Badge", "Cor", "Origem"],
        [
            ["Pendente", "Amarelo", "Calculado: ainda sem resolução"],
            ["Resolvido", "Verde",
             "Há registro em resolucoes para a matrícula"],
        ],
        larguras_cm=[3.5, 3.5, 9.5])

    # 12. Modais
    h1(doc, "12. Modais")
    h2(doc, "Modal \"Resolver pendência(s)\"")
    p(doc, "Abre ao clicar no botão ⊕ (Resolver) em uma linha pendente.")
    tabela(doc,
        ["Campo", "Obrigatório", "Descrição"],
        [
            ["N° do ticket do Jira", "Sim",
             "Ex.: IAM-1234. Formato livre; ideal seguir o padrão "
             "Jira da CVC."],
            ["Link do ticket", "Não",
             "URL completo do ticket (ex.: "
             "https://jira.cvc.com.br/browse/IAM-1234)."],
            ["Descrição", "Não",
             "Observações sobre como/por que foi resolvido. Até 600 "
             "caracteres."],
        ],
        larguras_cm=[4, 2.5, 10])
    p(doc, "Ao confirmar: grava uma interação RESOLUCAO na rede "
           "(arquivo .jsonl em INTERACOES/). Na próxima execução do "
           "Processador, a interação é consolidada (dobrada) na tabela "
           "resolucoes e a matrícula passa a aparecer como Resolvido na "
           "grid.")
    h2(doc, "Modal \"Detalhes da resolução\" (lupa)")
    p(doc, "Abre ao clicar na lupa (🔍) de uma linha já resolvida ou em "
           "\"ver detalhes\" no Histórico. Mostra:")
    p(doc, "• Cargo e Centro de Custo na época da resolução.")
    p(doc, "• Lista de pendências resolvidas (tipo, perfil encontrado → esperado).")
    p(doc, "• Ticket Jira (com link) + descrição.")
    p(doc, "• Quem resolveu (usuário do Windows) e quando.")
    h2(doc, "Modal \"Detalhe da pendência\" (no Histórico)")
    p(doc, "Aberto pelo botão \"ver detalhes\" na coluna Detalhe do "
           "Histórico quando a movimentação é Pendência identificada. "
           "Mostra a divergência original, antes da resolução.")

    # 13. Glossário
    h1(doc, "13. Glossário")
    tabela(doc,
        ["Termo", "Significado"],
        [
            ["Pendência", "Diferença entre o que o cargo exige (matriz) "
                          "e o acesso real do funcionário no sistema."],
            ["Matriz", "Mapa cargo → perfil(is) esperado(s) por sistema. "
                       "Mantida pela CVC e importada pelo Processador."],
            ["Matriz CCO", "Override por centro de custo — quando um CC "
                            "específico tem perfil próprio, sobrepondo a "
                            "matriz de cargo."],
            ["Cargo", "Função RH do funcionário, com código (ex.: AB001) "
                       "e descrição (ex.: ANALISTA FISCAL PL)."],
            ["Centro de Custo (CC)", "Estrutura organizacional, formato "
                                     "XX.XX.XX.XX."],
            ["Vínculo", "Funcionário (CLT, na base RH) ou Terceiro "
                         "(futura integração com base de terceiros)."],
            ["Quarentena", "Estado \"em espera\" antes de ação definitiva. "
                            "Funcionário em quarentena permanece 90 dias "
                            "(configurável) antes de auto-encerrar."],
            ["Resolução", "Ação manual de marcar uma pendência como "
                           "tratada, sob ticket do Jira. Vai pro Histórico, "
                           "sai das Pendências ativas."],
            ["Interação", "Registro de uma ação do usuário (envio para "
                           "quarentena, resolução, retirada). Gravado em "
                           ".jsonl na rede; consolidado no banco pelo "
                           "Processador."],
            ["Auto-update", "Mecanismo do visualizador.exe que compara "
                             "<versao> local vs rede e baixa atualizações "
                             "automaticamente."],
            ["bi_divergencias", "Tabela snapshot consolidada que alimenta "
                                 "o painel (combina validações + "
                                 "divergências)."],
            ["resolucoes", "Tabela com as resoluções já confirmadas "
                            "(sob ticket Jira)."],
            ["INTERACOES/", "Pasta na rede com os .jsonl por usuário (um "
                             "arquivo por USERNAME do Windows)."],
        ],
        larguras_cm=[3.5, 13])

    # Anexo
    h1(doc, "Anexo — Mapeamento status → ação (lógica do Processador)")
    tabela(doc,
        ["Cenário", "bi_divergencias.tipo", "Ação (no painel)", "Como aparece"],
        [
            ["Funcionário sem perfil no sistema", "SEM_ACESSO",
             "Incluir Acesso", "Card azul claro"],
            ["Funcionário com perfil errado", "DIVERGENTE",
             "Alterar Perfil", "Card azul escuro"],
            ["Cargo com 2+ perfis possíveis", "EM_ANALISE",
             "Em Análise", "Card laranja"],
            ["Usuário no SYSTUR sem matrícula", "ACESSO_SEM_VINCULO_RH",
             "Não Mapeado", "Card roxo"],
            ["Funcionário desligado com acesso",
             "(em divergencias, tipo ACESSO_DESLIGADO)",
             "(visão futura)", "(ainda não no painel)"],
        ],
        larguras_cm=[4.5, 4, 3.5, 4.5])

    # Rodape
    doc.add_paragraph()
    foot = doc.add_paragraph()
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = foot.add_run("Documento gerado automaticamente — referente à "
                      "versão v2.0.1 do sistema.")
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = COR_CINZA

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"OK -> {OUT}  ({OUT.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
