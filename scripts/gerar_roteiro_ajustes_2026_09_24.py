# -*- coding: utf-8 -*-
"""Gera ENTREGA/ROTEIRO_AJUSTES_CVC_IAM_2026-09-24.docx (+ .md).

Responde os OITO pontos do documento "Aplicação_2_09.pdf" (o retorno de 22/09,
9 paginas), o documento "Sistema_24_09 1.docx" (retorno de 24/09) e os ajustes
validados pelo usuario na tarde de 24/09, e avisa o que muda na tela.

Regerado na tarde de 24/09 (commits e5b7241, 481ce82, bb84d84): a versao da
manha dizia que a BRENDA virou pendencia — deixou de ser, porque quem e' da
CCO saiu da regra Oracle x SYSTUR. A Bruna nao tinha recebido a da manha.

Mesma formatacao dos roteiros de 08, 11 e 18/09.

OS NUMEROS SAO DA BASE DELA: o DADOS.zip de 15/09 reprocessado aqui com o
codigo desta entrega (scratchpad/reprocessar.py, RC 0), comparado contra a
mesma base processada com a versao que ela tem hoje.

Uso:  python scripts/gerar_roteiro_ajustes_2026_09_24.py
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
MEDIDO = "Medido na sua base (a de 15/09, reprocessada aqui com esta versão)"

RAIZ = Path(__file__).resolve().parent.parent
OUT_DOCX = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-09-24.docx"
OUT_MD = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-09-24.md"


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

    # ------------------------------------------------------------- capa
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = t.add_run("CVC IAM Analytics")
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = AZUL
    s = doc.add_paragraph()
    r = s.add_run("Roteiro de validação — seus documentos de 22/09 e 24/09")
    r.font.size = Pt(13)
    r.font.color.rgb = CINZA
    par(doc, "24/09/2026", size=9, cor=CINZA, md=False)
    _MD.insert(0, "# CVC IAM Analytics\n"
                  "## Roteiro de validação — seus documentos de 22/09 e 24/09\n"
                  "24/09/2026\n")

    doc.add_paragraph()
    par(doc, "Por que este documento existe", bold=True, size=11, cor=AZUL, space=2)
    par(doc,
        "Ele responde, um a um, os oito pontos do seu documento de 22/09 — as "
        "nove páginas, incluindo as que eram só imagem — e os do seu documento "
        "de 24/09 (Sistema_24_09). Cada item diz o que mudou, como conferir e o "
        "valor esperado na sua base.")
    par(doc, "Leia primeiro: o número de linhas DIMINUI", bold=True, size=11,
        cor=AZUL, space=2)
    par(doc,
        "Esta entrega tira da tela acessos que não deveriam estar lá, então o "
        "total cai de 14.176 para 12.310 linhas. Isso é o efeito pretendido: "
        "boa parte dessas linhas vinha de uma FUNÇÃO que não é a da pessoa (o "
        "ponto que você levantou no SIG). As pendências, ao contrário, SOBEM — "
        "de 1.151 para 1.278 pessoas —, porque passamos a cobrar casos que "
        "antes passavam batidos.")
    nota(doc,
         "O pacote já traz a pasta DADOS com o banco processado: você NÃO "
         "precisa rodar o Processador. Se rodar, tudo bem — mas deixe as "
         "matrizes na pasta ENTRADA, porque a regra do Oracle depende de uma "
         "coluna que só entra quando a matriz é importada de novo.")

    # ------------------------------------------------- antes de tudo
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

    # ------------------------------------------------- os 8 pontos
    doc.add_page_break()
    h1(doc, "1. Os oito pontos do seu documento de 22/09")

    regra(doc, "1.1", "Os acessos que a matriz prevê voltaram a aparecer",
          prioritaria=True,
          decide="Quais acessos “a incluir” a aplicação mostra.",
          criterio="Havia um corte que escondia a inclusão quando poucas "
                   "pessoas do mesmo cargo tinham aquele acesso. Ele nasceu "
                   "para não inundar a fila de pendências — mas em 29/07 você "
                   "pediu que “sem acesso” saísse das pendências e ficasse só "
                   "na Consulta. Desde então o corte só escondia informação. "
                   "Foi desligado: agora vem 100% do que a matriz mapeia.",
          conferir="Consulta → busque MARCELO DE CASTRO DIAS (1303) → “ver "
                   "detalhe” → aba Acessos.",
          esperado="SYSTUR aparece com ATEND_AGENCIA_LJP_PROMOTORES_VC, que é "
                   "o perfil da linha que você circulou na matriz. Antes ele "
                   "vinha com “Sem registros de acesso” e os 7 sistemas em "
                   "“Sem mapeamento”.")

    regra(doc, "1.2", "O SICA Esfera voltou a trazer o perfil sugerido",
          decide="O acesso esperado de quem é coberto pelo Mapeamento CCO.",
          criterio="Mesma causa do item anterior.",
          conferir="Consulta → CAMILA DOS SANTOS TENORIO MARQUES (32696).",
          esperado="SICA_ESFERA aparece com CREDITO B2B B2C — o perfil da "
                   "linha que você circulou. Na base inteira são 99 pessoas "
                   "com acesso sugerido pelo CCO no SICA Esfera.")

    regra(doc, "1.3", "O Oracle passa a seguir o perfil do SYSTUR",
          prioritaria=True,
          decide="Quais acessos do Oracle EBS a pessoa pode ter.",
          criterio="Você disse que os acessos do Oracle dependem do perfil "
                   "liberado no SYSTUR. A matriz do Oracle tem a coluna "
                   "PERFIL SYSTUR — 39 valores, 38 deles existindo igualzinho "
                   "no extrato do SYSTUR — e a aplicação a ignorava: a pessoa "
                   "recebia todas as responsabilidades do cargo dela. Agora a "
                   "linha da matriz só vale se ela tiver aquele perfil no "
                   "SYSTUR. Quem tem Oracle e NÃO tem perfil no SYSTUR vira "
                   "pendência NO SYSTUR, porque é lá que está a falta.",
          conferir="Consulta → PRISCILA SANTOS DE LIMA (90001455).",
          esperado="Oracle EBS aderente com os QUATRO perfis da função dela "
                   "(CVC AP NOVA VISUAL / AP BRASIL / AP SUBMARINO / AP VISUAL "
                   "Consulta). Na base: 185 pessoas com Oracle e sem perfil no "
                   "SYSTUR, 68 com acesso fora do que o perfil delas prevê, e "
                   "o “incluir” do Oracle cai de 354 para 233 pessoas. Quem é "
                   "do Mapeamento CCO não passa por esta regra (item 2.1).")

    regra(doc, "1.4", "Quando a matriz não cobre o cargo, a tela diz isso",
          decide="O que aparece para quem tem acesso num sistema que a matriz "
                 "não mapeia para o cargo dela.",
          criterio="Seu pedido: “no ebs vir que não está mapeado”. A linha "
                   "existe, é informativa (não é pendência) e mostra o acesso "
                   "que a pessoa tem hoje. A matriz do Oracle cobre 36 centros "
                   "de custo, então o caso é comum.",
          conferir="Consulta → MARCELO DE CASTRO DIAS (1303) → bloco “Sem "
                   "mapeamento”.",
          esperado="ORACLE_EBS — “tem hoje: CVC OIE BRASIL - Relatório de "
                   "Despesas — sem perfil previsto para o cargo/centro de "
                   "custo”. Na base: 281 pessoas.")

    regra(doc, "1.5", "O CCO passa a seguir a FUNÇÃO da pessoa",
          prioritaria=True,
          decide="Quais acessos do Mapeamento CCO valem para cada pessoa.",
          criterio="Você apontou: “com base na matriz o usuário não pode ter "
                   "acesso ao SIG”. O CCO casa por centro de custo + GESTOR, e "
                   "o mesmo gestor tem várias funções — a pessoa recebia a "
                   "soma de todas. Quem diz qual é a dela é o perfil do "
                   "SYSTUR. Se ela TEM um acesso que a função dela não prevê, "
                   "a linha não some: vira pendência dizendo isso.",
          conferir="Consulta → BRENDA VASCONCELOS DERENCIO (34530984).",
          esperado="Nenhuma linha de SIG cobrada (eram 14, vindas da função "
                   "“A Receber 2 + SIG”, que não é a dela). As outras funções "
                   "da equipe continuam visíveis como “o que ela pode ter” "
                   "(item 2.4). Na base: 2.929 linhas de outra função saíram "
                   "da cobrança — SIG 2.244, SIGOT 336, SICA RA 199, SICA "
                   "Esfera 143 —, afetando 196 pessoas.")

    regra(doc, "1.6", "Quantos perfis a pessoa pode ter",
          decide="O que a coluna “Perfil Esperado” mostra.",
          criterio="Você escreveu: “Ela pode ter acesso a 3 perfis do oracle e "
                   "tem um só então está errado”. A linha guardava apenas o "
                   "perfil que casou, e a tela usa esse campo para calcular a "
                   "diferença — então ela anunciava como excesso tudo o que a "
                   "matriz prevê e não foi o escolhido.",
          conferir="Consulta → GILDA TAVARES DA SILVA (34530435) → Oracle EBS.",
          esperado="“Tem 41 · Faltam 6 · 1 a mais: CVC OIE BRASIL - Relatório "
                   "de Despesas”. Antes dizia “41 a mais”, quando o acesso "
                   "fora do previsto era UM.")

    regra(doc, "1.7", "Transferidos em linhas e colunas",
          prioritaria=True,
          decide="Como a aba Transferidos mostra a situação de quem mudou de "
                 "área.",
          criterio="Seu desenho: Sistema | Tem atualmente | mapeando nova área "
                   "| Incluir/excluir/alterar acesso. As três perguntas de "
                   "17/09 viraram as três colunas. A tabela percorre TODOS os "
                   "sistemas, inclusive aqueles em que não há nada a fazer — "
                   "você pediu uma foto, e “nada aqui” também é informação.",
          conferir="Aba Transferidos → GILDA TAVARES DA SILVA (34530435) → "
                   "clique para expandir.",
          esperado="Sete linhas, uma por sistema, com o login em cinza abaixo "
                   "do nome do sistema. SICA Esfera e SIG aparecem com “—”.")

    regra(doc, "1.8", "O programa não cai mais ao trocar de janela",
          prioritaria=True,
          decide="Se o painel continua respondendo depois de ficar em segundo "
                 "plano.",
          criterio="Eram dois problemas somados. O painel se encerrava sozinho "
                   "após 5 minutos sem sinal de vida — e o navegador congela a "
                   "aba quando a janela fica atrás de outra. E, no Windows, "
                   "duas cópias do painel conseguiam abrir na mesma porta, de "
                   "modo que fechar uma derrubava a outra: o próprio “fechar e "
                   "abrir de novo” recriava o problema.",
          conferir="Abra o painel, vá trabalhar em outra janela por mais de 5 "
                   "minutos e volte.",
          esperado="Tudo continua funcionando, sem precisar fechar e abrir. A "
                   "troca de abas também ficou mais rápida.")

    # ------------------------------------------------- 24/09
    doc.add_page_break()
    h1(doc, "2. Seu documento de 24/09 e os ajustes do dia")

    regra(doc, "2.1", "Quem é do Mapeamento CCO não passa pela regra Oracle x SYSTUR",
          prioritaria=True,
          decide="Se o Oracle de quem está no CCO depende do perfil do SYSTUR.",
          criterio="Para quem está no Mapeamento CCO (centro de custo + gestor), "
                   "o Oracle é comparado direto com o que o CCO prevê, sem o "
                   "filtro pelo perfil do SYSTUR e sem as pendências “sem "
                   "perfil no SYSTUR” e “perfil fora do SYSTUR”. São 57 das "
                   "457 pessoas com Oracle.",
          conferir="Consulta → BRENDA VASCONCELOS DERENCIO (34530984).",
          esperado="Oracle EBS aderente — tem os 6 perfis da função dela; o CVC "
                   "OIE BRASIL - Relatório de Despesas aparece como “1 a mais”, "
                   "informativo. Ela não é pendência.")

    regra(doc, "2.2", "“Não tem mapeado na matriz”",
          decide="O que aparece para quem é do CCO, não tem Oracle e só o CCO "
                 "da equipe prevê Oracle.",
          criterio="Seu pedido: colocar que não tem mapeado na matriz. Em vez de "
                   "sugerir incluir, a linha é informativa e diz isso — dentro "
                   "da função, com cada perfil, e no bloco “Sem mapeamento”. "
                   "A função passa a mostrar quantos perfis ficaram de fora da "
                   "conta, para não dizer “completa” com metade dos acessos.",
          conferir="Consulta → ROSE APARECIDA DIOGO (2752).",
          esperado="Oracle: “não tem mapeado na matriz — a previsão vem só da "
                   "CCO da equipe”. A função “Atendimento a fornecedores CVC e "
                   "VISUAL” mostra “completa · 4 não mapeados na matriz”. Na "
                   "base: 61 pessoas.")

    regra(doc, "2.3", "Opera Operacional aparece pelo Mapeamento CCO",
          decide="Se o Opera Operacional aparece na aplicação.",
          criterio="Não recebemos extrato do Opera, então não dá para conferir se "
                   "a pessoa tem o acesso. O que o CCO prevê para a função dela "
                   "aparece como informativo — nunca como pendência nem como "
                   "“incluir”.",
          conferir="Consulta → EDISON ALVES DO NASCIMENTO (1759) → Funções "
                   "previstas → A Receber 2 + SIG.",
          esperado="OPERA_OPERACIONAL · A_RECEBER_2 · “sem extrato”. Na base: "
                   "149 pessoas, 203 linhas.")

    regra(doc, "2.4", "As outras funções da equipe que a pessoa pode ter",
          prioritaria=True,
          decide="O que aparece das funções do gestor que não são a da pessoa.",
          criterio="O CCO lista todas as funções da equipe. A função da pessoa "
                   "— a que o perfil do SYSTUR indica — é a cobrada. As demais "
                   "aparecem logo abaixo, com cada acesso marcado “tem” / “não "
                   "tem”, sem virar pendência. Quem não tem perfil no SYSTUR "
                   "recebe todas as funções, como antes.",
          conferir="Consulta → BRENDA VASCONCELOS DERENCIO (34530984) → final "
                   "da aba Acessos.",
          esperado="“Outras funções que a pessoa pode ter (3)”: A Receber 1 "
                   "Comissão, A Receber 2 + SIG e A Receber 3. Na base: 374 "
                   "pessoas têm o bloco.")

    regra(doc, "2.5", "Um perfil por sistema: as outras opções não são “falta”",
          prioritaria=True,
          decide="Como aparece o sistema em que a matriz prevê mais de uma "
                 "opção e a pessoa tem uma.",
          criterio="Seu documento: “se um dos acessos mapeados estiver ok traz "
                   "ele ok, e os a mais precisam ser trazidos estilo as funções "
                   "do CCO”. O sistema vem aderente, sem “Falta 1”, e as outras "
                   "opções vão para o bloco “Outros acessos previstos”. Uma "
                   "opção aparece direto; mais de uma fica recolhida. Vale para "
                   "todos os sistemas menos o Oracle, onde cada perfil é um "
                   "acesso.",
          conferir="Consulta → ROSELAINE DO NASCIMENTO FIGUEIREDO (34532575); "
                   "depois CAIO LUIZ DA COSTA (34531299).",
          esperado="Roselaine: SIGOT, SYSTUR e IC aderentes; em “Outros acessos "
                   "previstos”, SIGOT Intercompany, SYSTUR INTERCOMPANY e IC "
                   "IC_CADASTRO. Caio: “SYSTUR — 2 opções”, recolhido. Na base: "
                   "168 pessoas.")

    regra(doc, "2.6", "“Não pode ter acesso e tem”",
          prioritaria=True,
          decide="O que aparece para quem tem acesso num sistema que nem a "
                 "matriz nem o CCO preveem para ela.",
          criterio="A tela dizia só “sem perfil previsto”, sem mostrar o acesso. "
                   "Agora é pendência, com o perfil que a pessoa tem. Nas "
                   "linhas de análise com um lado só, a tela diz qual é: "
                   "“Deveria ter:” ou “Tem hoje:”.",
          conferir="Consulta → DENISE APARECIDA GONCALVES DOS SANTOS (1562).",
          esperado="Necessário análise: SYSTUR “Deveria ter: INTEGRADOR_CONTABIL” "
                   "e IC “Tem hoje: IC_CADASTRO”. Na base: 7 pessoas.")

    regra(doc, "2.7", "A função certa em cada acesso",
          decide="Em qual função do CCO cada acesso aparece.",
          criterio="O mesmo perfil do Oracle está em várias funções da equipe, e "
                   "a aplicação pegava a primeira da planilha. Agora vale a "
                   "função que o SYSTUR da pessoa indica. Só muda o nome da "
                   "função exibida; nenhum status muda.",
          conferir="Consulta → EDISON ALVES DO NASCIMENTO (1759).",
          esperado="Uma função só: A Receber 2 + SIG, com o Oracle dentro dela. "
                   "Antes aparecia também “A Receber 1”, que não é a dele.")

    # ------------------------------------------------- o que muda na tela
    doc.add_page_break()
    h1(doc, "3. O que vai parecer diferente — e por quê")
    par(doc,
        "Estas mudanças alteram números que você acompanha. Nenhuma delas é "
        "erro; todas vêm dos pontos acima.")
    lista(doc, [
        "O total de linhas cai de 14.176 para 12.310. São os acessos de função "
        "que não é da pessoa (item 1.5) e os do Oracle que o perfil do SYSTUR "
        "não autoriza (item 1.3).",
        "As pendências SOBEM: de 1.151 para 1.278 pessoas. A maior parte são "
        "as 185 pessoas que têm Oracle e não têm perfil no SYSTUR.",
        "Aparecem linhas novas de Opera Operacional (149 pessoas) e de “não tem "
        "mapeado na matriz” no Oracle (61 pessoas) — as duas informativas.",
        "Aparecem 7 pendências novas de “não pode ter acesso e tem”.",
    ])

    # ------------------------------------------------- perguntas
    doc.add_page_break()
    h1(doc, "4. Duas perguntas para você")
    pergunta(doc, "4.1 O Relatório de Despesas deve contar como pendência?",
             "Hoje conta para quem passa pela regra do SYSTUR. São 373 das 457 "
             "pessoas com Oracle que têm esse acesso. Se for corporativo, ele "
             "deixa de contar e a fila do Oracle diminui bastante.")
    pergunta(doc, "4.2 No SIG, os perfis são alternativos ou se somam?",
             "Hoje ter mais de um perfil no mesmo sistema vira pendência, e no "
             "SIG isso são 230 linhas. Mas 47% das pessoas com SIG têm mais de "
             "um (média de 18,7), e os nomes parecem permissões que se somam "
             "(ACESSO_CARRO_INTER_GRUPOS, CAD_FORNECEDOR_SALVAR). No SYSTUR, "
             "onde a regra faz sentido, são 1%.")

    # ------------------------------------------------- saida
    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_DOCX)
    OUT_MD.write_text("\n".join(_MD), encoding="utf-8")
    print(f"gerado: {OUT_DOCX}")
    print(f"gerado: {OUT_MD}")


if __name__ == "__main__":
    main()
