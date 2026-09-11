# -*- coding: utf-8 -*-
"""Gera ENTREGA/ROTEIRO_AJUSTES_CVC_IAM_2026-09-11.docx (+ .md).

Responde, item a item, o retorno de teste da Bruna de 09/09 ("Testes 2.pdf")
e registra o que mudou desde o roteiro de 08/09. Reaproveita a formatacao do
gerador de 08/09 (scripts/gerar_roteiro_ajustes.py) para os dois documentos
terem a mesma cara.

OS NUMEROS AQUI SAO DA BASE DELA. Diferente do roteiro de 08/09, que so' tinha
a nossa base de referencia: o zip do pacote de 08/09 trouxe o banco e a ENTRADA
dela, e ela foi reprocessada aqui com o codigo novo (10-11/09). Ainda assim
cada linha diz se o valor e' INVARIANTE ou MEDIDO — a ENTRADA dela pode ter
mudado desde 08/09.

Uso:  python scripts/gerar_roteiro_ajustes_2026_09_11.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_roteiro_ajustes as base  # noqa: E402  (mesma formatacao do de 08/09)

from docx import Document  # noqa: E402
from docx.shared import Pt, RGBColor  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402

h1, par, nota, shade = base.h1, base.par, base.nota, base.shade
MEDIDO_AQUI = "Medido na sua base (reprocessada aqui com a versão nova)"


def regra(*a, **kw):
    """Os numeros deste roteiro sao da base DELA — o rotulo padrao do de 08/09
    ("base de referencia") estaria errado aqui."""
    kw.setdefault("rot_medido", MEDIDO_AQUI)
    return base.regra(*a, **kw)



AZUL, CINZA, TEXTO, VERMELHO = base.AZUL, base.CINZA, base.TEXTO, base.VERMELHO
_MD = base._MD

RAIZ = Path(__file__).resolve().parent.parent
OUT_DOCX = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-09-11.docx"
OUT_MD = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-09-11.md"


def resposta(doc, pergunta, texto):
    """Pergunta dela (em destaque) seguida da resposta."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(f"“{pergunta}”")
    r.italic = True; r.bold = True
    r.font.size = Pt(10); r.font.color.rgb = AZUL
    _MD.append(f"\n**“{pergunta}”**\n")
    par(doc, texto, size=9.5)


def lista(doc, itens):
    for txt in itens:
        p = doc.add_paragraph(txt, style="List Bullet")
        for r_ in p.runs:
            r_.font.size = Pt(9.5); r_.font.color.rgb = TEXTO
        _MD.append(f"- {txt}")
    _MD.append("")


