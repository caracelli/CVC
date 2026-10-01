# -*- coding: utf-8 -*-
"""Gera ENTREGA/ROTEIRO_AJUSTES_CVC_IAM_2026-10-01.docx (+ .md).

Responde o documento "ajuste_01_10.docx" (retorno da Bruna), validado
visualmente pelo usuario em 01/10:
  1. CCO e' uma regra a parte: quem e' da CCO segue so' a CCO (sem matriz por
     cargo), e perfis que a funcao preve nao sao "mais de um perfil".
  2. Exportacao da Consulta: Pendencias e Status iguais aos da tela.

Mesma formatacao dos roteiros de 24, 28 e 29/09.

Uso:  python scripts/gerar_roteiro_ajustes_2026_10_01.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_roteiro_ajustes as base  # noqa: E402

from docx import Document  # noqa: E402
from docx.shared import Pt, Cm  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402

h1, par, nota = base.h1, base.par, base.nota
AZUL, CINZA, TEXTO = base.AZUL, base.CINZA, base.TEXTO
_MD = base._MD
MEDIDO = "Medido na sua base (a do pacote de 29/09, reprocessada com esta versão)"

RAIZ = Path(__file__).resolve().parent.parent
OUT_DOCX = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-10-01.docx"
OUT_MD = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-10-01.md"

CASOS = [
    ('14389', 'TATIANE DA SILVA LEMES', 'N2 - Financeiro',
     'SYSTUR em análise por “mais de um perfil”: tem PARAMETROS_DE_CAIXA, N2_FINANCEIRO, os dois previstos pela função.',
     'SYSTUR aderente pela função N2 - Financeiro, sem o alerta.'),
    ('15250', 'ADRIANNE RODRIGUES', 'Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, MARITIMO_CONC, os dois previstos pela função.',
     'SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.'),
    ('2061', 'ANDREIA REIS TEIXEIRA', 'Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, MARITIMO_CONC, os dois previstos pela função.',
     'SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.'),
    ('23217', 'ROBERTO FERREIRA DOS SANTOS', 'Sup Financeiro - Caixa',
     'SYSTUR em análise por “mais de um perfil”: tem PARAMETROS_DE_CAIXA, CCO_SUPORTE_DE_CAIXA_SUP_FIN, os dois previstos pela função.',
     'SYSTUR aderente pela função Sup Financeiro - Caixa, sem o alerta.'),
    ('2324', 'SEBASTIAO CLAUDIO DE ANDRADE', 'Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, ASS_CONC_BILHETES_RECIBOS_B2C_I, os dois previstos pela função.',
     'SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.'),
    ('32446', 'GRAZIELLI CARRILHO ANDRADE', 'Gerencia Operações',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COVID_VOADO_NAO_REMOVER, GER_OPER, os dois previstos pela função.',
     'SYSTUR aderente pela função Gerencia Operações, sem o alerta.'),
    ('34531737', 'THAYS MORAES PEREIRA DA SILVA', 'Apoio Canais criticos',
     'SYSTUR em análise por “mais de um perfil”: tem APOIO_CCRITICOS, CANAIS_CRITICOS, os dois previstos pela função.',
     'SYSTUR aderente pela função Apoio Canais criticos, sem o alerta.'),
    ('34532400', 'KATIA SUELI VIEIRA DIAS', 'A Receber 1 Comissão',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, A_RECEBER_1_COMISSAO, os dois previstos pela função.',
     'SYSTUR aderente pela função A Receber 1 Comissão, sem o alerta.'),
    ('6506', 'CRISTIANE VARELA GOMES', 'SUPERVISÃO',
     'SYSTUR em análise por “mais de um perfil”: tem CANAIS_CRITICOS, SUPERV_OPER_CCRITICOS, os dois previstos pela função.',
     'SYSTUR aderente pela função SUPERVISÃO, sem o alerta.'),
    ('7496', 'MIRIAM ARAUJO DE MOURA', 'Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, ASS_CONC_BILHETES_RECIBOS_B2C_I, os dois previstos pela função.',
     'SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.'),
    ('7530', 'ADILSON LUIS BRUGNARO', 'Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, ASS_CONC_BILHETES_RECIBOS_B2C_I, os dois previstos pela função.',
     'SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.'),
    ('90001050', 'MARCIO ALENCAR CARVALHO', 'Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, ASS_CONC_BILHETES_RECIBOS_B2C_I, os dois previstos pela função.',
     'SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.'),
    ('90001187', 'MARIA EDUARDA CRESPO FARIAS', 'A Receber 1 Comissão',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, A_RECEBER_1_COMISSAO, os dois previstos pela função.',
     'SYSTUR aderente pela função A Receber 1 Comissão, sem o alerta.'),
    ('90001406', 'ANA PAULA DE OLIVEIRA CARDAMONE', 'A Receber 1 Comissão',
     'SYSTUR em análise: a matriz do cargo pedia CUSTOS ou TESOURARIA; tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, A_RECEBER_1_COMISSAO.',
     'SYSTUR aderente pela função A Receber 1 Comissão, sem o alerta.'),
    ('90001433', 'CLAUDIA DA LUZ SALIDO RIVERO', 'Atendimento a fornecedores TREND N2',
     'SYSTUR em análise: a matriz do cargo pedia CUSTOS ou TESOURARIA; tem ATD_FOR_TREND_N2.',
     'SYSTUR aderente pela função Atendimento a fornecedores TREND N2, sem o alerta.'),
    ('9910', 'ALINE DA SILVA NASCIMENTO OLIVARES', 'A Receber 1 Comissão',
     'SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, A_RECEBER_1_COMISSAO, os dois previstos pela função.',
     'SYSTUR aderente pela função A Receber 1 Comissão, sem o alerta.'),
]


def regra(*a, **kw):
    kw.setdefault("rot_medido", MEDIDO)
    return base.regra(*a, **kw)


def lista(doc, itens):
    for txt in itens:
        p = doc.add_paragraph(txt, style="List Bullet")
        for r_ in p.runs:
            r_.font.size = Pt(9.5)
            r_.font.color.rgb = TEXTO
        _MD.append(f"- {txt}")
    _MD.append("")


def bloco(doc, titulo, linhas):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(titulo)
    r.bold = True
    r.font.size = Pt(10)
    r.font.color.rgb = AZUL
    _MD.append(f"\n**{titulo}**\n")
    tbl = doc.add_table(rows=0, cols=2)
    tbl.style = "Table Grid"
    for rot, val in linhas + [("Confere? Se não, o que deveria ser?", "")]:
        cells = tbl.add_row().cells
        cells[0].width = Cm(4.2)
        cells[1].width = Cm(12.3)
        r0 = cells[0].paragraphs[0].add_run(rot)
        r0.bold = True
        r0.font.size = Pt(8.5)
        r0.font.color.rgb = CINZA if rot.startswith("Confere") else AZUL
        r1 = cells[1].paragraphs[0].add_run(val)
        r1.font.size = Pt(8.5)
        r1.font.color.rgb = TEXTO
        _MD.append(f"- **{rot}:** {val}")
    _MD.append("")


def main():
    _MD.clear()
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = t.add_run("CVC IAM Analytics")
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = AZUL
    s = doc.add_paragraph()
    r = s.add_run("Roteiro de validação — seu documento de 01/10")
    r.font.size = Pt(13)
    r.font.color.rgb = CINZA
    par(doc, "01/10/2026", size=9, cor=CINZA, md=False)
    _MD.insert(0, "# CVC IAM Analytics\n"
                  "## Roteiro de validação — seu documento de 01/10\n"
                  "01/10/2026\n")

    doc.add_paragraph()
    par(doc, "Por que este documento existe", bold=True, size=11, cor=AZUL, space=2)
    par(doc,
        "Ele responde os dois pontos do seu documento de 01/10 (ajuste_01_10): o "
        "SYSTUR de quem é da CCO e a extração em Excel. Traz o antes e o depois "
        "de cada caso para você conferir.")
    nota(doc,
         "Este pacote substitui o de 29/09 e já inclui todos os ajustes dele. Ele "
         "traz a pasta DADOS com o banco processado: você NÃO precisa rodar o "
         "Processador.")

    doc.add_page_break()
    h1(doc, "Antes de tudo: o que fazer, nesta ordem")
    lista(doc, [
        "1. Feche o painel e o Processador, se estiverem abertos.",
        "2. BACKUP (obrigatório): copie as pastas DADOS\\BANCO e INTERACOES "
        "para outro lugar. Se algo não sair como esperado, é só devolvê-las.",
        "3. Extraia o pacote na pasta principal da instalação — a que contém "
        "DADOS, ENTRADA e EXECUTAVEIS — e aceite substituir os arquivos.",
        "4. NÃO apague nem mexa na pasta INTERACOES: é onde ficam as suas "
        "tratativas, e o painel as lê ao vivo.",
        "5. Abra o visualizador.exe.",
    ])

    doc.add_page_break()
    h1(doc, "1. CCO é uma regra à parte")
    regra(doc, "1", "Quem é da CCO segue só o que a CCO prevê",
          prioritaria=True,
          decide="O que vale para quem é da CCO: a CCO ou a matriz do cargo.",
          criterio="Como combinamos: o que está na CCO é o que a pessoa pode ter. "
                   "Quem é da CCO não recebe nada da matriz por cargo nem passa "
                   "pela regra Oracle × SYSTUR. Os perfis que a função prevê não "
                   "contam como “mais de um perfil” — a pessoa pode ter dois ou "
                   "mais, se estiverem na função. É da CCO quem está no centro de "
                   "custo + gestor da CCO e tem perfil (SYSTUR, SICA RA, SICA "
                   "ESFERA ou SIGOT) de uma função dessa equipe — ou não tem perfil "
                   "nenhum nesses sistemas. Assim os vice-presidentes da "
                   "Presidência, que dividem o centro de custo com o diretor da "
                   "CCO, continuam pela matriz do cargo.",
          conferir="Consulta → ANA PAULA DE OLIVEIRA CARDAMONE (90001406) → aba "
                   "Acessos. ANTES: SYSTUR em “Necessário análise” com “Usuário com "
                   "mais de um perfil (2)” e “Esperado: 1 de 2 opções: CUSTOS, "
                   "TESOURARIA”; a função A Receber 1 Comissão sem o SYSTUR.",
          esperado="DEPOIS: SYSTUR em “Acessos encontrados”, em verde, com "
                   "GRP_COMISSOES_IMPORTACAO_ARQUIVOS e A_RECEBER_1_COMISSAO, sem "
                   "alerta. Em “Funções previstas”, A Receber 1 Comissão — “tem 9 "
                   "de 11”, com o SYSTUR dentro (faltam SICA ESFERA e SICA RA). Na "
                   "base: 16 pessoas saem de pendência no SYSTUR.")

    par(doc, "Os 16 casos que mudaram", bold=True, size=10.5, cor=AZUL, space=2)
    for m, nome, fun, antes, depois in CASOS:
        bloco(doc, f"{m} — {nome}   ·   função {fun}",
              [("Antes (pacote de 29/09)", antes), ("Depois (este pacote)", depois)])
    par(doc, "Dois casos que mudam de motivo", bold=True, size=10.5, cor=AZUL, space=2)
    par(doc,
        "ELAINE ALVES MELKUNAS (33082) e SILMAR PERPETUO DA SILVA (34530333) estão "
        "no centro de custo + gestor de uma equipe da CCO, mas os perfis delas são "
        "de função de outra equipe. Por isso não contam como CCO dessa equipe e "
        "seguem a regra geral: continuam pendentes, agora como “tem acesso sem "
        "previsão” em vez de “acesso fora da função”.", size=9.5)

    doc.add_page_break()
    h1(doc, "2. A planilha da Consulta igual à tela")
    regra(doc, "2", "Pendências e Status da planilha = os do painel",
          prioritaria=True,
          decide="O que sai nas colunas Pendências e Status ao exportar a Consulta.",
          criterio="A planilha contava de outro jeito: “Pendências” levava o total "
                   "de linhas da pessoa e “Status” chamava de pendente o que é só "
                   "“incluir acesso” e de aderente o que é “sem mapeamento”. Agora "
                   "usa a mesma regra da tela, na linha da pessoa e na de cada "
                   "sistema. Conferido na base inteira: 7.433 pessoas, nenhuma "
                   "diferença entre planilha e tela. A exportação da aba "
                   "Pendências continua trazendo só o que é pendência — e nenhuma "
                   "pendência fica de fora dela.",
          conferir="Consulta → LETICIA THAIS SABIAO SOUZA (9130) → Exportar Excel → "
                   "Analítico. ANTES: SICA_RA “1 pendente” e ORACLE_EBS “Aderente”, "
                   "com a tela dizendo Pendências 0.",
          esperado="DEPOIS: pessoa com Pendências 0 e “Incluir acessos”; ORACLE_EBS "
                   "“Sem mapeamento” (CVC OIE BRASIL - Relatório de Despesas); "
                   "SICA_RA “Incluir acessos” (SVA PRODUTOS); SYSTUR “Aderente”.")

    doc.add_page_break()
    h1(doc, "3. O que vai parecer diferente")
    lista(doc, [
        "As pendências caem de 1.064 para 1.048 pessoas (de 1.108 para 1.089 "
        "linhas): são os SYSTUR da CCO que deixam de ser “mais de um perfil”.",
        "Nenhum número da tela muda por causa da planilha: ela passa a repetir o "
        "que a tela já mostrava.",
    ])

    h1(doc, "4. Duas perguntas para você")
    par(doc,
        "4.1 No documento, o nome da usuária do ponto da extração ficou em branco. "
        "O print da planilha é da LILIANE BENTO ALEXANDRE (4374), que tem só o SIG "
        "pendente e não tem Oracle; o do painel é da LETICIA THAIS SABIAO SOUZA "
        "(9130). Era uma delas, ou outra pessoa?", size=9.5)
    par(doc, "Sua resposta: ______________________________________________",
        size=9.5, cor=CINZA)
    par(doc,
        "4.2 O Oracle de quem a matriz não cobre (como o Relatório de Despesas da "
        "LETICIA) hoje é informativo — “sem mapeamento”, como você pediu em 23/09. "
        "Deve passar a contar como pendência? Na base, são cerca de 280 pessoas.",
        size=9.5)
    par(doc, "Sua resposta: ______________________________________________",
        size=9.5, cor=CINZA)

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_DOCX)
    OUT_MD.write_text("\n".join(_MD), encoding="utf-8")
    print(f"gerado: {OUT_DOCX}")
    print(f"gerado: {OUT_MD}")


if __name__ == "__main__":
    main()
