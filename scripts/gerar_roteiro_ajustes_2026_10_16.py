# -*- coding: utf-8 -*-
"""Gera ENTREGA/ROTEIRO_AJUSTES_CVC_IAM_2026-10-16.docx (+ .md).

Atualizacao de 16/10 (pacote versao 1.0.4): ajustes aprovados pela Bruna no
mockup de 16/10. Mesma formatacao dos roteiros anteriores.

Uso:  python scripts/gerar_roteiro_ajustes_2026_10_16.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_roteiro_ajustes as base  # noqa: E402

from docx import Document  # noqa: E402
from docx.shared import Pt  # noqa: E402

h1, par = base.h1, base.par
AZUL, CINZA, TEXTO = base.AZUL, base.CINZA, base.TEXTO
_MD = base._MD

RAIZ = Path(__file__).resolve().parent.parent
OUT_DOCX = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-10-16.docx"
OUT_MD = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-10-16.md"


def lista(doc, itens, estilo="List Number"):
    for txt in itens:
        p = doc.add_paragraph(txt, style=estilo)
        for r_ in p.runs:
            r_.font.size = Pt(9.5)
            r_.font.color.rgb = TEXTO
        _MD.append(f"- {txt}")
    _MD.append("")


def main():
    _MD.clear()
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    t = doc.add_paragraph()
    r = t.add_run("CVC IAM Analytics")
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = AZUL
    s = doc.add_paragraph()
    r = s.add_run("Atualização de 16/10 — ajustes aprovados (versão mantida em 1.0.3)")
    r.font.size = Pt(13)
    r.font.color.rgb = CINZA
    par(doc, "16/10/2026", size=9, cor=CINZA, md=False)
    _MD.insert(0, "# CVC IAM Analytics\n## Atualização de 16/10 — ajustes aprovados "
                  "(versão mantida em 1.0.3)\n16/10/2026\n")

    h1(doc, "1. O que muda")
    par(doc, "Ajustes aprovados no mockup de 16/10 (MOCKUP_PAINEL_AJUSTES_2026-10-16.html).")
    lista(doc, [
        "Contas de robô e sistêmicas (login SIST…) nunca ficam vinculadas a uma pessoa: vão "
        "sempre para Pendências como “Usuário Não Encontrado”, para análise e quarentena. Antes, "
        "o robô cadastrado com o e-mail de quem o criou virava acesso dessa pessoa. A categoria "
        "“Contas de serviço” da aba Desligados passa a ficar vazia.",
        "Conta com e-mail de uma pessoa, mas CPF e nome de outra, deixa de ser atribuída a ela "
        "(caso ALEXANDRA, 90000266: o PERFIL_CONSULTA do SYSTUR era do robô “VISUAL TURISMO”). "
        "Nome abreviado continua valendo (ex.: “FELIPPE SATO”).",
        "Quem está na CCO é validado só pela CCO, inclusive no Oracle EBS: o que a função prevê "
        "e a pessoa não tem passa a ser “Incluir” (antes: “não tem mapeado na matriz”). Caso "
        "CLAUDIA, 90001433; na base de 09/10 são 52 pessoas.",
        "Transferidos: o perfil “CVC OIE BRASIL - Relatório de Despesas” é desconsiderado, como "
        "já era na validação. No detalhe e no Excel ele aparece como “desconsiderado (perfil "
        "padrão)”.",
        "Resolver pendência: com mais de uma pendência, o painel lista cada uma para escolher "
        "(nenhuma vem marcada; “marcar todas” resolve tudo de uma vez, como antes).",
        "Motivo do “Resolver pendência”: só “Acesso Indevido”.",
        "Layout: as barras de botões das abas Transferidos, Desligados, Quarentena e Consulta "
        "não quebram mais em telas menores.",
    ], estilo="List Bullet")

    h1(doc, "2. Reprocessar a rede (manual)")
    par(doc,
        "A versão continua 1.0.3, a mesma da rede: nenhuma máquina se atualiza sozinha. O "
        "reprocessamento é feito à mão, por uma pessoa, com a EXECUTAVEIS deste pacote.")
    lista(doc, [
        "Feche o Processador em todas as máquinas (o painel pode continuar aberto).",
        "Extraia a pasta EXECUTAVEIS do zip numa pasta LOCAL (ex.: C:\\CVC_IAM_1016\\EXECUTAVEIS). "
        "O Processador não abre direto da pasta de rede: rodado de lá, ele mostra um aviso e "
        "não processa.",
        "Abra o Processador.exe dessa pasta local. Ele lê e grava os dados da rede, como sempre. "
        "Espere “Processamento finalizado”.",
        "Nos painéis abertos, clique em Atualizar para carregar a base nova.",
    ])
    par(doc,
        "O reprocessamento é necessário: a vinculação dos robôs, a regra da CCO no Oracle e o "
        "perfil padrão nos Transferidos são calculados pelo Processador.", size=9.5)
    par(doc,
        "Os painéis das máquinas continuam na versão atual até a próxima atualização de versão. "
        "Eles já mostram os dados novos: robôs em Pendências, a ALEXANDRA aderente e o EBS da "
        "CLAUDIA como inclusão. As mudanças de tela (escolher a pendência no Resolver, motivo só "
        "“Acesso Indevido”, o “Relatório de Despesas” marcado como desconsiderado e o layout das "
        "barras) aparecem quando o painel novo for instalado. Para ver tudo agora numa máquina, "
        "abra o visualizador.exe da mesma pasta local.", size=9.5)

    h1(doc, "3. O que conferir")
    lista(doc, [
        "Pendências: as contas SIST… aparecem como “Usuário Não Encontrado”.",
        "Consulta da ALEXANDRA (90000266): SYSTUR aderente, só com B2B_PROJETOS.",
        "Consulta da CLAUDIA (90001433): ORACLE_EBS em “Acessos esperados” com os 8 perfis.",
        "Transferidos: o “Relatório de Despesas” não aparece no resumo do Oracle.",
        "Resolver pendência de quem tem pendência em mais de um sistema: a lista para escolher; "
        "motivo só “Acesso Indevido”.",
    ], estilo="List Bullet")

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_DOCX)
    OUT_MD.write_text("\n".join(_MD), encoding="utf-8")
    print(f"gerado: {OUT_DOCX}")
    print(f"gerado: {OUT_MD}")


if __name__ == "__main__":
    main()