def main():
    _MD.clear()
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    # ------------------------------------------------------------ capa
    t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = t.add_run("CVC IAM Analytics"); r.bold = True
    r.font.size = Pt(20); r.font.color.rgb = AZUL
    s = doc.add_paragraph()
    r = s.add_run("Roteiro de validação — respostas ao seu teste de 09/09")
    r.font.size = Pt(13); r.font.color.rgb = CINZA
    par(doc, "Pacote UPDATE_BRUNA_v1.0.0  ·  11/09/2026", size=9, cor=CINZA, md=False)
    _MD.insert(0, "# CVC IAM Analytics\n"
                  "## Roteiro de validação — respostas ao seu teste de 09/09\n"
                  "Pacote UPDATE_BRUNA_v1.0.0 · 11/09/2026\n")

    doc.add_paragraph()
    par(doc, "Por que este documento existe", bold=True, size=11, cor=AZUL, space=2)
    par(doc,
        "Ele responde, ponto a ponto, o documento de testes que você mandou em "
        "09/09 (“Testes 2”). Cinco pontos viraram correção no painel e três eram "
        "dúvidas de funcionamento, que estão respondidas aqui. No caminho "
        "entraram mais dois ajustes, também descritos.")
    par(doc, "Como usar", bold=True, size=11, cor=AZUL, space=2)
    par(doc,
        "Igual ao roteiro de 08/09: cada ajuste tem “Como conferir” e o valor "
        "esperado, e a última linha pergunta se a regra está CERTA. As marcadas "
        "com ★ são as que mais aparecem na tela.")
    nota(doc,
         "Os números “medidos” deste documento vêm da SUA base: o pacote de 08/09 "
         "trouxe o banco e os arquivos de entrada da sua máquina, e reprocessamos "
         "aqui com a versão nova. Se você depositou arquivos novos depois de "
         "08/09, os seus números podem diferir um pouco.")

    # ------------------------------------------------------------ antes de tudo
    doc.add_page_break()
    h1(doc, "Antes de tudo: o que fazer, nesta ordem")
    par(doc,
        "O mesmo procedimento de 08/09. O passo 3 continua obrigatório: as "
        "correções agem na fase de ANÁLISE, e sem rodar o Processador a tela "
        "continua com os números da rodada anterior.")
    passos = [
        ("1.", "Feche o painel e o Processador, se estiverem abertos."),
        ("2.", "Extraia o pacote e copie EXECUTAVEIS/ por cima da pasta atual. "
               "NÃO apague nem mexa em DADOS/ e INTERACOES/ — é onde ficam o "
               "banco e as tratativas que você já registrou."),
        ("2b.", "Copie também a pasta ENTRADA/ do pacote por cima da atual. Ela "
                "leva só os dois arquivos de referência de sempre (o de-para do "
                "SIG e a matriz do franqueado). Nenhum dado seu é substituído."),
        ("3.", "Rode o Processador.exe UMA VEZ. Obrigatório."),
        ("4.", "Abra o visualizador.exe."),
    ]
    for num, txt in passos:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(f"{num}  "); r.bold = True
        r.font.size = Pt(10.5); r.font.color.rgb = AZUL
        r2 = p.add_run(txt); r2.font.size = Pt(9.5); r2.font.color.rgb = TEXTO
        _MD.append(f"{num} {txt}")

    # ------------------------------------------------------------ 1 correcoes
    doc.add_page_break()
    h1(doc, "1. O que você apontou e foi corrigido")

    regra(doc, "1.1", "Colaborador ativo que não aparecia na Consulta",
          "Se todo colaborador ativo aparece na Consulta.",
          "Quem não tem nenhum acesso esperado relevante para o cargo (a matriz "
          "não prevê nada, ou prevê sistemas que quase ninguém do cargo usa — o "
          "limiar de 30%) ficava sem nenhuma linha e sumia da tela inteira. "
          "Agora aparece na Consulta com a situação “Sem Expectativa”: é "
          "informativo, NÃO entra em Pendências nem nos contadores.",
          "Consulta → busque WILIAN MANOEL DE OLIVEIRA, AURELINA DE SOUZA SANTOS "
          "CAMILO ou qualquer outro nome da sua lista.",
          "19 dos 21 nomes da lista passam a aparecer. Os ativos sem nenhuma "
          "linha no painel caem de 6.747 para 6.194 — o restante é explicado "
          "na nota abaixo.",
          tipo_esperado="MEDIDO", prioritaria=True)
    nota(doc,
         "Os três nomes que continuam de fora têm motivo próprio. PRISCILA SANTOS "
         "DE LIMA não está na sua base de ativos (há uma JAQUELINE PRISCILA "
         "OLIVEIRA DE LIMA, que é outra pessoa) — vale conferir de onde veio o "
         "nome. LEONARDO COELHO PALADINO e ANA PAULA DE BARROS BRAGA SOARES eram "
         "aderentes no SYSTUR em 01/07 e hoje não têm nenhum acesso ativo: a "
         "regra temporária de “provável desligamento” os tira da tela até a "
         "fase de desligados. Dos demais que seguem fora, a grande maioria são "
         "franqueados e prestadores sem acesso nenhum, pelas regras já "
         "combinadas (roteiro de 08/09, item 1.1, e roteiro de 06/08, item "
         "2.6); o restante são outros casos da mesma regra de provável "
         "desligamento.")

    regra(doc, "1.2", "SYSTUR na Consulta com a mesma leitura da Pendências",
          "Como aparece o acesso que casa com mais de um perfil do cargo.",
          "No SYSTUR a pessoa só pode ter UM perfil. Quando o perfil dela não "
          "bate com nenhum dos que o cargo permite, a Consulta listava cada "
          "perfil possível como uma linha — lia como “faltam 5”. Agora é uma "
          "linha só, como na Pendências: “Tem hoje: X · Esperado: 1 de N "
          "opções”. O contador de pendências da pessoa conta esse acesso uma vez.",
          "Consulta → uma pessoa com “Em Análise” no SYSTUR → “ver detalhe”.",
          "12 pessoas nessa situação (SYSTUR, SIGOT e Oracle EBS), que somavam "
          "42 linhas e agora são 12 — uma por acesso.",
          tipo_esperado="MEDIDO", prioritaria=True)

    regra(doc, "1.3", "“Acessos iguais” vindo como Em Análise",
          "Quando o perfil da pessoa e o dos colegas são o mesmo escrito diferente.",
          "A comparação com os colegas (usada para terceiro e prestador) era "
          "letra a letra: “gestao de acessos” e “GESTAO DE ACESSOS” contavam "
          "como perfis diferentes. Agora ignora maiúscula, acento e espaço. A "
          "tela continua mostrando cada perfil como está escrito no extrato.",
          "Consulta → CAROLINA MOTA SANTOS DE JESUS → SICA_RA.",
          "O SICA_RA dela sai como Aderente. Era a única linha nesse caso "
          "(Em Análise do espelho de prestador: 26 → 25).",
          tipo_esperado="MEDIDO")

    regra(doc, "1.4", "Trocar de aba perdia os dados",
          "O que a aba mostra quando a leitura dos dados falha.",
          "Quando a leitura de uma aba falhava uma vez, o painel guardava o erro "
          "como se fosse a resposta, e a aba ficava vazia em toda volta até "
          "fechar e abrir de novo. Agora o erro não é guardado — a próxima "
          "visita lê de novo. Se ainda assim falhar, a aba DIZ que falhou, em "
          "vez de mostrar a lista vazia com o contador antigo em cima.",
          "Navegue entre as abas várias vezes, principalmente Transferidos.",
          "Nunca “Nenhuma transferência detectada” com o contador preenchido "
          "(era o seu print: “69 a revisar” sobre uma lista vazia). Em falha, "
          "a mensagem “Não foi possível carregar os transferidos”.",
          prioritaria=True)

    regra(doc, "1.5", "O que é o “D” na Consulta",
          "O selo D da coluna Abas.",
          "D quer dizer que a matrícula consta na base de DESLIGADOS — não que "
          "haja algo a remover. Quem consta como desligado mas não tem nenhum "
          "acesso ativo é “OK”: nada a fazer. Por isso você filtrava e não "
          "achava nada. Agora o botão diz qual é o caso ao passar o mouse, e "
          "fica apagado quando não há nada a remover.",
          "Consulta → passe o mouse sobre um “D”.",
          "D apagado = desligado sem acesso ativo (nada a remover). D normal = "
          "acesso ativo a revogar, ou já encaminhado para tratamento.")

    # ------------------------------------------------------------ 2 duvidas
    doc.add_page_break()
    h1(doc, "2. Suas dúvidas de funcionamento")

    resposta(doc,
             "Se eu tratar um caso que não muda o perfil na próxima atualização "
             "da base, o que se espera?",
             "A tratativa não se perde e não expira. Na próxima atualização, se "
             "o caso vier IGUAL (mesma pessoa, mesmo sistema, mesmo perfil), ele "
             "continua como Resolvido. Se o perfil encontrado MUDAR, é um caso "
             "novo: aparece como Pendente, e a tratativa anterior fica "
             "registrada no histórico.")
    nota(doc,
         "Um cuidado: a tratativa dada para a PESSOA inteira ou para um SISTEMA "
         "inteiro vale para o escopo todo — se aparecer uma pendência nova "
         "nesse escopo, ela também sai como Resolvido. Tratar pelo acesso "
         "específico evita isso. Separar os ciclos de tratativa ao longo do "
         "tempo está previsto para a fase de integração com o Jira.")
    resposta(doc,
             "O usuário com perfil básico que pode não estar mapeado na matriz — "
             "como ele se comporta?",
             "Se o cargo não tem nenhum acesso esperado, ele aparece na Consulta "
             "como “Sem Expectativa” (item 1.1): é informativo e nunca vira "
             "pendência. Se o cargo tem expectativa e o perfil dele não é o "
             "previsto, ele aparece como Alterar Perfil ou Em Análise; tratado, "
             "segue a regra acima.")

    regra(doc, "2.1", "Tratativa por sistema ou por acesso entra no Histórico",
          "Se toda tratativa aparece no Histórico e no tempo médio.",
          "Achado ao revisar a sua dúvida. A tratativa pode ser dada para a "
          "pessoa inteira, para um sistema ou para um acesso. Só a primeira "
          "chegava ao Histórico e ao tempo médio da Visão Geral; as outras duas "
          "apareciam Resolvido na Pendências e não entravam lá. Agora as três "
          "entram.",
          "Trate uma pendência só de um sistema → rode o Processador → "
          "Histórico da pessoa.",
          "O marco “Pendência resolvida” aparece no sistema tratado, com o "
          "ticket e a data da tratativa.")

    resposta(doc,
             "O transferido apaga o histórico do que ele já trouxe? Fica "
             "pendente até ser tratado?",
             "A lista de Transferidos é refeita a cada carga (compara a base de "
             "RH nova com a anterior), mas nada se perde: a movimentação e a "
             "tratativa ficam registradas. Sim, a pessoa fica em “A Revisar” até "
             "ser tratada.")
    resposta(doc,
             "Se eu der a tratativa, ele encerra o ciclo? Ou, se o perfil ficar "
             "inaderente, ele vem nas pendências?",
             "As duas coisas, porque são verificações separadas. A tratativa "
             "encerra o caso na aba Transferidos. Já a Pendências olha o perfil: "
             "se o acesso continuar fora do esperado para a função nova, ele "
             "aparece lá — e é resolvido lá.")
    resposta(doc,
             "O transferido pode, já no primeiro apontamento, aparecer nas duas "
             "guias?",
             "Sim, é esperado. A aba Transferidos mostra que a pessoa mudou de "
             "função; a Pendências mostra se o acesso dela está certo para a "
             "função nova. Tratar em uma não resolve a outra.")
    nota(doc,
         "Um cuidado na aba Transferidos: a tratativa é registrada pela "
         "matrícula. Se a mesma pessoa for transferida de novo mais adiante, ela "
         "aparece como já tratada — vale conferir o de → para antes de "
         "considerar o caso encerrado.")

    # ------------------------------------------------------------ 3 preparacao
    doc.add_page_break()
    h1(doc, "3. Preparado para os próximos arquivos")

    regra(doc, "3.1", "SICA no mesmo modelo do SICA_RA",
          "Como os extratos de SICA que ainda não chegaram serão lidos.",
          "Confirmado que os demais arquivos de SICA virão no mesmo modelo do "
          "SICA_RA de 01/09. O SICA_ESFERA já está preparado para esse modelo, "
          "sem deixar de ler o relatório que você manda hoje — lido nos dois "
          "arquivos reais (24/06 e 15/08), o resultado é idêntico ao de antes.",
          "Quando depositar o arquivo novo: painel → “Arquivos importados”.",
          "A data do arquivo novo aparece, e a quantidade de acessos não é "
          "zero. Se vier zero, me avise — é o sinal de layout diferente do "
          "esperado.")

    # ------------------------------------------------------------ 4 perguntas
    doc.add_page_break()
    h1(doc, "4. As perguntas do roteiro de 08/09")
    resposta(doc, "3 de 3 — Qual extrato do SYSTUR está na sua ENTRADA?",
             "Respondida pela sua própria base: é o formato novo "
             "(view_systur_08_09_2026_07-00.csv), com a coluna de status. Nada "
             "a trocar.")
    par(doc,
        "Seguem em aberto as outras duas. Com o extrato novo, os franqueados "
        "que ficam em Em Análise são, na sua base, principalmente os perfis de "
        "exceção da pergunta 1 (199 linhas) — é ela que mais mexe na fila.",
        size=9.5)

    # ------------------------------------------------------------ 5 resumo
    doc.add_page_break()
    h1(doc, "5. Resumo para devolver")
    par(doc,
        "As duas perguntas em aberto e, abaixo, o que discordar. O que não for "
        "citado fica entendido como aprovado.")
    for num, txt in [
        ("1", "Os perfis de exceção (FRANQUEADOS_VC, GERENTE_GERAL_MASTER, "
              "MASTER_FRANQUEADO) têm aprovação da Governança de SI?"),
        ("2", "As 11 equivalências de cargo derivadas do uso estão corretas?"),
    ]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(f"{num}.  "); r.bold = True
        r.font.size = Pt(10.5); r.font.color.rgb = AZUL
        r2 = p.add_run(txt); r2.font.size = Pt(9.5); r2.font.color.rgb = TEXTO
        _MD.append(f"{num}. {txt}")

    par(doc, "", space=6, md=False)
    tbl = doc.add_table(rows=1, cols=3)
    tbl.style = "Table Grid"
    for i, titulo in enumerate(("Item", "O que está errado", "O que deveria ser")):
        r_ = tbl.rows[0].cells[i].paragraphs[0].add_run(titulo)
        r_.bold = True; r_.font.size = Pt(9)
        r_.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(tbl.rows[0].cells[i], "1F2D5C")
    for _ in range(6):
        tbl.add_row()
    _MD.append("\n| Item | O que está errado | O que deveria ser |\n"
               "|---|---|---|\n| | | |\n| | | |\n| | | |\n")

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_DOCX)
    OUT_MD.write_text("\n".join(_MD), encoding="utf-8")
    print(f"OK -> {OUT_DOCX}  ({OUT_DOCX.stat().st_size/1024:.0f} KB)")
    print(f"OK -> {OUT_MD}  ({OUT_MD.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
