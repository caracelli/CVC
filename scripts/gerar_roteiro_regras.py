# -*- coding: utf-8 -*-
"""Gera ENTREGA/ROTEIRO_REGRAS_CVC_IAM_v1.0.0.docx.

Roteiro de validacao POR CATEGORIA E REGRA — o que foi construido, o criterio
exato de cada regra (limiares inclusive) e quanto ela produziu na base entregue.

A ideia: teste automatizado prova que o CODIGO faz o que foi escrito; so a
usuaria prova que a REGRA esta certa. Entao cada regra vem com o numero que ela
gerou e uma linha de parecer para ela responder "concordo / nao concordo".

Sem nome e matricula de pessoa: o documento circula por e-mail. Onde e' preciso
localizar um caso, o caminho e' o filtro do painel.

Uso:
    python scripts/gerar_roteiro_regras.py
"""
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "ENTREGA" / "ROTEIRO_REGRAS_CVC_IAM_v1.0.0.docx"

AZUL = RGBColor(0x1F, 0x2D, 0x5C)
CINZA = RGBColor(0x5A, 0x64, 0x78)
TEXTO = RGBColor(0x2C, 0x33, 0x40)
AMBAR = RGBColor(0x7A, 0x5B, 0x10)


def shade(cell, cor):
    tc = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:color"), "auto")
    el.set(qn("w:fill"), cor)
    tc.append(el)


def h1(doc, txt):
    p = doc.add_heading(txt, level=1)
    for r in p.runs:
        r.font.color.rgb = AZUL
    return p


def h2(doc, txt):
    p = doc.add_heading(txt, level=2)
    for r in p.runs:
        r.font.color.rgb = AZUL
        r.font.size = Pt(12)
    return p


def par(doc, txt, size=10, italic=False, bold=False, cor=TEXTO, space=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space)
    r = p.add_run(txt)
    r.italic, r.bold = italic, bold
    r.font.size = Pt(size)
    r.font.color.rgb = cor
    return p


