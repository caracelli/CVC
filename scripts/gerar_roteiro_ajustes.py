# -*- coding: utf-8 -*-
"""Gera ENTREGA/ROTEIRO_AJUSTES_CVC_IAM_2026-09-08.docx (+ .md).

COMPLEMENTA o ROTEIRO_REGRAS_CVC_IAM_v1.0.0 (06/08). Aquele descreve as regras
que ja' estavam no ar; este cobre SO' o que mudou desde entao — que e' onde a
tela vai parecer diferente do que ela conhece.

POR QUE ESTE NAO PUXA NUMERO DA API (o de 06/08 puxava):

O pacote de 06/08 levava o BANCO PRONTO, entao dava para cravar "Deve mostrar:
421 pessoas" — o numero era o mesmo na maquina dela. O pacote de agora
(UPDATE_BRUNA) leva SO' os executaveis: o banco dela nasce da ENTRADA da
maquina dela, com os extratos dela. Numero do NOSSO ambiente escrito aqui
apareceria como falha em cada linha da tela dela.

Entao cada regra traz um de dois tipos de verificacao:

  INVARIANTE  — vale em qualquer base ("tem de ser zero"). Esse eu cravo.
  MEDIDO      — o que deu na nossa base de referencia, rotulado como tal, so'
                para dar ordem de grandeza. O numero dela pode diferir.

Uso:  python scripts/gerar_roteiro_ajustes.py
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

RAIZ = Path(__file__).resolve().parent.parent
OUT_DOCX = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-09-08.docx"
OUT_MD = RAIZ / "ENTREGA" / "ROTEIRO_AJUSTES_CVC_IAM_2026-09-08.md"

AZUL = RGBColor(0x1F, 0x2D, 0x5C)
CINZA = RGBColor(0x5A, 0x64, 0x78)
TEXTO = RGBColor(0x2C, 0x33, 0x40)
AMBAR = RGBColor(0x7A, 0x5B, 0x10)
VERDE = RGBColor(0x1E, 0x7B, 0x43)
VERMELHO = RGBColor(0xA4, 0x26, 0x2C)

_MD = []          # espelho markdown do que vai para o docx


# ---------------------------------------------------------------- docx utils
def shade(cell, cor):
    tc = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear"); el.set(qn("w:color"), "auto")
    el.set(qn("w:fill"), cor)
    tc.append(el)


def h1(doc, txt):
    p = doc.add_heading(txt, level=1)
    for r in p.runs:
        r.font.color.rgb = AZUL
    _MD.append(f"\n## {txt}\n")
    return p


def par(doc, txt, size=10, italic=False, bold=False, cor=TEXTO, space=4, md=True):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space)
    r = p.add_run(txt)
    r.italic, r.bold = italic, bold
    r.font.size = Pt(size)
    r.font.color.rgb = cor
    if md and txt:
        _MD.append(f"**{txt}**\n" if bold else f"{txt}\n")
    return p


def nota(doc, txt):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(txt)
    r.italic = True
    r.font.size = Pt(8.5)
    r.font.color.rgb = AMBAR
    _MD.append(f"> {txt}\n")


def regra(doc, cod, titulo, decide, criterio, conferir, esperado,
          tipo_esperado="INVARIANTE", prioritaria=False,
          rot_medido="Medido na base de referência (o seu pode diferir)"):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(11)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(("★  " if prioritaria else "") + f"{cod}  {titulo}")
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = AZUL
    _MD.append(f"\n### {'★ ' if prioritaria else ''}{cod} {titulo}\n")

    # rot_medido tem de comecar com "Medido": a cor da celula depende disso
    rot_esperado = ("Deve mostrar (vale em qualquer base)"
                    if tipo_esperado == "INVARIANTE" else rot_medido)
    linhas = [
        ("O que decide", decide),
        ("Critério", criterio),
        ("Como conferir", conferir),
        (rot_esperado, esperado),
        ("A regra está correta? Se não, qual deveria ser?", ""),
    ]
    tbl = doc.add_table(rows=0, cols=2)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    for rot, val in linhas:
        cells = tbl.add_row().cells
        cells[0].width = Cm(4.6)
        cells[1].width = Cm(11.9)
        pergunta = rot.startswith("A regra")
        r0 = cells[0].paragraphs[0].add_run(rot)
        r0.bold = True
        r0.font.size = Pt(8.5)
        r0.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if pergunta else AZUL
        shade(cells[0], "1F2D5C" if pergunta else "EEF2F8")
        r1 = cells[1].paragraphs[0].add_run(val)
        r1.font.size = Pt(9)
        eh_num = rot.startswith("Deve mostrar") or rot.startswith("Medido")
        r1.font.color.rgb = (VERDE if rot.startswith("Deve mostrar")
                             else CINZA if rot.startswith("Medido") else TEXTO)
        if eh_num:
            r1.bold = True
        if pergunta:
            shade(cells[1], "FCF9EE")
        _MD.append(f"- **{rot}:** {val}" if val else f"- **{rot}:** ______")
    _MD.append("")
    return tbl


def main():
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    # ------------------------------------------------------------ capa
    t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = t.add_run("CVC IAM Analytics"); r.bold = True
    r.font.size = Pt(20); r.font.color.rgb = AZUL
    s = doc.add_paragraph()
    r = s.add_run("Roteiro de validação dos ajustes — o que mudou desde 06/08")
    r.font.size = Pt(13); r.font.color.rgb = CINZA
    par(doc, "Pacote UPDATE_BRUNA_v1.0.0  ·  08/09/2026", size=9, cor=CINZA)
    _MD.insert(0, "# CVC IAM Analytics\n"
                  "## Roteiro de validação dos ajustes — o que mudou desde 06/08\n"
                  "Pacote UPDATE_BRUNA_v1.0.0 · 08/09/2026\n")

    doc.add_paragraph()
    par(doc, "Por que este documento existe", bold=True, size=11, cor=AZUL, space=2)
    par(doc,
        "O roteiro de 06/08 descreve as regras que já estavam no ar. Este cobre "
        "só o que MUDOU desde então — que é justamente onde a tela vai parecer "
        "diferente do que você conhece. A ideia é que nenhuma diferença apareça "
        "como surpresa: se algo mudou de lugar, está explicado aqui, com o "
        "critério e o passo para conferir.")

    par(doc, "Como usar", bold=True, size=11, cor=AZUL, space=2)
    par(doc,
        "Cada ajuste tem “Como conferir” (o que filtrar na tela) e um valor "
        "esperado. A última linha é a que importa: dizer se a regra está CERTA. "
        "Se não bater com o que você vê, já é um achado — anote e me avise.")
    par(doc,
        "As regras marcadas com ★ são as que mais mudam o volume da fila. Se o "
        "tempo for curto, comece por elas.")

    nota(doc,
         "Uma diferença importante em relação ao roteiro de 06/08: aquele pacote "
         "levava o banco pronto, então dava para cravar o número exato de cada "
         "tela. Este pacote leva só os executáveis — o banco é gerado na sua "
         "máquina, com os seus extratos. Por isso cada linha diz se o valor é um "
         "INVARIANTE (tem de valer em qualquer base) ou apenas o que MEDIMOS na "
         "nossa base de referência, que serve como ordem de grandeza.")

    # ------------------------------------------------------------ antes de tudo
    doc.add_page_break()
    h1(doc, "Antes de tudo: o que fazer, nesta ordem")
    par(doc,
        "O passo 3 é o que costuma escapar, e sem ele nada deste documento "
        "acontece na tela — os ajustes agem na fase de ANÁLISE, não na "
        "importação. Enquanto o Processador não rodar, os números continuam os "
        "da rodada anterior.")
    passos = [
        ("1.", "Feche o painel e o Processador, se estiverem abertos."),
        ("2.", "Extraia o pacote e copie EXECUTAVEIS/ por cima da pasta atual. "
               "NÃO apague nem mexa em DADOS/ e INTERACOES/ — é onde ficam o "
               "banco e as tratativas que você já registrou."),
        ("2b.", "Copie também a pasta ENTRADA/ do pacote por cima da atual. Ela "
                "leva só dois arquivos de referência (o de-para do SIG e a "
                "matriz do franqueado). Nenhum dado seu é substituído."),
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

    par(doc, "", space=2)
    par(doc, "Os números vão mudar bastante", bold=True, size=11,
        cor=VERMELHO, space=2)
    par(doc,
        "Esta rodada mexe em como várias populações são julgadas, então a "
        "comparação com a tela de antes não fecha — e isso é esperado, não "
        "defeito. Print ou planilha tirada da tela atual fica desatualizada "
        "depois do passo 3.")

    # ------------------------------------------------------------ 1 franqueado
    doc.add_page_break()
    h1(doc, "1. Franqueado — a mudança maior")

    par(doc,
        "Foi o pedido que você fez em 31/08 (“para franqueado não tem a questão "
        "de espelho”) e repetiu em 04/09, olhando o print com a origem "
        "“Espelho — franqueados”. Está atendido, e é a mudança que mais altera "
        "a tela.")

    regra(doc, "1.1", "Franqueado saiu do espelho",
          "Como o perfil esperado do franqueado é determinado.",
          "Enquanto a matriz de lojas estiver carregada, franqueado NÃO passa "
          "mais pelo espelho dos colegas. Terceiro e prestador continuam no "
          "espelho — eles não têm matriz, e tirá-los apagaria essa população "
          "da tela.",
          "Pendências ou Consulta → funil da coluna Origem.",
          "“Espelho — franqueados” não pode aparecer nenhuma vez. Se aparecer, "
          "a matriz não foi lida — me avise.",
          prioritaria=True)
    nota(doc,
         "Consequência aceita: franqueado SEM acesso nenhum deixou de receber "
         "sugestão de inclusão. Sem o tipo de loja no cadastro, a matriz não "
         "consegue dizer QUAL perfil conceder — e inventar a partir dos colegas "
         "era exatamente o que você vetou.")

    regra(doc, "1.2", "Matriz de lojas — o que ela valida",
          "Se o perfil que o franqueado TEM é justificado pelo cargo dele.",
          "A matriz cruza CARGO × TIPO DE ATENDIMENTO × TIPO DE LOJA. As duas "
          "últimas não existem no cadastro (local de trabalho e filial vêm "
          "vazios), mas o NOME do perfil as codifica — ATEND_PUBLIC_LJT_… é "
          "atendimento ao público em loja terceirizada. Por isso a regra só "
          "fecha ao contrário: valida ADERÊNCIA, não gera inclusão.",
          "Pendências ou Consulta → funil da coluna Origem = "
          "“Matriz — franqueado”.",
          "Toda linha dessa origem tem de trazer um motivo dizendo se o cargo "
          "autoriza o perfil. Linha sem motivo é achado.",
          prioritaria=True)

    regra(doc, "1.3", "Cargo que não autoriza o perfil",
          "O achado de segurança desta rodada.",
          "Quando o cargo da pessoa não consta na matriz para o perfil que ela "
          "tem, a linha sai como divergência com o motivo "
          "CARGO_NAO_AUTORIZA_PERFIL. São os dois sentidos: atendente com "
          "perfil de gerente (escalada de privilégio) e gerente com perfil "
          "abaixo do cargo.",
          "Consulta → busque pelo texto do motivo, ou filtre a origem "
          "“Matriz — franqueado” e olhe a coluna de motivo.",
          "231 acessos (215 pessoas) — dos quais 44 atendentes com perfil de "
          "supervisor e 31 com perfil de gerente.",
          tipo_esperado="MEDIDO", prioritaria=True)
    nota(doc,
         "Este é o número que vale conferir caso a caso: cada um é uma pessoa "
         "com acesso que o cargo dela não prevê.")

    regra(doc, "1.4", "Perfis de exceção da Governança de SI",
          "O bloco separado no fim da sua planilha de matriz.",
          "FRANQUEADOS_VC, GERENTE_GERAL_MASTER e MASTER_FRANQUEADO nunca são "
          "carregados como perfil esperado — se fossem, o painel passaria a "
          "MANDAR conceder MASTER_FRANQUEADO a todo gerente de franquia. Quem "
          "tem um deles vai para Em Análise citando a Governança.",
          "Consulta → busque por FRANQUEADOS_VC ou MASTER_FRANQUEADO.",
          "Nenhum desses três pode aparecer como perfil ESPERADO / a conceder. "
          "Se aparecer, é defeito.",
          prioritaria=True)
    nota(doc,
         "PERGUNTA EM ABERTO (1 de 3): existe aprovação da Governança de "
         "Segurança da Informação para esses acessos? Medimos 207 na base de "
         "referência — entre eles 1 caixa e 3 atendentes com FRANQUEADOS_VC, "
         "que são os que mais saltam.")

    regra(doc, "1.5", "De-para de cargo derivado do uso",
          "Como o cargo do RH é traduzido para o cargo da matriz.",
          "O RH escreve VENDEDOR, VENDEDORA, ATENDENTE - ; a matriz fala "
          "ATENDENTE. Em vez de pedir a lista, o de-para é derivado do próprio "
          "uso: se pelo menos 70% dos acessos de um cargo apontam para o mesmo "
          "cargo da matriz, ele é tratado como equivalente. Cargo que já existe "
          "na matriz NÃO ganha tradutor — senão um gerente com perfil de "
          "atendente viraria aderente.",
          "Consulta → a coluna de motivo mostra “cargo X tratado como Y "
          "(N acessos, M% de consistência)”.",
          "11 equivalências. As cinco maiores: ATENDENTE - → ATENDENTE (1.144 "
          "acessos, 98%) · SUPERVISOR → SUPERVISOR ADMINISTRATIVO (326, 93%) · "
          "GERENTE - → GERENTE (200, 96%) · GERENTE DE VENDAS → GERENTE (166, "
          "98%) · VENDEDOR → ATENDENTE (131, 94%).",
          tipo_esperado="MEDIDO")
    nota(doc,
         "PERGUNTA EM ABERTO (2 de 3): essas equivalências estão certas? Elas "
         "saem do uso, não de uma definição sua — se alguma estiver errada, ela "
         "está escondendo ou criando divergência.")

    # ------------------------------------------------------------ 2 em analise
    doc.add_page_break()
    h1(doc, "2. Por que tanto franqueado em “Em Análise”")

    par(doc,
        "Esta seção existe porque é o ponto onde a tela mais vai destoar do que "
        "você viu na rodada passada, e a causa não é a regra nova — é o extrato.")

    regra(doc, "2.1", "Conta sem status no extrato",
          "O que fazer quando o extrato não diz se a conta está ativa.",
          "A regra que você definiu é que não se assume conta ativa. O extrato "
          "SYSTUR antigo (o relatório de 30/04, em XLSX) não traz coluna de "
          "status; o formato novo (view_systur_….csv) traz. Sem status, o "
          "resultado vai para Em Análise — mas agora PRESERVANDO o veredito da "
          "matriz no motivo, em vez de apagá-lo.",
          "Consulta → filtre origem “Matriz — franqueado” e leia a coluna de "
          "motivo.",
          "Se o seu extrato SYSTUR não tiver status, quase todo franqueado cai "
          "em Em Análise — mas cada linha continua dizendo se o cargo autoriza "
          "o perfil. O veredito não se perde.",
          prioritaria=True)
    nota(doc,
         "PERGUNTA EM ABERTO (3 de 3): qual extrato do SYSTUR está na sua "
         "ENTRADA? Se for o de 30/04, vale trocar pelo mais recente no formato "
         "view_systur_….csv — com a coluna de status, os aderentes aparecem "
         "como Aderente e as divergências como Divergente, limpo. Foi o que "
         "medimos: 4.405 aderentes / 231 divergentes / 207 de exceção.")

    regra(doc, "2.2", "Conta pendente ou bloqueada vira “a incluir”",
          "O desfecho de quem tem conta, mas ela não está ativa.",
          "Pedido seu em 31/08: conta com status inativo, bloqueado ou P, "
          "quando a pessoa pode ter o acesso, sai como “a incluir” mostrando o "
          "perfil liberável. Vale para todos os sistemas — com UMA exceção: "
          "franqueado, porque ali essa conversão apagaria a escalada de "
          "privilégio da regra 1.3.",
          "Pendências → filtro Ação = “Incluir Acesso”; a coluna de motivo "
          "distingue CONTA_PENDENTE de CONTA_BLOQUEADA.",
          "Nenhuma linha de franqueado pode sair com o motivo CONTA_PENDENTE "
          "genérico — o motivo dela tem de citar a matriz.")
    nota(doc,
         "Esta exceção é uma decisão nossa, e é o ponto do documento que mais "
         "merece a sua opinião: ela privilegia não perder o achado de segurança, "
         "ao custo de o franqueado ficar em Em Análise em vez de “a incluir”. "
         "Se preferir o contrário, é reversível numa linha.")

    # ------------------------------------------------------------ 3 desligados
    doc.add_page_break()
    h1(doc, "3. Desligados e contas de sistema")

    regra(doc, "3.1", "Conta de serviço não é acesso de desligado",
          "O que fazer com robô cadastrado com o e-mail de uma pessoa.",
          "Login com prefixo SIST é conta de serviço: sai da lista de revogação "
          "e passa a ter categoria própria, em vez de aparecer como acesso a "
          "revogar de quem saiu. O robô não é revogado porque quem o cadastrou "
          "foi embora — revogar derruba produção. A lista de prefixos está no "
          "config, não no código.",
          "Desligados → a categoria própria de conta de serviço.",
          "297 acessos saíram da lista de revogação — 69% das 432 linhas que "
          "havia. Vieram de 10 logins: ROBO MARITIMO, AUTOMACAO RPA SOLO, "
          "PROJETO JENKINS, ROBO AEREO GRUPOS, entre outros.",
          tipo_esperado="MEDIDO", prioritaria=True)
    nota(doc,
         "Era o SIST0230 do seu print de 28/08. Uma conta ficou de fora do "
         "corte e vale o seu olhar: MTZOPE288 / CCO PLANTAO — conta "
         "compartilhada de plantão, nem robô nem pessoa.")

    regra(doc, "3.2", "Desligado que voltou a trabalhar",
          "Quando um desligado com acesso é falso positivo.",
          "Se a conta pertence a alguém ATIVO hoje com o MESMO login, não é "
          "acesso a revogar — é a conta que a pessoa usa. Só aponta quando o "
          "ativo tem login diferente, aí a conta antiga sobra mesmo. Regra sua, "
          "textual, de 10/08.",
          "Desligados → a lista de revogação.",
          "A regra derrubou os falsos positivos de 762 para 24 pessoas na base "
          "em que foi medida.",
          tipo_esperado="MEDIDO")

    # ------------------------------------------------------------ 4 consulta
    doc.add_page_break()
    h1(doc, "4. Consulta — identidade e perfis")

    regra(doc, "4.1", "Mesma pessoa em dois vínculos vira uma linha",
          "Quando duas identidades são a mesma pessoa.",
          "Você apontou em 10/08: “se é a mesma pessoa por que traz separado?”. "
          "Acontece quando alguém existe em duas origens — prestador no "
          "diretório e terceiro no RH, mesmo CPF. Agora elas viram uma linha só, "
          "somando os acessos. É fusão de APRESENTAÇÃO: cada tratativa continua "
          "gravada contra a identidade real, e o detalhe mostra de qual "
          "identidade veio cada acesso.",
          "Consulta → busque por um CPF que você saiba ter dois cadastros.",
          "Uma linha por pessoa, com os dois vínculos na coluna Categoria "
          "(ex.: “Prestador · Terceiro”).")
    nota(doc,
         "Ajuste de 08/09: a fusão passou a exigir também que o NOME tenha algo "
         "em comum. Encontramos 8 casos na base em que o mesmo CPF estava em "
         "pessoas diferentes — código de terceiro cadastrado no campo de CPF. "
         "Sem essa trava, o acesso de uma apareceria sob o nome da outra.")

    regra(doc, "4.2", "Perfil excessivo aparece na tela",
          "Quem tem o perfil certo MAIS outros que o cargo não prevê.",
          "Antes o veredito Aderente prevalecia e o extra sumia — a tela "
          "afirmava o que a pessoa tinha, e afirmava errado. Agora o extra "
          "aparece no perfil atual e a linha ganha um “?” explicando. Por "
          "decisão de configuração, isso NÃO vira pendência: é informativo.",
          "Consulta → linhas com o ícone “?” e o texto de perfil excessivo.",
          "141 casos, somando 178 perfis a mais.",
          tipo_esperado="MEDIDO")
    nota(doc,
         "Existe uma chave de configuração para transformar isso em pendência "
         "de verdade. Está desligada porque cobrar 141 casos de uma vez é "
         "decisão sua, não nossa.")

    # ------------------------------------------------------------ 5 leitura
    doc.add_page_break()
    h1(doc, "5. Leitura dos arquivos")

    regra(doc, "5.1", "O leitor acha o cabeçalho sozinho",
          "Como cada extrato é interpretado.",
          "O leitor passou a procurar a linha do cabeçalho e o separador pelos "
          "nomes de coluna que espera, em vez de contar linhas fixas. Nasceu do "
          "SICA_RA, que chegou em 01/09 num layout novo — e o leitor antigo lia "
          "ZERO acesso sem dar erro nenhum. Falha silenciosa é o pior tipo.",
          "Painel → link “Arquivos importados”, no topo.",
          "Cada base tem de mostrar a data do arquivo que você depositou. Data "
          "velha em alguma base significa que aquele arquivo não entrou.",
          prioritaria=True)

    regra(doc, "5.2", "Extrato cumulativo — o mais novo manda",
          "Qual arquivo vale quando chegam vários do mesmo sistema.",
          "Cada exportação traz a base inteira com o status do dia, então o "
          "arquivo mais recente substitui o anterior. Quando o nome não tem "
          "data, vale a data do arquivo.",
          "Painel → “Arquivos importados”.",
          "A data mostrada tem de ser a do arquivo mais recente que você "
          "colocou na pasta.")
    nota(doc,
         "Achado que vale a sua confirmação: no extrato do SICA_RA de 01/09, "
         "116 dos 135 acessos que o painel mostrava não existem mais como "
         "acesso vivo (110 viraram inativo, 6 bloqueado, 7 sumiram). Se esse "
         "arquivo for o extrato COMPLETO do sistema, está certo; se for um "
         "recorte, precisamos do arquivo inteiro.")

    # ------------------------------------------------------------ 6 nao mudou
    doc.add_page_break()
    h1(doc, "6. O que NÃO mudou (e continua valendo)")
    par(doc,
        "Tudo que está no roteiro de 06/08 segue em vigor. Vale reforçar três "
        "pontos que costumam gerar dúvida e não foram alterados nesta rodada:")
    for txt in [
        "Conta BLOQUEADA ou INATIVA não conta como acesso — a ação certa nesses "
        "casos é desbloquear, não criar.",
        "“Incluir Acesso” e “Aderente” não entram na contagem de pendências: "
        "quem não tem o acesso não é irregularidade a corrigir.",
        "O limiar de 30% de adesão continua suprimindo inclusão em cargo onde "
        "quase ninguém tem o acesso — é o que evita inundar a fila.",
    ]:
        p = doc.add_paragraph(txt, style="List Bullet")
        for r_ in p.runs:
            r_.font.size = Pt(9.5)
            r_.font.color.rgb = TEXTO
        _MD.append(f"- {txt}")

    # ------------------------------------------------------------ 7 resumo
    doc.add_page_break()
    h1(doc, "7. Resumo para devolver")
    par(doc,
        "Se preferir responder de uma vez: as três perguntas em aberto e, "
        "abaixo, o que discordar. O que não for citado fica entendido como "
        "aprovado.")

    perguntas = [
        ("1", "Os perfis de exceção (FRANQUEADOS_VC, GERENTE_GERAL_MASTER, "
              "MASTER_FRANQUEADO) têm aprovação da Governança de SI?"),
        ("2", "As 11 equivalências de cargo derivadas do uso estão corretas?"),
        ("3", "Qual extrato do SYSTUR está na sua ENTRADA — o de 30/04 ou o "
              "formato novo com coluna de status?"),
    ]
    for num, txt in perguntas:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(f"{num}.  "); r.bold = True
        r.font.size = Pt(10.5); r.font.color.rgb = AZUL
        r2 = p.add_run(txt); r2.font.size = Pt(9.5); r2.font.color.rgb = TEXTO
        _MD.append(f"{num}. {txt}")

    par(doc, "", space=6)
    tbl = doc.add_table(rows=1, cols=3)
    tbl.style = "Table Grid"
    hdr = tbl.rows[0].cells
    for i, titulo in enumerate(("Regra", "O que está errado", "O que deveria ser")):
        r_ = hdr[i].paragraphs[0].add_run(titulo)
        r_.bold = True; r_.font.size = Pt(9)
        r_.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(hdr[i], "1F2D5C")
    for _ in range(6):
        tbl.add_row()
    _MD.append("\n| Regra | O que está errado | O que deveria ser |\n"
               "|---|---|---|\n| | | |\n| | | |\n| | | |\n")

    par(doc, "", space=6)
    nota(doc,
         "Toda regra deste documento é critério ou parâmetro que pode mudar. "
         "Alteração exige um reprocessamento para os números refletirem a "
         "decisão.")

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_DOCX)
    OUT_MD.write_text("\n".join(_MD), encoding="utf-8")
    print(f"OK -> {OUT_DOCX}  ({OUT_DOCX.stat().st_size/1024:.0f} KB)")
    print(f"OK -> {OUT_MD}  ({OUT_MD.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
