# -*- coding: utf-8 -*-
"""Gera ENTREGA/ROTEIRO_AJUSTES_CVC_IAM_2026-10-08.docx (+ .md).

Responde o documento "Aplicacao_CVC_07_10 1.docx" (retorno da Bruna em 07/10)
e o que achamos na base da REDE (DADOS.zip e ENTRADAs.zip de 08/10).

OS NUMEROS SAO DA REDE: o banco que estava na rede em 08/10 ("antes") e a
simulacao da proxima execucao com esta versao ("depois") — mesmo banco, os
extratos pendentes de 07 e 08/10 e os 3 arquivos que foram para ERROS em 06/10.

Mesma formatacao dos roteiros anteriores.

Uso:  python scripts/gerar_roteiro_ajustes_2026_10_08.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_roteiro_ajustes as base  # noqa: E402

from docx import Document  # noqa: E402
from docx.shared import Pt  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402

h1, par, nota = base.h1, base.par, base.nota
AZUL, CINZA, TEXTO = base.AZUL, base.CINZA, base.TEXTO
_MD = base._MD
MEDIDO = "Medido na base da rede (próxima execução, com esta versão)"

RAIZ = Path(__file__).resolve().parent.parent
OUT_DOCX = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-10-08.docx"
OUT_MD = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-10-08.md"


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


def pergunta(doc, titulo, texto):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(titulo)
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = AZUL
    _MD.append(f"\n### {titulo}\n")
    par(doc, texto, size=9.5)
    par(doc, "Sua resposta: ______________________________________________",
        size=9.5, cor=CINZA)


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
    r = s.add_run("Roteiro de validação — seu documento de 07/10")
    r.font.size = Pt(13)
    r.font.color.rgb = CINZA
    par(doc, "08/10/2026", size=9, cor=CINZA, md=False)
    _MD.insert(0, "# CVC IAM Analytics\n"
                  "## Roteiro de validação — seu documento de 07/10\n"
                  "08/10/2026\n")

    doc.add_paragraph()
    par(doc, "Por que este documento existe", bold=True, size=11, cor=AZUL, space=2)
    par(doc,
        "Ele responde o seu documento de 07/10 (Aplicação_CVC_07_10) e explica o "
        "que encontramos na base da rede. Parte dos casos que você apontou "
        "(CLAUDIA, franqueados em espelho) não era regra: eram arquivos que não "
        "chegaram a ser processados na rede. Isso está no item 1.")

    doc.add_page_break()
    h1(doc, "1. O que aconteceu na rede")
    par(doc,
        "No dia 06/10, às 13:37, rodou na rede uma versão ANTIGA do Processador "
        "(de junho), de alguma instalação velha que ainda aponta para a rede. Ela "
        "durou um minuto, mas mandou para DADOS\\ERROS o extrato do SYSTUR de 06/10 "
        "e a matriz de lojas (franqueados), e parou com erro. As execuções "
        "seguintes, com a versão correta, terminaram — mas sem esses dois "
        "arquivos. Além disso, a matriz da CCO enviada em 05/10 veio sem a linha "
        "de título e era rejeitada pelo programa; isso foi corrigido nesta versão.")
    lista(doc, [
        "Sem a matriz nova da CCO, quem é da CCO e mudou de gestor (como a "
        "CLAUDIA) ficava fora da CCO e caía na matriz do cargo.",
        "Sem a matriz de lojas, os franqueados eram comparados pelo espelho.",
        "Recomendação: apagar instalações antigas do programa nas máquinas que "
        "acessam a rede.",
    ])

    doc.add_page_break()
    h1(doc, "2. Os ajustes desta versão")

    regra(doc, "2.1", "Oracle: o Relatório de Despesas é desconsiderado",
          prioritaria=True,
          decide="Se o perfil CVC OIE BRASIL - RELATÓRIO DE DESPESAS conta na "
                 "validação do Oracle.",
          criterio="Seu pedido: desconsiderar o perfil. Ele sai inteiro da "
                   "validação: não é mais “a mais”, nem “não pode ter e tem”, nem "
                   "“mais de um perfil”. O extrato continua igual.",
          conferir="Consulta → GILDA TAVARES DA SILVA (34530435) e LETICIA THAIS "
                   "SABIAO SOUZA (9130) → Oracle EBS.",
          esperado="GILDA: Oracle aderente (o único “a mais” era o Relatório). "
                   "LETICIA: sem linha de Oracle. Na rede: 377 acessos "
                   "desconsiderados; as pendências de Oracle dos funcionários caem "
                   "de 350 para 1.")

    regra(doc, "2.2", "A matriz da CCO volta a ser lida",
          prioritaria=True,
          decide="Se a matriz da CCO sem linha de título é aceita.",
          criterio="A matriz de 05/10 tem o cabeçalho na primeira linha; a anterior "
                   "tinha um título antes. O programa agora aceita as duas.",
          conferir="Consulta → CLAUDIA DA LUZ SALIDO RIVERO (90001433).",
          esperado="SYSTUR, SIG e SIGOT aderentes pela CCO (gestora HELEN ANTONIA "
                   "LA SPINA RUAS) — sem TESOURARIA/CUSTOS e sem pendência. Na "
                   "rede: as pendências de SYSTUR dos funcionários caem de 211 "
                   "para 48.")

    regra(doc, "2.3", "Franqueados: matriz de lojas, não espelho",
          prioritaria=True,
          decide="Como os franqueados são validados no SYSTUR.",
          criterio="Seu pedido: usar a matriz do SYSTUR de lojas. Ela passou a ser "
                   "lida. Agora cada franqueado é comparado com o que a matriz "
                   "prevê para o cargo, o tipo de atendimento e o tipo de loja.",
          conferir="Aba Pendências → filtre Categoria = Franqueado.",
          esperado="Origem “Matriz franqueado” em vez de “Espelho — franqueados”. "
                   "Na rede: 4.855 linhas pela matriz (eram 774 pelo espelho) e "
                   "522 franqueados com pendência — 317 com perfil que o cargo não "
                   "autoriza (ex.: Atendente com perfil de Supervisor) e 192 com "
                   "perfil que a matriz só libera com aprovação da Governança "
                   "(ex.: Gerente com FRANQUEADOS_VC). Ver a pergunta 4.1.")

    regra(doc, "2.4", "Transferidos sem linhas repetidas",
          decide="Como a aba Transferidos mostra os sistemas de quem é da CCO.",
          criterio="A planilha da CCO escreve “Sigot”, “Systur”, “Oracle EBS”; os "
                   "acessos usam SIGOT, SYSTUR, ORACLE_EBS. O mesmo sistema saía "
                   "em duas linhas, e o que a CCO prevê nunca casava com o que a "
                   "pessoa tem (falta e sobrou falsos). Os nomes agora são "
                   "unificados.",
          conferir="Aba Transferidos → ELAINE ALVES MELKUNAS (33082).",
          esperado="Uma linha por sistema; SIGOT e SYSTUR com “tem”, sem as linhas "
                   "“Sigot” e “Systur” de inclusão.")

    regra(doc, "2.5", "Quarentena com motivo",
          decide="O que se informa ao enviar para quarentena.",
          criterio="Seu pedido: um campo Motivo com Exceção, Férias/Cobertura de "
                   "férias e Usuário sistêmico. É obrigatório; o texto livre "
                   "virou “Detalhe (opcional)”.",
          conferir="Qualquer pendência → Enviar para quarentena.",
          esperado="Campo Motivo com as 3 opções; sem escolher, a quarentena não é "
                   "enviada. No histórico aparece “Opção — detalhe”.")

    doc.add_page_break()
    h1(doc, "3. Respostas às suas perguntas")
    par(doc, "ALEXANDRA RODRIGUES DE LIMA DIAS (90000266) — de onde vem o 2º perfil",
        bold=True, size=10, cor=AZUL)
    par(doc,
        "Vem do login SIST00207, que no SYSTUR tem o nome “VISUAL TURISMO” e outro "
        "CPF, mas está cadastrado com o e-mail dela (alexandra.dias@cvccorp.com.br). "
        "O programa liga a conta à pessoa pelo e-mail — por isso não aparece quando "
        "o extrato é filtrado pelo nome dela. Ver a pergunta 4.2.", size=9.5)
    par(doc, "Tratado, mas não regularizado: volta a apontar?", bold=True, size=10,
        cor=AZUL)
    par(doc,
        "Volta. Se, no processamento seguinte, o acesso continua divergente, a "
        "pendência reaparece marcada como REABERTA (como no seu primeiro print).",
        size=9.5)
    par(doc, "Pode ter e não tem / tem e não pode ter", bold=True, size=10, cor=AZUL)
    par(doc,
        "É a regra aplicada: o que a matriz prevê e a pessoa não tem aparece em "
        "“Acessos esperados” (não é pendência); o que a pessoa tem e não pode ter é "
        "pendência. O caso da GILDA era o Relatório de Despesas (item 2.1).",
        size=9.5)
    par(doc, "Dá para simular cenários (quarentena vencendo, transferido tratado "
        "errado, base manipulada)?", bold=True, size=10, cor=AZUL)
    par(doc,
        "Dá. Montamos bases de teste com esses cenários e mostramos o resultado "
        "antes de cada entrega.", size=9.5)

    doc.add_page_break()
    h1(doc, "4. Perguntas para você")
    pergunta(doc, "4.1 Franqueados com perfil que só a Governança libera",
             "Na matriz de lojas, a coluna ACESSO MANUAL = SIM marca perfis que só "
             "podem ser liberados com aprovação. Hoje isso vira pendência (192 "
             "franqueados). Deve continuar como pendência, ou ser só informativo?")
    pergunta(doc, "4.2 Conta genérica cadastrada com o e-mail de uma pessoa",
             "Caso da ALEXANDRA: a conta “VISUAL TURISMO” (outro CPF) usa o e-mail "
             "dela e foi ligada a ela. Deve continuar ligada à pessoa, ou contas "
             "com CPF diferente não devem ser ligadas pelo e-mail? (Ou tratar como "
             "usuário sistêmico na quarentena.)")
    pergunta(doc, "4.3 Itens do seu documento que precisam de conversa",
             "Transferidos (não pendente enquanto em transferidos, data da "
             "identificação, volta à fila depois do tratamento); “deixar apenas em "
             "tratativa do analista” na resolução; escolher qual pendência está "
             "sendo tratada; CCO com perfis de funções diferentes. Podemos marcar "
             "uma conversa para fechar esses pontos?")

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_DOCX)
    OUT_MD.write_text("\n".join(_MD), encoding="utf-8")
    print(f"gerado: {OUT_DOCX}")
    print(f"gerado: {OUT_MD}")


if __name__ == "__main__":
    main()