def regra(doc, codigo, titulo, decide, criterio, onde, na_base):
    """Uma regra = um bloco. Ultima linha em branco: o parecer da usuaria."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(f"{codigo}  {titulo}")
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = AZUL

    linhas = [("O que a regra decide", decide),
              ("Critério exato", criterio),
              ("Onde ver no painel", onde),
              ("Na base entregue", na_base),
              ("Parecer (preencher)", "")]
    tbl = doc.add_table(rows=0, cols=2)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    for rot, val in linhas:
        cells = tbl.add_row().cells
        cells[0].width = Cm(4.2)
        cells[1].width = Cm(12.3)
        c0 = cells[0].paragraphs[0]
        r0 = c0.add_run(rot)
        r0.bold = True
        r0.font.size = Pt(8.5)
        r0.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if rot.startswith("Parecer") else AZUL
        shade(cells[0], "1F2D5C" if rot.startswith("Parecer") else "EEF2F8")
        c1 = cells[1].paragraphs[0]
        r1 = c1.add_run(val)
        r1.font.size = Pt(9)
        r1.font.color.rgb = TEXTO
        if rot.startswith("Parecer"):
            shade(cells[1], "FCF9EE")
    return tbl


def nota(doc, txt):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(txt)
    r.italic = True
    r.font.size = Pt(8.5)
    r.font.color.rgb = AMBAR


def main():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)

    # ---------------- capa ----------------
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = t.add_run("CVC IAM Analytics")
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = AZUL
    s = doc.add_paragraph()
    r = s.add_run("Roteiro de validação por categoria e regra")
    r.font.size = Pt(13)
    r.font.color.rgb = CINZA
    par(doc, "Pacote TESTE_LOCAL_BRUNA_v1.0.0  ·  06/08/2026", size=9, cor=CINZA)

    doc.add_paragraph()
    par(doc, "Para que serve este documento", bold=True, size=11, cor=AZUL)
    par(doc,
        "Os testes automatizados provam que o sistema faz o que foi programado. "
        "Eles não provam que a REGRA está certa — isso só quem conhece a operação "
        "consegue dizer. Este roteiro lista, categoria por categoria, cada regra "
        "que decide sozinha alguma coisa no painel: o critério que ela usa (com os "
        "limiares numéricos) e quanto ela produziu na base entregue.")
    par(doc,
        "Cada bloco tem uma linha de Parecer em branco. Basta escrever se concorda "
        "com a regra ou o que deveria mudar. Onde discordar, o número muda depois "
        "de um reprocessamento — nenhuma regra deste documento é definitiva.")

    par(doc, "Como localizar os casos", bold=True, size=11, cor=AZUL, space=2)
    par(doc,
        "Não há nome nem matrícula aqui de propósito: o documento circula por "
        "e-mail. Para ver os casos de uma regra, use o caminho indicado em "
        "“Onde ver no painel”.")

    nota(doc,
         "Ressalva desta base: as pendências que vieram da matriz de cargo foram "
         "geradas hoje, então a coluna de tempo de tratamento na Visão Geral está "
         "achatada. Os números de validação estão corretos; apenas o “há quantos "
         "dias” dessas linhas não representa histórico real.")

    doc.add_page_break()

    # ---------------- 1. identidade ----------------
    h1(doc, "1. Identidade — ligar o acesso a uma pessoa")
    par(doc,
        "Antes de julgar se um acesso é indevido, o sistema precisa saber de quem "
        "ele é. Toda regra das seções seguintes depende desta. São 92.794 acessos "
        "lidos dos sete sistemas contra 14.428 ativos e 29.831 desligados do RH.")

    regra(doc, "1.1", "Cascata de vinculação (acesso → pessoa)",
          "De quem é cada acesso encontrado nos extratos.",
          "Tenta em ordem, e para no primeiro que casar: CPF → e-mail → login → "
          "CPF parcial + nome → nome → aproximação (fuzzy). A ordem vai do mais "
          "confiável para o menos: o CPF identifica sozinho, o nome não.",
          "Consulta → coluna Vínculo; e o método aparece no detalhe do acesso.",
          "CPF 50.412 · nome 9.384 · e-mail 1.442 · fuzzy 694 · login 128 · "
          "CPF parcial 13 · não vinculado 30.721 (33,1%).")
    nota(doc,
         "Os 33,1% não vinculados são majoritariamente contas de franqueado e "
         "prestador, que não estão na base de RH — por isso as três exportações do "
         "diretório (regra 1.4). Vale conferir se esse percentual faz sentido.")

    regra(doc, "1.2", "Situação da conta manda",
          "Se uma conta encontrada no extrato conta como acesso.",
          "Conta BLOQUEADA ou INATIVA não é acesso: já está revogada, então não "
          "vira pendência nem irregularidade — em nenhuma das regras.",
          "Não aparece como pendência em lugar nenhum (é uma exclusão).",
          "Das 92.794 contas: 48.170 bloqueadas, 44.605 ativas, 11 pendentes, "
          "6 inativas, 2 desligadas. 17.259 acessos foram ignorados por este motivo.")
    nota(doc,
         "Esta é a regra de maior impacto no volume: mais da metade das contas "
         "está bloqueada. Se para a CVC uma conta bloqueada ainda for risco "
         "(porque pode ser reativada), a regra precisa mudar.")

    regra(doc, "1.3", "Acesso sem vínculo com o RH (órfão)",
          "Acesso cujo dono não foi encontrado em nenhuma base de pessoas.",
          "Um achado por LOGIN e SISTEMA — não por perfil. Um login com cinco "
          "perfis gera um achado, não cinco, e o achado carrega todos os perfis. "
          "Contas bloqueadas ficam de fora (regra 1.2).",
          "Pendências → filtro Tipo = “Sem Vínculo RH”.",
          "65 achados: SYSTUR 54 · SIG 5 · SIGOT 3 · SICA RA 1 · SICA Esfera 1 · IC 1.")

    regra(doc, "1.4", "Identidades do diretório (AD)",
          "Quem é franqueado, prestador ou já desligado, para quem não está no RH.",
          "Três exportações do diretório (franqueados, prestadores, desligados) "
          "entram como fonte de identidade. As pastas são lidas em ordem "
          "cronológica: “07-2026”, “08-2026” viram 202607, 202608 e o mais recente "
          "prevalece.",
          "Bases (link “Arquivos importados”) → grupo Diretório (AD).",
          "Franqueados, prestadores e desligados do AD carregados; alimentam a "
          "validação por espelho (regras 2.4).")

    # ---------------- 2. validacao ----------------
    doc.add_page_break()
    h1(doc, "2. Validação do acesso — o que a pessoa deveria ter")
    par(doc,
        "Aqui o sistema compara o que a pessoa TEM com o que ela DEVERIA ter, e "
        "emite um dos vereditos: Aderente (bate), Incluir Acesso (falta), Alterar "
        "Perfil (errado) ou Em Análise (não dá para decidir sozinho). O que muda "
        "de regra para regra é COMO se descobre o “deveria ter”.")

    regra(doc, "2.1", "Matriz de perfis por cargo",
          "O perfil esperado, quando existe matriz para o cargo.",
          "Chave: centro de custo + cargo. É a regra principal — as demais são "
          "usadas quando esta não alcança a pessoa.",
          "Pendências → coluna Origem = MATRIZ.",
          "2.249 validações. Matriz carregada: SYSTUR 6.580 linhas · Oracle 3.682 · "
          "SICA RA 206 · SIGOT 195 · SICA Esfera 106 · IC 67.")

    regra(doc, "2.2", "CCO — centro de custo + gestor",
          "O perfil esperado quando o cargo não está na matriz, mas o centro de "
          "custo e o gestor estão no mapeamento CCO/CSC.",
          "Chave: centro de custo + gestor. Aplicada ANTES da regra de “Em "
          "Análise”, senão sistemas sem dados de CCO virariam enxurrada de Em "
          "Análise falso.",
          "Pendências → coluna Origem = CCO.",
          "1.708 validações: SYSTUR 945 · SIGOT 349 · Oracle 266 · SICA RA 138 · "
          "SICA Esfera 10.")

    regra(doc, "2.3", "Espelho dinâmico do SIG",
          "O perfil esperado no SIG, que não tem matriz de cargo.",
          "Olha os COLEGAS da pessoa e considera padrão o perfil presente em pelo "
          "menos 70% deles. Grupo: centro de custo + gestor + cargo; se não houver "
          "gente suficiente, cai para centro de custo + gestor. Exige no mínimo "
          "2 colegas que usem o SIG — com menos, não há padrão que se sustente.",
          "Pendências → filtro Sistema = SIG; Origem = ESPELHO.",
          "654 validações. Veredito: Sem Acesso 289 · Em Análise 280 · Aderente 215 · "
          "Alterar 15.")
    nota(doc,
         "Os 70% e o mínimo de 2 colegas são parâmetros — mudar o número muda "
         "quantas pendências o SIG gera. É a regra que mais depende do seu "
         "julgamento.")

    regra(doc, "2.4", "Espelho de terceiros, franqueados e prestadores",
          "O perfil esperado de quem não tem cargo na estrutura da CVC.",
          "Mesma lógica de espelho (70%, mínimo 2 pares), com chave própria: "
          "terceiro espelha por empresa + supervisor; franqueado e prestador "
          "espelham por empresa + gestor do diretório. Vale em todos os sistemas.",
          "Pendências → coluna Origem começa com ESPELHO_.",
          "Franqueado 767 · prestador 644 · terceiro 163.")

    regra(doc, "2.5", "Limiar de inclusão — 30% de adesão",
          "Se a falta de um acesso vira pendência de “Incluir Acesso”.",
          "Só gera Incluir Acesso quando pelo menos 30% das pessoas daquele cargo "
          "já têm o acesso ao sistema. Abaixo disso a matriz provavelmente abrange "
          "demais, e cobrar inclusão inundaria a fila com ruído.",
          "É uma supressão: as linhas não aparecem.",
          "1.587 inclusões suprimidas por este critério.")
    nota(doc,
         "Parâmetro ajustável: 0% desliga a regra (tudo vira pendência). Se a CVC "
         "quiser cobrar inclusão mesmo em cargo de baixa adesão, é só baixar.")

    regra(doc, "2.6", "Sem grupo de comparação não vira pendência",
          "O que fazer quando não há como saber o esperado.",
          "Terceiro, franqueado ou prestador sem grupo-espelho com padrão não vira "
          "pendência. Sem par comparável, o sistema não tem base para afirmar que "
          "o acesso está errado — e acusar sem base gera retrabalho.",
          "É uma supressão: as linhas não aparecem.",
          "4.337 acessos nesta situação.")

    regra(doc, "2.7", "Dois ou mais perfis e nenhum aderente → Em Análise",
          "O veredito quando a pessoa tem acesso, mas nada bate com o esperado.",
          "Com 2+ acessos ou 2+ perfis esperados, vai para Em Análise (pode ser "
          "excesso ou ambiguidade, precisa de gente). Com exatamente 1 de cada e "
          "eles não casam, é Alterar Perfil — aí o erro é claro.",
          "Pendências → filtro Ação = “Em Análise”.",
          "Em Análise: SIG 280 · SYSTUR 63 · SIGOT 16 · SICA RA 10 · IC 10 · "
          "Oracle 6.")

    regra(doc, "2.8", "Perfil por aproximação (só IC)",
          "Como comparar o perfil do extrato com o da matriz no Integrador Contábil.",
          "O extrato traz “IC_CONSULTA” e a matriz traz “IC CONSULTA” — e a própria "
          "matriz é inconsistente internamente. Só no IC a comparação ignora "
          "underscore, espaço e caixa. Não se aplica ao SYSTUR, que já bate exato.",
          "IC: Aderente 48 · Sem Acesso 36 · Em Análise 10.",
          "Solução temporária, para ser removida quando a matriz for padronizada.")

    regra(doc, "2.9", "Status indefinido no extrato → Em Análise",
          "O que fazer quando o extrato não diz se a conta está ativa.",
          "Sem informação de status, o sistema não decide sozinho: manda para "
          "Em Análise em vez de assumir ativo (acusaria indevidamente) ou "
          "bloqueado (esconderia risco).",
          "Pendências → filtro Ação = “Em Análise”.",
          "10 resultados nesta situação.")

    # ---------------- 3. ciclo de vida ----------------
    doc.add_page_break()
    h1(doc, "3. Ciclo de vida — o que muda depois que a pessoa muda")
    par(doc,
        "As regras acima olham uma foto. Estas comparam fotos: o que acontece "
        "quando alguém sai da empresa ou muda de função.")

    regra(doc, "3.1", "Desligado com acesso ativo",
          "Acesso que continua existindo depois do desligamento.",
          "Cruza a base de desligados do RH com os extratos dos sistemas. Conta "
          "bloqueada não conta (regra 1.2) — já está revogada.",
          "Aba Desligados.",
          "19.309 divergências, sobre 29.831 desligados na base.")

    regra(doc, "3.2", "Transferido — detecção de movimentação",
          "Quem mudou de função e por isso precisa ter o acesso revisto.",
          "Compara cada carga de RH com a anterior e detecta mudança em cargo, "
          "centro de custo, departamento ou gestor. Só a mudança entre execuções "
          "é enxergada — por isso o histórico depende de rodar regularmente.",
          "Aba Transferidos; e o de/para de cada pessoa no detalhe.",
          "727 movimentações. O que mudou: gestor 372 · cargo 137 · centro de "
          "custo + departamento 60 · combinações 158.")

    regra(doc, "3.3", "Revalidação depois da transferência",
          "O que fazer com cada acesso de quem se moveu.",
          "Classifica cada acesso comparando o esperado ANTES e DEPOIS da "
          "mudança: MANTÉM (serve nas duas funções), SOBROU (servia na antiga, "
          "não serve na nova — é o que revogar), FALTA (a nova função exige e ela "
          "não tem), EXCESSO (não está em nenhum dos dois padrões).",
          "Aba Transferidos → detalhe da pessoa.",
          "Mantém 6.432 · Falta 4.064 · Excesso 1.953 · Sobrou 434.")
    nota(doc,
         "O “Sobrou” (434) é o número operacional desta aba: são os acessos que a "
         "transferência tornou desnecessários.")

    regra(doc, "3.4", "Perfil inválido",
          "Perfil que a pessoa tem e que não existe no que o cargo prevê.",
          "Compara o perfil encontrado com a lista de perfis esperados do cargo.",
          "Pendências → filtro Tipo.",
          "249 divergências: Oracle 184 · SYSTUR 43 · SIGOT 10 · SICA RA 7 · "
          "SICA Esfera 3 · IC 2.")

    # ---------------- 4. tratativa ----------------
    doc.add_page_break()
    h1(doc, "4. Tratativa e histórico — o que o analista registra")

    regra(doc, "4.1", "Motivo só na pendência",
          "Quais campos são obrigatórios ao tratar cada tipo de caso.",
          "Pendência exige motivo (lista fechada) + parecer. Desligado e "
          "transferido exigem só o parecer: no desligado o desfecho é sempre "
          "revogar, e no transferido o motivo repetiria o nome da aba — campo "
          "obrigatório de resposta única vira atrito, não informação.",
          "Botão Resolver, nas três abas.",
          "Motivos disponíveis: Exceção, Transferência de Área, Acesso Indevido "
          "(configuráveis em arquivo).")

    regra(doc, "4.2", "Chamado no Jira é opcional",
          "Se é preciso ter um chamado aberto para registrar a tratativa.",
          "Não é. O obrigatório é o que PROVA a tratativa (motivo e parecer); o "
          "número do chamado é referência externa e pode nem existir ainda. Antes "
          "o ticket era obrigatório, o que impedia registrar tratativa interna.",
          "Formulário de tratativa → bloco “Chamado no Jira (opcional)”.",
          "O botão “Abrir chamado no Jira” está visível e DESABILITADO — depende "
          "do formulário no Jira e de alinhamento da equipe.")

    regra(doc, "4.3", "Ciclo de vida do acesso",
          "Como um caso caminha da identificação até o encerramento.",
          "Pendência identificada → Resolvida → Aderente. Se a divergência "
          "reaparece num processamento seguinte, o caso REABRE e ganha um novo "
          "ciclo, em vez de sumir do histórico.",
          "Aba Histórico (trilha por sistema) e aba Aderentes.",
          "5.356 pares (pessoa, sistema) rastreados: 3.265 com pendência "
          "registrada, 2.714 já aderentes.")

    regra(doc, "4.4", "Quarentena",
          "Como tirar um caso da fila sem perdê-lo de vista.",
          "Envio com prazo em dias, título e motivo. No fim do prazo o caso "
          "volta sozinho para os pendentes. Pode ser aplicada à pessoa inteira, a "
          "um sistema ou a um acesso específico.",
          "Aba Quarentena.",
          "Nenhum caso em quarentena na base entregue (recurso disponível).")

    # ---------------- 5. leitura ----------------
    h1(doc, "5. Como ler os filtros")

    regra(doc, "5.1", "Filtro de sistema faz coisas diferentes em cada aba",
          "O que aparece quando se filtra por um sistema.",
          "Em Pendências, Aderentes e Histórico o filtro ISOLA: a pessoa entra se "
          "tiver algo naquele sistema, e só as linhas daquele sistema aparecem. Na "
          "Consulta ele escolhe QUEM aparece, mas a linha continua mostrando todos "
          "os acessos da pessoa — a Consulta é a visão completa do indivíduo.",
          "Painel lateral (Pendências) e funil no cabeçalho das colunas.",
          "Na Consulta, um aviso em destaque avisa disso sempre que houver filtro "
          "de sistema ativo.")

    # ---------------- 6. sem regra ----------------
    h1(doc, "6. O que ainda NÃO tem regra")
    par(doc,
        "Itens conhecidos e deliberadamente fora desta entrega. Estão aqui para "
        "que a ausência seja uma decisão, e não uma surpresa.")

    itens = [
        ("Perfil excessivo", "Quem tem MAIS acesso do que o cargo exige não é "
         "sinalizado quando o esperado também está presente: o veredito Aderente "
         "prevalece e esconde o extra. Só cai em Em Análise pela regra 2.7."),
        ("Abertura automática de chamado", "O botão existe e está desabilitado. "
         "Depende do formulário no Jira e de alinhamento da equipe."),
        ("Tempo de tratamento nesta base", "As pendências vindas da matriz "
         "nasceram hoje, então o aging da Visão Geral está achatado. Não é regra: "
         "é característica desta base de teste."),
        ("Terceiros", "A integração existe e está desligada por configuração "
         "nesta fase."),
    ]
    for tit, txt in itens:
        p = doc.add_paragraph(style="List Bullet")
        r = p.add_run(tit + " — ")
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = AZUL
        r2 = p.add_run(txt)
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = TEXTO

    # ---------------- 7. fecho ----------------
    doc.add_page_break()
    h1(doc, "7. Resumo para devolver")
    par(doc,
        "Se preferir responder tudo de uma vez, basta marcar abaixo as regras com "
        "as quais NÃO concorda e escrever o porquê. As demais ficam entendidas "
        "como aprovadas.")

    tbl = doc.add_table(rows=1, cols=3)
    tbl.style = "Table Grid"
    cab = ["Regra", "Concordo?", "Se não, o que deveria ser"]
    for i, txt in enumerate(cab):
        cel = tbl.rows[0].cells[i]
        cel.text = ""
        r = cel.paragraphs[0].add_run(txt)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(cel, "1F2D5C")
    tbl.rows[0].cells[0].width = Cm(3.0)
    tbl.rows[0].cells[1].width = Cm(2.6)
    tbl.rows[0].cells[2].width = Cm(10.9)
    for _ in range(10):
        c = tbl.add_row().cells
        c[0].width = Cm(3.0)
        c[1].width = Cm(2.6)
        c[2].width = Cm(10.9)

    doc.add_paragraph()
    nota(doc,
         "Toda regra deste documento é parâmetro ou critério que pode mudar. "
         "Alterações exigem um reprocessamento para os números refletirem a "
         "decisão.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"OK -> {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
