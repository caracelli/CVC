import unicodedata
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from loguru import logger
from sqlalchemy import text

from dominio.objetos_valor import situacao_conta as sit_conta
from dominio.objetos_valor.sistema import Sistema, sistema_do_texto
from dominio.objetos_valor.status_validacao import StatusValidacao
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import AcessoSistema, RhAtivo
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite
from infraestrutura.leitores_arquivos.leitor_base import (
    normalizar_nome_coluna as _nnc,
)
from infraestrutura.leitores_arquivos.leitor_matriz_franqueado import (
    cargos_por_perfil, perfis_de_excecao,
)
from dominio.servicos_dominio.servico_depara_cargo import derivar_depara


def _norm(s: str) -> str:
    if not s:
        return ""
    s = s.upper().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # colapsa espacos internos: 'ANALISTA  PL' == 'ANALISTA PL'
    return " ".join(s.split())


# Sistemas que casam perfil por APROXIMACAO (nao por string exata). Por
# enquanto so o IC: o extrato traz NM_GRUPO com underscore ('IC_CONSULTA') e
# a matriz traz 'IC CONSULTA' (com espaco) — alem de inconsistencia DENTRO da
# propria matriz ('IC_CADASTRO' x 'IC CADASTRO'). A normalizacao abaixo casa
# os dois. NAO aplicar ao SYSTUR (perfil = CD_GRUPO_SIGLA, ja bate exato e e'
# homologado). Solucao temporaria — rever quando o cliente padronizar a matriz.
_SISTEMAS_PERFIL_APROXIMADO = {Sistema.IC_INTEGRADOR_CONTABIL.value}

# Populacoes que NAO tem matriz de cargo e sao validadas por ESPELHO (cada uma
# com os SEUS pares): terceiros (base de RH) e as identidades do diretorio AD
# (franqueado/prestador). Decidido com a usuaria em 24/06 (terceiros) e
# 29/07/2026 (franqueado/prestador).
_VINCULOS_ESPELHO = {"TERCEIRO", "FRANQUEADO", "PRESTADOR"}

# Chave do espelho por populacao: (chave cheia, chave ampla de fallback).
# Terceiro: Empresa + Supervisor (o supervisor vem na coluna `departamento`).
# Franqueado/Prestador (AD): Empresa + Gestor (o "Manager" do diretorio).
_CHAVES_ESPELHO = {
    "TERCEIRO":   (("empresa", "departamento"), ("departamento",)),
    "FRANQUEADO": (("empresa", "gestor"), ("gestor",)),
    "PRESTADOR":  (("empresa", "gestor"), ("gestor",)),
}


def _norm_perfil(p: str) -> str:
    """Normaliza nome de perfil para casamento aproximado: upper, sem acento,
    '_' -> espaco e espacos colapsados. Assim 'IC_CONSULTA' == 'IC CONSULTA '."""
    s = _norm(p).replace("_", " ")
    return " ".join(s.split())


class ValidarAcessosSistema:

    # B1 (regra ajustavel — decidida 25/06): so gera INCLUSAO (SEM_ACESSO) quando
    # a ADESAO do cargo ao sistema for >= este limiar. Cargo onde quase ninguem
    # tem o acesso => a matriz provavelmente abrange demais => nao inunda
    # pendencia. Trocar o valor + reprocessar ajusta o rigor (0 desliga a regra).
    _LIMIAR_INCLUSAO = 0.30

    # Consistencia minima para aceitar uma equivalencia de cargo derivada do
    # uso (VENDEDOR == ATENDENTE). Mesmo 70% do espelho do SIG/terceiros.
    _FRANQ_LIMIAR_DEPARA = 0.70

    def __init__(self, conexao: ConexaoBancoDados,
                 excesso_gera_pendencia: bool = False,
                 pendente_vira_inclusao: bool = False,
                 matriz_franqueado=None,
                 multi_perfil_gera_pendencia: bool = False,
                 multi_perfil_sistemas=None,
                 multi_perfil_sistemas_fora=None,
                 limiar_inclusao: float = None,
                 ancora_systur_sistemas=None,
                 ancora_systur_isentos=None,
                 matriz_tem_precedencia: bool = True,
                 cco_pela_funcao: bool = True):
        self._conexao = conexao
        # Regras da matriz do franqueado (lista de RegraFranqueado). Vazio/None
        # = regra desligada e o franqueado segue so' no espelho, como antes de
        # 02/09 — a matriz e' um ARQUIVO do cliente, entao a ausencia dele nao
        # pode quebrar o processamento.
        self._matriz_franqueado = matriz_franqueado or []
        self._franq_aderentes = 0
        self._franq_divergentes = 0
        self._franq_excecao = 0
        self._franq_depara = {}
        # CONTA PENDENTE ('P'/vazio no extrato): False = "Em Analise" (o
        # comportamento de 10/08), True = "Incluir Acesso" com o perfil
        # liberavel (pedido da area em 31/08). E' flag porque muda o DESFECHO
        # de uma pendencia — voltar atras nao pode exigir build novo.
        self._pendente_vira_inclusao = bool(pendente_vira_inclusao)
        # PERFIL EXCESSIVO — ver _gerar_registros_sistema. Ligado, o excesso
        # deixa de ser informativo e vira pendencia (Em Analise). Default OFF:
        # a decisao (A "pelo menos o esperado" x B "exatamente o esperado") e'
        # de negocio e ainda nao foi tomada. Com OFF o excesso JA APARECE na
        # tela — so nao cobra acao.
        self._excesso_gera_pendencia = bool(excesso_gera_pendencia)
        self._excesso_casos = 0
        self._excesso_perfis = 0
        # MAIS DE UM PERFIL no mesmo sistema — ver _aplicar_mais_de_um_perfil.
        # Nao confundir com o excesso acima: aqui nao importa se a matriz preve
        # os dois perfis. A area (22/09/2026) decidiu que UM perfil por pessoa
        # por sistema e' o limite, entao a linha nao pode ficar Aderente.
        # Default False no construtor (quem chama sem a flag mantem o
        # comportamento antigo); em producao o config manda, e ele vem true.
        # Lista vazia de sistemas = TODOS.
        self._multi_perfil_gera_pendencia = bool(multi_perfil_gera_pendencia)
        self._multi_perfil_sistemas = {
            str(x).strip().upper() for x in (multi_perfil_sistemas or []) if str(x).strip()}
        # Sistemas em que ter varios perfis e' NORMAL — a regra nao se aplica.
        # ORACLE_EBS entrou em 23/09/2026, com a explicacao da area: "no oracle
        # cada perfil e' um acesso especifico ao sistema". Contar esses perfis
        # como "um a mais" transformava em pendencia quem tem exatamente o que
        # a funcao dela preve (caso medido: PRISCILA 90001455, 4 perfis Oracle,
        # todos da funcao "Atendimento a fornecedores CVC e VISUAL").
        self._multi_perfil_fora = {
            str(x).strip().upper() for x in (multi_perfil_sistemas_fora or [])
            if str(x).strip()}
        self._multi_perfil_casos = 0
        # LIMIAR DE INCLUSAO (B1) — ver a constante da classe. Passa a vir do
        # config; None mantem o valor historico de 25/06 (0,30), que e' o que
        # os testes exercitam. Em producao o config manda, e ele vem ZERO desde
        # 23/09/2026: a area pediu 100% do que a matriz mapeia.
        self._limiar_inclusao = (self._LIMIAR_INCLUSAO if limiar_inclusao is None
                                 else float(limiar_inclusao))
        # regra temporaria de provavel desligamento (sobrescritos no fluxo real)
        self._aderentes_anteriores: Set[Tuple[str, str]] = set()
        self._prov_deslig = 0
        # B1 — adesao por (sistema, cargo): preenchido em _calc_adocao_cargo
        self._tot_cargo: Dict[str, int] = {}
        self._tem_cargo_sis: Dict[Tuple[str, str], Set[str]] = {}
        self._inclusao_suprimida = 0
        # status da conta (preenchidos em _carregar_dados / executar)
        self._status_indefinido: Set[Tuple[str, str]] = set()
        # (matricula, sistema) que TEM conta no extrato, mas revogada
        # (BLOQUEADA/INATIVA). Nao e' acesso — mas a pessoa ja existe no
        # sistema, e a tela precisa dizer isso (ver _sem_acesso_explicado).
        self._conta_revogada: Set[Tuple[str, str]] = set()
        self._acessos_revogados = 0
        self._sem_acesso_explicado = 0
        self._forcado_analise = 0
        self._espelho_sem_padrao = 0
        # matriculas que SUMIRAM do arquivo de ativos mais recente (ver
        # _calc_desatualizados) — nao recebem a linha NAO_MAPEADO
        self._desatualizados: Set[str] = set()
        self._nao_map_desatualizado = 0
        # ANCORA NO PERFIL DO SYSTUR — ver _filtrar_pelo_perfil_systur.
        # Lista vazia = regra desligada (comportamento anterior a 23/09/2026).
        self._ancora_systur = {
            str(x).strip().upper() for x in (ancora_systur_sistemas or [])
            if str(x).strip()}
        # Perfis que NAO entram na conta da divergencia (corporativos, que
        # matriz nenhuma prescreve). Comparados por _norm, com casamento por
        # PREFIXO — 'CVC OIE BRASIL' pega as variacoes do mesmo acesso.
        self._ancora_systur_isentos = [
            _norm(x) for x in (ancora_systur_isentos or []) if str(x).strip()]
        # PRECEDENCIA DA MATRIZ sobre a CCO (usuario, 23/09/2026: "regra
        # primeiro matriz depois cco"). Ligada por padrao; o parametro existe
        # para MEDIR o efeito (A/B na base real) e para um teste poder
        # exercitar o comportamento anterior sem reescrever o motor.
        self._matriz_tem_precedencia = bool(matriz_tem_precedencia)
        # A CCO responde pela FUNCAO da pessoa, e nao por todas as funcoes
        # do gestor dela — ver o laco por pessoa. Ligado por padrao; chave
        # propria para medir o efeito e para a area poder recuar.
        self._cco_pela_funcao = bool(cco_pela_funcao)
        self._ancora_filtrados = 0      # linhas de esperado cortadas pelo filtro
        self._ancora_sem_systur = 0     # pessoas com acesso e sem perfil no SYSTUR
        self._ancora_divergentes = 0    # pessoas com acesso fora do que o SYSTUR preve

    def executar(self):
        ativos, acessos_por_matricula, sistemas_com_dados, perfis_por_chave, cco = self._carregar_dados()
        self._prov_deslig = 0   # contador da regra temporaria de provavel desligamento
        self._inclusao_suprimida = 0
        self._franq_aderentes = self._franq_divergentes = self._franq_excecao = 0
        self._excesso_casos = 0
        self._excesso_perfis = 0
        self._espelho_sem_padrao = 0
        # REGRA DO SIG (area, 23/09/2026): quem tem SIG pela CCO nao passa pelo
        # espelho — senao a mesma pessoa sairia duas vezes no sistema.
        self._sig_pela_cco: Set[str] = set()
        self._sig_inclusao_suprimida = 0
        # (matricula, sistema) -> esperado que sobreviveu ao filtro da ancora,
        # normalizado. Ver o comentario no laco por pessoa.
        self._ancora_esperado: Dict[Tuple[str, str], Set[str]] = {}
        # (matricula, sistema) que a matriz/CCO cobria ANTES do filtro
        self._ancora_tinha_mapa: Set[Tuple[str, str]] = set()
        self._ancora_filtrados = 0
        self._ancora_sem_systur = 0
        self._ancora_divergentes = 0
        self._ancora_nao_mapeado = 0
        # perfis da CCO descartados porque a MATRIZ ja' respondia pelo sistema
        self._cco_apos_matriz = 0
        # linhas da CCO descartadas por serem de OUTRA funcao do gestor
        self._cco_outra_funcao = 0
        # pessoas com acesso que a funcao DELA nao preve (a guarda acima)
        self._acesso_fora_da_funcao = 0
        self._calc_adocao_cargo(ativos, acessos_por_matricula)   # B1
        self._desatualizados = self._calc_desatualizados(ativos)
        self._nao_map_desatualizado = 0

        registros: List[Dict] = []
        for func in ativos:
            # Terceiro/Franqueado/Prestador NAO usam matriz/CCO nem o espelho do
            # SIG: tem caminho proprio (_validar_espelho_vinculo) em TODOS os
            # sistemas — nao tem cargo/CC na matriz para casar.
            if (getattr(func, "tipo_vinculo", "") or "").upper() in _VINCULOS_ESPELHO:
                continue
            cc = _norm(func.centro_custo_codigo or "")   # normaliza p/ casar com matriz/CCO
            # MATRIZ de perfis casa por (cc, cargo); CCO casa por (cc, GESTOR)
            # — o gestor desambigua qual subconjunto de funcoes do cc se aplica.
            chave_matriz = (cc, _norm(func.cargo_descricao or ""))
            chave_cco = (cc, _norm(getattr(func, "gestor", "") or ""))

            regs_func: List[Dict] = []
            # Junta MATRIZ + CCO num CONJUNTO UNICO de perfis esperados POR SISTEMA
            # (cada perfil carrega sua origem). Assim a regra "≥1 aderente -> OK"
            # enxerga matriz e cco JUNTOS — senao a pessoa fica OK pela matriz E
            # DIVERGENTE pela cco no mesmo run (bug). Dedup por (sistema, perfil);
            # a matriz tem precedencia (avaliada primeiro).
            perfis_sis: Dict[str, List[Tuple[str, bool, str]]] = defaultdict(list)
            _vistos_sp: Set[Tuple[str, str]] = set()
            # Sistemas em que a MATRIZ por cargo falou desta pessoa. Quando ela
            # fala, a CCO NAO entra naquele sistema — regra do usuario
            # (23/09/2026): "regra primeiro matriz depois cco"; e antes, em
            # 22/09: "a pessoa nao precisa ter as duas origens, quem nao tem
            # matriz tem cco". Ate aqui as duas eram SOMADAS e a matriz so'
            # vencia no empate de perfil, o que misturava dois catalogos e
            # inflava o esperado de quem ja' estava coberto pela matriz.
            # Medido em 23/09 na base de 15/09: 7 pessoas, 13 perfis da CCO,
            # todos no SYSTUR — as duas matrizes quase nao se sobrepoem.
            _sistemas_da_matriz: Set[str] = set()
            for sistema_valor, perfis in perfis_por_chave.get(chave_matriz, {}).items():
                for perfil, manual in perfis:
                    if (sistema_valor, perfil) not in _vistos_sp:
                        _vistos_sp.add((sistema_valor, perfil))
                        perfis_sis[sistema_valor].append((perfil, manual, "MATRIZ"))
                        _sistemas_da_matriz.add(sistema_valor)
            # (sistema, perfil) -> funcao da CCO, para carimbar a linha depois.
            # Fora do loop de geracao de proposito: `_gerar_registros_sistema`
            # trabalha com a tupla (perfil, manual, origem) em varios pontos, e
            # mudar a aridade dela por causa de um rotulo sairia caro.
            funcao_por_sp: Dict[Tuple[str, str], str] = {}
            # A FUNCAO DA PESSOA, lida do perfil que ela tem no SYSTUR.
            #
            # A CCO casa por (centro de custo, GESTOR) — nao por funcao. Um
            # gestor tem varias funcoes na equipe, e ate' 23/09/2026 a pessoa
            # recebia a UNIAO de todas elas. Retorno da area:
            #   "CCO esta vindo errado: com base na matriz o usuario nao pode
            #    ter acesso ao SIG (...) exemplo para Funcao a Receber 1"
            # Caso do documento: a matricula 34530984 tem A_RECEBER_1 no
            # SYSTUR, e a funcao "A Receber 1" NAO preve SIG — mas ela recebia
            # 14 perfis de SIG, vindos da funcao "A Receber 2 + SIG" do mesmo
            # gestor.
            #
            # Medido na base de 15/09: 2.929 linhas vinham de outra funcao
            # (SIG 2.244, SIGOT 336, SICA_RA 199, SICA_ESFERA 143, SYSTUR 7),
            # contra 806 da funcao certa. 196 pessoas.
            #
            # Quem NAO tem perfil no SYSTUR fica como estava: sem ele nao ha'
            # como saber a funcao, e filtrar tiraria toda a previsao de 1.034
            # linhas. Errar para o lado de mostrar demais, nao de esconder.
            _sis_filtrados: Set[str] = set()
            _funcoes_da_pessoa: Set[str] = set()
            if self._cco_pela_funcao:
                for _p in self._perfis_systur_de(func, acessos_por_matricula):
                    _funcoes_da_pessoa |= self._funcao_do_perfil_systur.get(_p, set())
            for sistema_str, perfil_esperado, _funcao in cco.get(chave_cco, []):
                sistema_enum = sistema_do_texto(sistema_str)
                # Sistema que o projeto nao conhece e' IGNORADO. A planilha da
                # CCO cita sistema fora do escopo; antes disso o nome cru virava
                # um "sistema" fantasma, que so' servia para ser descartado
                # depois, sem log nenhum.
                if sistema_enum is None:
                    continue
                sistema_valor = sistema_enum.value
                if _funcao:
                    funcao_por_sp.setdefault((sistema_valor, perfil_esperado), _funcao)
                # PRECEDENCIA: a matriz por cargo ja' respondeu por este
                # sistema — a CCO nao acrescenta. Ver _sistemas_da_matriz.
                if (self._matriz_tem_precedencia
                        and sistema_valor in _sistemas_da_matriz):
                    self._cco_apos_matriz += 1
                    continue
                # Linha de OUTRA funcao do mesmo gestor — ver acima. So' filtra
                # quando se sabe a funcao da pessoa E a linha diz de qual
                # funcao veio; na duvida, mantem.
                if (_funcoes_da_pessoa and _funcao
                        and _norm(_funcao) not in _funcoes_da_pessoa):
                    self._cco_outra_funcao += 1
                    _sis_filtrados.add(sistema_valor)
                    continue
                if (sistema_valor, perfil_esperado) not in _vistos_sp:
                    _vistos_sp.add((sistema_valor, perfil_esperado))
                    perfis_sis[sistema_valor].append((perfil_esperado, False, "CCO"))

            _prov_deslig_antes = self._prov_deslig
            _ps_systur = (self._perfis_systur_de(func, acessos_por_matricula)
                          if self._ancora_systur else set())
            for sistema_valor, perfis_comb in perfis_sis.items():
                if sistema_valor in self._ancora_systur:
                    # A matriz/CCO falava deste sistema para esta pessoa ANTES
                    # do filtro? E' o que separa "a matriz nao cobre voce"
                    # (nao mapeado) de "cobre, mas o seu perfil do SYSTUR nao
                    # autoriza" (divergencia). Ver _cobrar_ancora_systur.
                    self._ancora_tinha_mapa.add((func.matricula, sistema_valor))
                    perfis_comb = self._filtrar_pelo_perfil_systur(
                        sistema_valor, perfis_comb, chave_matriz,
                        funcao_por_sp, _ps_systur)
                    # GUARDA O CONJUNTO INTEIRO que sobrou. A cobranca nao pode
                    # relê-lo das linhas: a linha de ADERENTE grava um unico
                    # `perfil_esperado` (o que casou), nao os N previstos —
                    # medido em 23/09, ler dali derrubava o Aderente do Oracle
                    # de 169 para 32 pessoas, acusando de divergencia quem tem
                    # exatamente o que a funcao dela preve.
                    self._ancora_esperado[(func.matricula, sistema_valor)] = {
                        _norm(p) for p, _, _ in perfis_comb}
                    # Sobrou nada: o SYSTUR dela nao autoriza NADA neste
                    # sistema. Nao gera linha de esperado — o que ela porventura
                    # TENHA de acesso e' cobrado no passo de divergencia, que
                    # roda sobre os acessos e nao sobre a matriz.
                    if not perfis_comb:
                        continue
                regs_func.extend(self._gerar_registros_sistema(
                    func, sistema_valor, perfis_comb,
                    acessos_por_matricula, sistemas_com_dados,
                ))
            # NINGUEM SOME POR CAUSA DO FILTRO DE FUNCAO. Se a CCO so' falava
            # daquele sistema por OUTRA funcao, a pessoa fica sem esperado ali
            # — e, se ela TEM acesso, a linha inteira desaparecia e o acesso
            # sumia da tela. E' o mesmo cuidado do lado do Oracle
            # (_cobrar_ancora_systur). Medido em 23/09 na base de 15/09: 3
            # pares (2 pessoas), todos ja' pendencia antes; sem esta guarda
            # eles virariam invisiveis, que e' pior que a pendencia errada.
            for _s in _sis_filtrados:
                if _s not in sistemas_com_dados:
                    continue
                if any(r.get("sistema") == _s for r in regs_func):
                    continue
                _tem = {p for sis, p in acessos_por_matricula.get(func.matricula, ())
                        if sis == _s and p}
                if not _tem:
                    continue
                self._acesso_fora_da_funcao += 1
                regs_func.append(self._registro_base(func) | {
                    "sistema": _s,
                    "perfil_esperado": "",
                    "perfil_atual": ", ".join(sorted(_tem)),
                    "acesso_manual": False,
                    "status": StatusValidacao.EM_ANALISE.value,
                    "origem_matriz": "CCO",
                    "motivo_status": "ACESSO_FORA_DA_FUNCAO",
                })

            # Carimba a FUNCAO da CCO na linha (vazio quando o esperado veio da
            # matriz por cargo, que nao tem funcao).
            # A busca e' POR PERFIL, e o campo pode trazer VARIOS separados por
            # virgula (linha Aderente, desde 23/09). Procurar pela string
            # inteira nao acha nada: medido no mesmo dia, 685 linhas — 100% das
            # aderentes com mais de um previsto — perderam a funcao, e ela
            # sumiu do bloco "Funcoes previstas", que e' justamente o que a
            # area pediu em 17/09 ("qual a matriz de acessos, qual a funcao?").
            for _r in regs_func:
                _sis = _r.get("sistema")
                for _p in (_r.get("perfil_esperado") or "").split(","):
                    _f = funcao_por_sp.get((_sis, _p.strip()))
                    if _f:
                        _r["funcao"] = _f
                        break
            # A regra TEMPORARIA de provavel desligamento (linha ~600, retorna
            # [] quando a pessoa JA foi aderente e zerou o acesso) tem dono
            # proprio — "sai na fase de desligados" — e o teste
            # test_provavel_desligamento.py trava que ela produz ZERO linha,
            # nao um NAO_MAPEADO informativo. Sem este flag, o fallback abaixo
            # "vazaria" um NAO_MAPEADO por cima da regra de desligamento.
            _foi_provavel_desligamento = self._prov_deslig > _prov_deslig_antes

            # Sem nenhum mapeamento em nenhuma matriz — OU mapeamento existe mas
            # toda expectativa foi suprimida pela B1 (adesao < 30% em todo
            # sistema aplicavel). Achado de 09/09 (retorno da Bruna, "gente
            # ativa some da Consulta"): ate aqui, NAO_MAPEADO nunca era salvo
            # (fora de _STATUS_SALVOS), entao a pessoa ficava com ZERO linha em
            # QUALQUER lugar do painel — nem Consulta, nem Pendencias. Medido na
            # base dela: 6.747 de 13.638 ativos (49%) sem nenhuma linha. Agora
            # e' salvo como informativo (nao vira pendencia — ver _STATUS_INFO).
            # Quem SUMIU do arquivo de ativos mais recente nao ganha a linha
            # (usuario, 15/09: "todo mundo que sumiu") — senao um desligado que
            # ficou acumulado na rh_ativos apareceria como ativo sem mapeamento.
            if (not regs_func and not _foi_provavel_desligamento
                    and func.matricula in self._desatualizados):
                self._nao_map_desatualizado += 1
            elif not regs_func and not _foi_provavel_desligamento:
                regs_func.append(self._registro_base(func) | {
                    "sistema": "",
                    "perfil_esperado": "",
                    "perfil_atual": "",
                    "acesso_manual": False,
                    "status": StatusValidacao.NAO_MAPEADO.value,
                    "origem_matriz": "",
                    "motivo_status": "SEM_EXPECTATIVA_RELEVANTE",
                })

            if any(r.get("sistema") == Sistema.SIG.value for r in regs_func):
                self._sig_pela_cco.add(func.matricula)
            registros.extend(regs_func)

        # SIG: validacao por ESPELHO dinamico (so CLT; terceiros vao no proprio)
        registros.extend(self._validar_sig_espelho(
            ativos, acessos_por_matricula, sistemas_com_dados))
        # FRANQUEADO: matriz propria (cargo x tipo de loja).
        regs_franq = self._validar_franqueado_matriz(
            ativos, acessos_por_matricula, sistemas_com_dados)
        registros.extend(regs_franq)

        # Populacoes SEM matriz de cargo validadas por ESPELHO em TODOS os
        # sistemas, cada uma espelhando com os SEUS pares.
        #
        # FRANQUEADO SAI DO ESPELHO quando a matriz esta carregada. A area foi
        # explicita, duas vezes: em 31/08, "para franqueado nao tem a questao de
        # espelho"; e em 04/09, vendo linhas de franqueado com origem
        # "Espelho - franqueados", "e' para nao ter esse espelho de
        # franqueados". Antes disso o espelho ainda respondia pelo franqueado
        # SEM acesso — 260 linhas em que o perfil sugerido saia do palpite dos
        # colegas, exatamente o que ela nao quer para essa populacao.
        # Consequencia aceita: franqueado sem acesso deixa de receber sugestao
        # de inclusao. A matriz nao pode substitui-la (sem TIPO DE LOJA nao da'
        # para dizer QUAL perfil conceder), e inventar era o problema.
        vinculos_espelho = sorted(_VINCULOS_ESPELHO)
        if self._matriz_franqueado:
            vinculos_espelho = [v for v in vinculos_espelho if v != "FRANQUEADO"]
            self._avisar_franqueado_fora_da_matriz(ativos, acessos_por_matricula)
        for _vinculo in vinculos_espelho:
            registros.extend(self._validar_espelho_vinculo(
                ativos, acessos_por_matricula, sistemas_com_dados, _vinculo))

        # STATUS INDEFINIDO (extrato nao diz se a conta esta ativa: vazio ou
        # 'P'/pendente): NAO se assume ativo — o resultado daquele (matricula,
        # sistema) vira "Em Analise" para revisao humana. Vale para todos os
        # caminhos (matriz, CCO, espelho do SIG e espelho de terceiros).
        self._forcado_analise = 0
        for r in registros:
            if r["status"] in (StatusValidacao.OK.value, StatusValidacao.DIVERGENTE.value) \
                    and (r["matricula"], r["sistema"]) in self._status_indefinido:
                # FRANQUEADO nunca toma o ramo "vira inclusao" — achado da
                # auditoria de 08/09: com `pendente_vira_inclusao=True` (o
                # valor de producao desde 31/08) o ramo abaixo LIMPA
                # perfil_atual e escreve um motivo generico, apagando o
                # veredito da matriz (CARGO_NAO_AUTORIZA_PERFIL e' escalada de
                # privilegio real; virar "Incluir Acesso" faz a tela sugerir
                # CONCEDER um perfil que a pessoa ja tem indevidamente). O
                # comentario que dizia "medido em 02/09" so' era verdade se o
                # teste rodou com a flag desligada — nesta config (true) o
                # ramo nunca tinha sido combinado com o franqueado antes.
                if self._pendente_vira_inclusao and r.get("origem_matriz") != "MATRIZ_FRANQUEADO":
                    # RETORNO DA AREA (31/08/2026, "Testes 1.docx"), textual:
                    #   "Considerar apenas os acessos ativos: se a pessoa
                    #    estiver com acesso nesse status, inativo, bloqueado ou
                    #    P, e ela poder ter o acesso, trazer como a incluir e o
                    #    perfil que pode ser liberado para ela."
                    # O print que ela mandou junto e' exatamente o "?" do
                    # CONTA_INDEFINIDA, com a pergunta "os perfis estao iguais,
                    # nao deveria estar aderente?". Explicar nao bastou: ela
                    # quer OUTRO DESFECHO. Bloqueado/inativo ja saiam como
                    # "Incluir Acesso" (CONTA_BLOQUEADA); faltava o 'P'.
                    # Medido em 31/08 no E2E dos 7 sistemas: 11 linhas.
                    r["status"] = StatusValidacao.SEM_ACESSO.value
                    # O perfil LIBERAVEL e' o esperado. O que ela tem hoje sai
                    # do campo porque a conta nao esta ativa — afirmar posse
                    # seria o mesmo defeito do perfil excessivo ao contrario.
                    r["perfil_atual"] = ""
                    r["motivo_status"] = "CONTA_PENDENTE"
                else:
                    r["status"] = StatusValidacao.EM_ANALISE.value
                    # Guarda o PORQUE: sem isso a tela mostra uma linha com perfil
                    # esperado == encontrado marcada como pendencia e o analista nao
                    # tem como saber que o motivo e' o status da conta no extrato
                    # (retorno da area, 10/08/2026).
                    # PRESERVA o motivo que a regra ja tinha escrito. Sem isso,
                    # um franqueado com perfil que o cargo NAO autoriza — ou com
                    # perfil de excecao da Governanca — perde o achado e vira
                    # so' "CONTA_INDEFINIDA" na tela. Medido em 02/09 na base do
                    # cliente: o extrato SYSTUR de abril nao traz status, e os
                    # 4.843 resultados de franqueado saiam todos com o motivo
                    # trocado. O status continua sendo o da regra da area (nao
                    # se assume conta ativa); o que muda e' so' nao apagar o
                    # porque.
                    _antes = (r.get("motivo_status") or "").strip()
                    r["motivo_status"] = (
                        f"CONTA_INDEFINIDA | {_antes}" if _antes else "CONTA_INDEFINIDA")
                self._forcado_analise += 1

        # CONTA BLOQUEADA: a pessoa TEM conta no sistema, mas revogada — pela
        # regra da area (22/07) conta bloqueada nao e' acesso, entao o resultado
        # sai como SEM_ACESSO ("Incluir Acesso"). Sem explicar isso, a tela
        # mostra o login dela preenchido e manda CRIAR um acesso que ja existe;
        # a acao certa e' DESBLOQUEAR. Mesmo defeito de transparencia do
        # CONTA_INDEFINIDA (retorno da area, 10/08 e 25/08/2026): a regra nao
        # muda, so passa a se explicar.
        self._sem_acesso_explicado = 0
        for r in registros:
            if r["status"] == StatusValidacao.SEM_ACESSO.value                     and not (r.get("perfil_atual") or "").strip()                     and (r["matricula"], r["sistema"]) in self._conta_revogada:
                r["motivo_status"] = "CONTA_BLOQUEADA"
                self._sem_acesso_explicado += 1

        # MAIS DE UM PERFIL no mesmo sistema (retorno da area, 22/09/2026,
        # textual): "Mais de um perfil nao pode ficar nada como aderente, ele
        # precisa vir como pendencia para analise".
        #
        # NAO e' o perfil excessivo. O excessivo pergunta "a matriz preve este
        # acesso?"; esta regra pergunta "quantos perfis ela tem?" — e a
        # resposta so' pode ser um. Uma pessoa com DOIS perfis que a matriz
        # preve nao tem excesso nenhum e, ate aqui, saia Aderente.
        #
        # Roda como PASSO SOBRE OS REGISTROS, e nao dentro de cada regra, de
        # proposito: os perfis chegam por quatro caminhos (matriz por cargo,
        # CCO, espelho do SIG e espelho de terceiros/franqueado) e todos eles
        # terminam com a mesma pergunta. Um passo so' nao tem como esquecer um
        # caminho — e passa a valer sozinho para um caminho novo.
        #
        # So' mexe em quem esta OK: DIVERGENTE e EM_ANALISE ja' sao pendencia
        # (mudar o motivo delas apagaria o achado da regra que as gerou), e
        # SEM_ACESSO/NAO_MAPEADO nao afirmam posse de perfil nenhum.
        #
        # Vem DEPOIS de CONTA_INDEFINIDA e CONTA_BLOQUEADA: quem tem a conta
        # inativa ja' saiu de OK e nao deve ser cobrada por perfil que nao
        # exerce.
        #
        # Conta perfis DISTINTOS pela mesma normalizacao do casamento (_norm, e
        # _norm_perfil nos sistemas de perfil aproximado): 'IC_CONSULTA' e
        # 'IC CONSULTA' sao o mesmo perfil, e contar os dois inventaria
        # pendencia — o mesmo cuidado que o dedup dos esperados ja' toma.
        #
        # Medido em 22/09/2026 na base de 15/09: 419 linhas Aderentes viram
        # pendencia (SIG 197, ORACLE_EBS 164, SYSTUR 58) e o total de
        # pendencias vai de 826 para 1.245.
        self._multi_perfil_casos = 0
        if self._multi_perfil_gera_pendencia:
            for r in registros:
                if r["status"] != StatusValidacao.OK.value:
                    continue
                sis = r.get("sistema") or ""
                if self._multi_perfil_sistemas and sis.upper() not in self._multi_perfil_sistemas:
                    continue
                if sis.upper() in self._multi_perfil_fora:
                    continue
                _k = (_norm_perfil if sis in _SISTEMAS_PERFIL_APROXIMADO else _norm)
                _perfis = {_k(x) for x in (r.get("perfil_atual") or "").split(",") if x.strip()}
                if len(_perfis) <= 1:
                    continue
                r["status"] = StatusValidacao.EM_ANALISE.value
                # PRESERVA o motivo anterior, igual ao CONTA_INDEFINIDA: a
                # linha pode ja' carregar PERFIL_EXCESSIVO ou o veredito da
                # matriz do franqueado, e esse porque nao pode se perder.
                _antes = (r.get("motivo_status") or "").strip()
                r["motivo_status"] = (
                    f"MAIS_DE_UM_PERFIL | {_antes}" if _antes else "MAIS_DE_UM_PERFIL")
                self._multi_perfil_casos += 1

        # ANCORA NO SYSTUR — cobranca. O filtro acima so' ESTREITA o esperado;
        # este passo olha para o lado do ACESSO e garante que ninguem some.
        # Roda por ultimo de proposito: precisa enxergar o veredito final das
        # outras regras para nao sobrescrever pendencia ja' achada.
        if self._ancora_systur:
            registros.extend(self._cobrar_ancora_systur(
                ativos, acessos_por_matricula, sistemas_com_dados, registros))

        # PENDENCIAS (acao): so DIVERGENTE e EM_ANALISE. SEM_ACESSO ("esperado")
        # deixou de ser pendencia (retorno Bruna): e' informativo, so na Consulta.
        _STATUS_ACAO = {
            StatusValidacao.DIVERGENTE.value,
            StatusValidacao.EM_ANALISE.value,
        }
        # Informativos (salvos, aparecem na Consulta, NAO contam pendencia):
        # OK (encontrados/aderentes), SEM_ACESSO (esperados) e NAO_MAPEADO (sem
        # expectativa relevante — ver comentario acima, achado de 09/09).
        _STATUS_INFO = {
            StatusValidacao.OK.value,
            StatusValidacao.SEM_ACESSO.value,
            StatusValidacao.NAO_MAPEADO.value,
        }
        _STATUS_SALVOS = _STATUS_ACAO | _STATUS_INFO
        registros_salvos = [r for r in registros if r["status"] in _STATUS_SALVOS]
        for r in registros_salvos:
            # Fase 1: pendencia nasce PENDENTE (ciclo PENDENTE→RESOLVIDO). OK e
            # SEM_ACESSO (esperado) nao sao pendencia (nao entram na resolucao).
            r["situacao_acao"] = ("PENDENTE" if r["status"] in _STATUS_ACAO
                                  else "OK")

        repo = RepositorioMatrizSqlite(self._conexao)
        repo.salvar_validacoes(registros_salvos)

        _n_pend = sum(1 for r in registros_salvos if r["status"] in _STATUS_ACAO)
        logger.success(
            f"Validação de acessos concluída: {len(registros)} avaliados, "
            f"{_n_pend} pendência(s) + {len(registros_salvos) - _n_pend} "
            f"informativo(s) (OK/esperado) gravados."
        )
        if self._prov_deslig:
            logger.info(
                f"[regra temporaria] {self._prov_deslig} caso(s) 'foi aderente + 0 "
                f"acesso' + FORA do arquivo de ativos mais recente retirado(s) como "
                f"provavel DESLIGAMENTO (sai na fase de desligados)."
            )
        if self._acessos_revogados or self._forcado_analise:
            logger.info(
                f"[status] {self._acessos_revogados} acesso(s) ignorado(s) por conta "
                f"BLOQUEADA/INATIVA (ja revogada) e {self._forcado_analise} resultado(s) "
                f"levado(s) a 'Em Análise' por status INDEFINIDO no extrato."
            )
        if self._sem_acesso_explicado:
            logger.info(
                f"[status] {self._sem_acesso_explicado} 'sem acesso' explicado(s) "
                f"por CONTA BLOQUEADA (a conta existe no sistema, mas esta "
                f"revogada — a acao e' desbloquear, nao criar)."
            )
        if self._espelho_sem_padrao:
            logger.info(
                f"[espelho] {self._espelho_sem_padrao} acesso(s) de "
                f"terceiro/franqueado/prestador sem grupo-espelho com padrao — "
                f"NAO viraram pendencia (sem par comparavel para dizer o esperado)."
            )
        if self._multi_perfil_casos:
            _esc = (", ".join(sorted(self._multi_perfil_sistemas))
                    if self._multi_perfil_sistemas else "todos os sistemas")
            logger.info(
                f"[mais de um perfil] {self._multi_perfil_casos} resultado(s) que "
                f"seriam ADERENTES viraram pendencia (Em Analise) por ter mais de "
                f"um perfil no mesmo sistema — escopo: {_esc}. Regra da area de "
                f"22/09/2026; desligue em validacao/mais_de_um_perfil/gera_pendencia."
            )
        if self._sig_inclusao_suprimida:
            logger.info(
                f"[sig] {self._sig_inclusao_suprimida} inclusao(oes) de SIG NAO "
                f"geradas pelo espelho — regra da area de 23/09/2026: no SIG, "
                f"quem diz o que a pessoa DEVERIA ter e' so' a matriz CCO. Quem "
                f"TEM acesso continua sendo validado normalmente."
            )
        if self._excesso_casos:
            _modo = ("como PENDENCIA (Em Analise)" if self._excesso_gera_pendencia
                     else "so' INFORMATIVO (segue Aderente) — ligar em "
                          "validacao/perfil_excessivo/gera_pendencia p/ cobrar")
            logger.info(
                f"[excesso] {self._excesso_casos} caso(s) com perfil ALEM do "
                f"esperado, somando {self._excesso_perfis} perfil(is) extra(s); "
                f"{_modo}."
            )
        if self._franq_aderentes or self._franq_divergentes or self._franq_excecao:
            logger.info(
                f"[franqueado] matriz de lojas: {self._franq_aderentes} aderente(s), "
                f"{self._franq_divergentes} perfil(is) que o cargo NAO autoriza, "
                f"{self._franq_excecao} perfil(is) de EXCECAO (dependem de aval da "
                f"Governanca de SI). A matriz valida ADERENCIA — nao gera inclusao, "
                f"porque o tipo de loja nao existe no cadastro. Franqueado NAO "
                f"passa pelo espelho (pedido da area em 31/08 e 04/09)."
            )
            if self._franq_depara:
                _amostra = sorted(self._franq_depara.values(),
                                  key=lambda e: -e.acessos)[:5]
                logger.info(
                    f"[franqueado] {len(self._franq_depara)} equivalencia(s) de cargo "
                    f"derivada(s) do uso (>={self._FRANQ_LIMIAR_DEPARA:.0%}): "
                    + "; ".join(e.descricao() for e in _amostra)
                )
        if self._nao_map_desatualizado:
            logger.info(
                f"[nao mapeado] {self._nao_map_desatualizado} pessoa(s) sem expectativa "
                f"que SUMIRAM do arquivo de ativos mais recente — sem linha "
                f"(nao aparecem como ativo)."
            )
        if self._inclusao_suprimida:
            logger.info(
                f"[B1] {self._inclusao_suprimida} inclusao(oes) suprimida(s): cargo com "
                f"adesao < {self._limiar_inclusao:.0%} ao sistema (matriz abrangente demais)."
            )

    # ------------------------------------------------------------------
    def _carregar_dados(self):
        with self._conexao.sessao() as sessao:
            ativos = sessao.query(RhAtivo).all()
            acessos_db = sessao.query(AcessoSistema).all()

            # REGRA TEMPORARIA (sai na fase de desligados): (matricula, sistema)
            # que JA foram aderentes — usado para tratar "foi aderente + agora 0
            # acesso" como provavel desligamento. Tabela pode nao existir em
            # banco antigo -> set vazio (sem efeito).
            self._aderentes_anteriores: Set[Tuple[str, str]] = set()
            try:
                self._aderentes_anteriores = {
                    (r[0], r[1]) for r in sessao.execute(text(
                        "SELECT matricula, sistema FROM ciclo_vida_acesso "
                        "WHERE dt_aderente IS NOT NULL")).fetchall()
                }
            except Exception:
                pass

        # matricula → lista de (sistema_valor, perfil). O STATUS da conta manda:
        # conta BLOQUEADA/INATIVA ja esta revogada, entao NAO e' acesso (regra da
        # area, 22/07) — antes disso a validacao ignorava o status e tratava uma
        # conta bloqueada como acesso vivo. Status INDEFINIDO (vazio, 'P') nao
        # assume ativo: o acesso conta, mas a validacao daquele (matricula,
        # sistema) sai como "Em Analise" para revisao humana.
        acessos_por_matricula: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self._status_indefinido: Set[Tuple[str, str]] = set()
        self._acessos_revogados = 0
        for a in acessos_db:
            if not a.matricula_vinculada:
                continue
            if sit_conta.sem_acesso_efetivo(a.situacao):
                self._acessos_revogados += 1
                self._conta_revogada.add((a.matricula_vinculada, a.sistema))
                continue
            acessos_por_matricula[a.matricula_vinculada].append((a.sistema, a.perfil or ""))
            if sit_conta.indefinida(a.situacao):
                self._status_indefinido.add((a.matricula_vinculada, a.sistema))

        # sistemas que têm registros de acesso no banco
        sistemas_com_dados: Set[str] = {a.sistema for a in acessos_db}

        repo = RepositorioMatrizSqlite(self._conexao)

        # (cc, cargo_norm) → {sistema_valor: [(perfil, acesso_manual)]}
        perfis_por_chave: Dict[Tuple[str, str], Dict[str, List[Tuple[str, bool]]]] = \
            defaultdict(lambda: defaultdict(list))
        # (sistema, cc, cargo_norm, perfil_norm) -> perfil do SYSTUR que a
        # matriz exige para aquela linha. Indice LATERAL de proposito: a tupla
        # de `perfis_por_chave` e' desempacotada em varios pontos do motor e
        # mudar a aridade dela por causa de um filtro sairia caro (mesmo
        # cuidado que `funcao_por_sp` ja' toma com a funcao da CCO).
        self._systur_da_linha: Dict[Tuple[str, str, str, str], Set[str]] = defaultdict(set)
        for pe in repo.obter_perfis_esperados():
            chave = (_norm(pe.cargo_codigo), _norm(pe.cargo_descricao))
            perfis_por_chave[chave][pe.sistema.value].append((pe.perfil, pe.acesso_manual))
            _ps = _norm(getattr(pe, "perfil_systur", "") or "")
            if _ps:
                self._systur_da_linha[
                    (pe.sistema.value, chave[0], chave[1], _norm(pe.perfil))].add(_ps)

        # (cc, gestor_norm) → lista de (sistema_str, perfil, funcao), sem duplicatas.
        # A CCO casa por centro de custo + GESTOR (nao por funcao/cargo), mas a
        # FUNCAO viaja junto: e' ela que a area usa para ler o esperado ("a
        # pessoa tem direito a funcao X; quais acessos formam a X?", 17/09/2026).
        cco: Dict[Tuple[str, str], List[Tuple[str, str, str]]] = defaultdict(list)
        # PONTE perfil do SYSTUR -> funcao. Ela mora dentro da PROPRIA CCO: as
        # linhas de sistema 'Systur' dao a traducao entre o nome tecnico do
        # perfil e o nome humano da funcao ('A_RECEBER_1' <-> 'A Receber 1',
        # 'ATD_FOR_CVC_VISUAL_CP' <-> 'Atendimento a fornecedores CVC e
        # VISUAL'). Sem ela as duas matrizes nao se falam: a do Oracle usa o
        # nome tecnico na coluna PERFIL SYSTUR e a CCO usa o nome humano na
        # coluna FUNCAO. Medido em 23/09/2026: 111 funcoes, 177 linhas.
        self._funcao_do_perfil_systur: Dict[str, Set[str]] = defaultdict(set)
        for r in repo.obter_cco():
            chave = (_norm(r["cc"]), _norm(r.get("gestor", "")))
            entry = (r["sistema"], r["perfil"], (r.get("funcao") or "").strip())
            if entry not in cco[chave]:
                cco[chave].append(entry)
            if sistema_do_texto(r["sistema"]) is Sistema.SYSTUR and r.get("funcao"):
                self._funcao_do_perfil_systur[_norm(r["perfil"])].add(_norm(r["funcao"]))

        return ativos, acessos_por_matricula, sistemas_com_dados, perfis_por_chave, cco

    # ------------------------------------------------------------------
    # B1 — adesao de acesso por (sistema, cargo)
    # ------------------------------------------------------------------
    # Abaixo desta fracao, o "arquivo mais recente" nao parece a base inteira
    # (export parcial/incremental) — ai' ninguem e' dado como sumido.
    _COBERTURA_MIN_ULTIMO_ARQUIVO = 0.5

    def _calc_desatualizados(self, ativos) -> Set[str]:
        """Matriculas que SUMIRAM do arquivo de ativos mais recente da sua
        populacao (CLT, terceiro, prestador...).

        A rh_ativos ACUMULA de proposito (merge, bc7af3e: "delete+insert
        apagaria os ausentes"), entao quem saiu da base continua gravado com o
        arquivo antigo em `arquivo_origem`. Medido em 15/09: os 79 CLT nessa
        situacao estavam TODOS na base de desligados. Decisao do usuario
        (15/09): quem sumiu nao recebe a linha NAO_MAPEADO.

        "Mais recente" = o `arquivo_origem` da linha com maior `dt_importacao`
        do vinculo. Sem data ou sem arquivo de origem, nao ha como saber:
        ninguem some. Se o mais recente cobre menos da metade da populacao,
        tambem ninguem some (e o log avisa) — protege contra um export parcial
        esconder metade das pessoas."""
        por_vinc: Dict[str, List] = defaultdict(list)
        for f in ativos:
            por_vinc[(getattr(f, "tipo_vinculo", "") or "FUNCIONARIO").upper()].append(f)
        fora: Set[str] = set()
        for vinc, fs in por_vinc.items():
            datados = [f for f in fs if getattr(f, "dt_importacao", None)]
            if not datados:
                continue
            ultimo = max(datados, key=lambda f: f.dt_importacao).arquivo_origem
            if not ultimo:
                continue
            sumiram = [f for f in fs
                       if getattr(f, "arquivo_origem", None) and f.arquivo_origem != ultimo]
            if len(fs) - len(sumiram) < len(fs) * self._COBERTURA_MIN_ULTIMO_ARQUIVO:
                logger.warning(
                    f"[ativos] {vinc}: o arquivo mais recente ('{ultimo}') cobre so' "
                    f"{len(fs) - len(sumiram)} de {len(fs)} — parece parcial; "
                    f"ninguem foi dado como fora da base.")
                continue
            fora.update(f.matricula for f in sumiram)
        return fora

    def _calc_adocao_cargo(self, ativos, acessos_por_matricula):
        """Por (sistema, cargo): quantos funcionarios do cargo REALMENTE tem
        acesso no sistema (numerador) vs total do cargo (denominador). Usado
        pela B1 para decidir se a Inclusao e' sinal real ou ruido de matriz."""
        cargo_de = {}
        self._tot_cargo = defaultdict(int)
        for f in ativos:
            if (getattr(f, "tipo_vinculo", "") or "").upper() == "TERCEIRO":
                continue
            cg = _norm(f.cargo_descricao or "")
            cargo_de[f.matricula] = cg
            self._tot_cargo[cg] += 1
        self._tem_cargo_sis = defaultdict(set)
        for mat, lst in acessos_por_matricula.items():
            cg = cargo_de.get(mat)
            if cg is None:
                continue
            for sis, _perfil in lst:
                self._tem_cargo_sis[(sis, cg)].add(mat)

    def _adocao(self, sistema: str, cargo_norm: str) -> float:
        """Fracao do cargo que tem acesso ao sistema. Sem base (cargo de 1
        pessoa, etc.) -> 1.0 para NAO bloquear (conservador)."""
        tot = self._tot_cargo.get(cargo_norm, 0)
        if tot < 2:          # cargo sem pares suficientes: nao da pra inferir ruido
            return 1.0
        return len(self._tem_cargo_sis.get((sistema, cargo_norm), ())) / tot

    def _registro_base(self, func: RhAtivo) -> Dict:
        return {
            "matricula": func.matricula,
            "cpf": func.cpf,
            "nome": func.nome,
            "email": func.email or "",
            "centro_custo_codigo": func.centro_custo_codigo or "",
            "centro_custo_nome": func.centro_custo_nome or "",
            "cargo_codigo": func.cargo_codigo or "",
            "cargo_descricao": func.cargo_descricao or "",
            "funcao": "",          # preenchido quando o esperado vem da CCO
        }

    # ------------------------------------------------------------------
    # ANCORA NO PERFIL DO SYSTUR (area, 23/09/2026)
    # ------------------------------------------------------------------
    # Textual: "ele so' pode ter os acessos oracle se o perfil bater com o
    # systur que ele tem; se no systur nao vier perfil e' pendencia systur; se
    # no oracle o perfil ou acesso divergir do systur e' pendencia oracle".
    #
    # E' um FILTRO sobre o esperado que ja' existia, nao uma fonte nova: o
    # conjunto continua vindo da matriz (cc+cargo) e da CCO (cc+gestor), e
    # depois perde as linhas que pertencem a um perfil do SYSTUR que a pessoa
    # nao tem. Feito assim de proposito — trocar a origem do esperado mudaria
    # o escopo de quem recebe linha de Oracle; filtrar so' pode ESTREITAR.
    #
    # As duas matrizes se ligam por caminhos diferentes:
    #   MATRIZ  — coluna PERFIL SYSTUR, nome tecnico, casa direto com o extrato.
    #   CCO     — coluna FUNCAO, nome humano; a traducao vem das linhas de
    #             'Systur' da propria CCO (ver _funcao_do_perfil_systur).
    # Linha sem nenhum dos dois campos NAO depende do SYSTUR e fica.
    def _perfis_systur_de(self, func, acessos_por_matricula) -> Set[str]:
        return {_norm(p) for s, p in acessos_por_matricula.get(func.matricula, ())
                if s == Sistema.SYSTUR.value and p}

    def _filtrar_pelo_perfil_systur(
        self,
        sistema_valor: str,
        perfis: List[Tuple[str, bool, str]],
        chave_matriz: Tuple[str, str],
        funcao_por_sp: Dict[Tuple[str, str], str],
        perfis_systur: Set[str],
    ) -> List[Tuple[str, bool, str]]:
        funcoes = set()
        for p in perfis_systur:
            funcoes |= self._funcao_do_perfil_systur.get(p, set())

        mantidos: List[Tuple[str, bool, str]] = []
        for perfil, manual, origem in perfis:
            exigido = self._systur_da_linha.get(
                (sistema_valor, chave_matriz[0], chave_matriz[1], _norm(perfil)))
            if exigido:
                if exigido & perfis_systur:
                    mantidos.append((perfil, manual, origem))
                else:
                    self._ancora_filtrados += 1
                continue
            _f = _norm(funcao_por_sp.get((sistema_valor, perfil), ""))
            if _f:
                if _f in funcoes:
                    mantidos.append((perfil, manual, origem))
                else:
                    self._ancora_filtrados += 1
                continue
            # nao diz a qual perfil do SYSTUR pertence: nao depende dele
            mantidos.append((perfil, manual, origem))
        return mantidos

    def _cobrar_ancora_systur(
        self, ativos, acessos_por_matricula, sistemas_com_dados, registros,
    ) -> List[Dict]:
        """Lado do ACESSO da regra da ancora. Duas cobrancas:

        1. tem acesso no sistema ancorado e NAO tem perfil no SYSTUR
           -> pendencia no SYSTUR ("se no systur nao vier perfil e' pendencia
           systur"). E' la' que esta' a falta: o Oracle dela so' pode ser
           julgado depois que o SYSTUR disser qual funcao ela exerce.

        2. tem acesso que o perfil do SYSTUR dela nao preve
           -> pendencia no proprio sistema ancorado.

        3. tem acesso e a matriz do sistema NAO COBRE o cargo/centro de custo
           dela -> linha informativa "Nao Mapeado" no proprio sistema.
           Pedido da area (Bruna) em 23/09/2026, sobre a matricula 1303:
           "tem o centro de custo dele mas nao tem o cargo no EBS, ai vai ter
           que vir o perfil que pode ter no systur e no ebs vir que nao esta
           mapeado, isso pode acontecer". Nao e' pendencia: nao ha o que
           cobrar de ninguem enquanto a matriz nao disser o que esse cargo
           pode ter. A falta que gera acao e' a do SYSTUR (caso 1).

        O caso 2 PRECISA criar linha quando o filtro zerou o esperado: sem
        isso a pessoa sairia do painel justamente por ter acesso que ninguem
        explica — o oposto do que a regra quer.
        """
        novos: List[Dict] = []
        por_mat = {f.matricula: f for f in ativos}
        # (matricula, sistema) -> linhas ja' existentes
        linhas: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
        for r in registros:
            linhas[(r.get("matricula"), r.get("sistema") or "")].append(r)

        for sistema_valor in sorted(self._ancora_systur):
            if sistema_valor not in sistemas_com_dados:
                continue
            for mat, func in por_mat.items():
                tem = {p for s, p in acessos_por_matricula.get(mat, ()) if s == sistema_valor and p}
                if not tem:
                    continue
                cobravel = {p for p in tem if not self._isento_da_ancora(p)}
                ps = self._perfis_systur_de(func, acessos_por_matricula)

                # CASO 3 — a matriz deste sistema nao cobre o cargo/CC dela.
                # Independe do SYSTUR: nao ha esperado nenhum para comparar, e
                # dizer "perfil fora do SYSTUR" seria acusar de divergencia
                # quem a matriz sequer menciona. Informativo, nao pendencia.
                if (mat, sistema_valor) not in self._ancora_tinha_mapa:
                    if not linhas[(mat, sistema_valor)]:
                        self._ancora_nao_mapeado += 1
                        novos.append(self._registro_base(func) | {
                            "sistema": sistema_valor,
                            "perfil_esperado": "",
                            "perfil_atual": ", ".join(sorted(tem)),
                            "acesso_manual": False,
                            "status": StatusValidacao.NAO_MAPEADO.value,
                            "origem_matriz": "ANCORA_SYSTUR",
                            "motivo_status": f"SEM_MAPEAMENTO_{sistema_valor}",
                        })
                    # o lado do SYSTUR (caso 1) continua valendo — e' a falta
                    # que gera acao. Nao ha' `continue` aqui de proposito.
                    if ps:
                        continue

                if not ps:
                    self._ancora_sem_systur += 1
                    alvo = [x for x in linhas[(mat, Sistema.SYSTUR.value)]
                            if x["status"] != StatusValidacao.EM_ANALISE.value]
                    motivo = f"SEM_PERFIL_SYSTUR_COM_{sistema_valor}"
                    if alvo:
                        # ja' tem linha de SYSTUR (tipicamente "incluir"):
                        # vira pendencia e ganha o porque, sem duplicar.
                        r = alvo[0]
                        r["status"] = StatusValidacao.EM_ANALISE.value
                        _antes = (r.get("motivo_status") or "").strip()
                        r["motivo_status"] = f"{motivo} | {_antes}" if _antes else motivo
                    else:
                        novos.append(self._registro_base(func) | {
                            "sistema": Sistema.SYSTUR.value,
                            "perfil_esperado": "",
                            "perfil_atual": "",
                            "acesso_manual": False,
                            "status": StatusValidacao.EM_ANALISE.value,
                            "origem_matriz": "ANCORA_SYSTUR",
                            "motivo_status": motivo,
                        })
                    continue

                esperado = self._ancora_esperado.get((mat, sistema_valor), set())
                sobra = {p for p in cobravel if _norm(p) not in esperado}
                if not sobra:
                    continue
                self._ancora_divergentes += 1
                motivo = "PERFIL_FORA_DO_SYSTUR"
                alvo = [x for x in linhas[(mat, sistema_valor)]
                        if x["status"] != StatusValidacao.EM_ANALISE.value]
                if alvo:
                    r = alvo[0]
                    r["status"] = StatusValidacao.EM_ANALISE.value
                    r["perfil_atual"] = ", ".join(sorted(tem))
                    _antes = (r.get("motivo_status") or "").strip()
                    r["motivo_status"] = f"{motivo} | {_antes}" if _antes else motivo
                elif not linhas[(mat, sistema_valor)]:
                    # o filtro zerou o esperado: cria a linha, senao some
                    novos.append(self._registro_base(func) | {
                        "sistema": sistema_valor,
                        "perfil_esperado": "",
                        "perfil_atual": ", ".join(sorted(tem)),
                        "acesso_manual": False,
                        "status": StatusValidacao.EM_ANALISE.value,
                        "origem_matriz": "ANCORA_SYSTUR",
                        "motivo_status": motivo,
                    })
        return novos

    def _isento_da_ancora(self, perfil: str) -> bool:
        """Acesso corporativo que matriz nenhuma prescreve e que a area nao
        quer ver como divergencia. Casa por PREFIXO."""
        p = _norm(perfil)
        return any(p.startswith(i) for i in self._ancora_systur_isentos)

    def _gerar_registros_sistema(
        self,
        func: RhAtivo,
        sistema_valor: str,
        perfis: List[Tuple[str, bool, str]],   # (perfil, acesso_manual, origem)
        acessos_por_matricula: Dict[str, List[Tuple[str, str]]],
        sistemas_com_dados: Set[str],
    ) -> List[Dict]:
        base = self._registro_base(func)

        # Casamento de perfil:
        #  - SEMPRE case-insensitive (+ acento/trim) via _norm: a matriz pode vir
        #    'Analista_M_C' e o extrato 'ANALISTA_M_C' — e' o mesmo perfil.
        #  - Para os sistemas em _SISTEMAS_PERFIL_APROXIMADO (hoje so o IC), tambem
        #    aproxima '_' <-> espaco (extrato usa '_', matriz usa espaco).
        aproximado = sistema_valor in _SISTEMAS_PERFIL_APROXIMADO
        _chave = _norm_perfil if aproximado else _norm

        # Dedup por NOME de perfil: a matriz pode ter linhas repetidas (mesmo
        # cargo+sistema+perfil). EM_ANALISE deve ser decidido pelo numero de
        # perfis DISTINTOS — sem isso, uma linha duplicada viraria 2 perfis e
        # marcaria EM_ANALISE indevido (escondendo ADERENTE/SEM_ACESSO).
        #
        # A chave e' a MESMA do casamento (_chave), nao a string crua. Retorno da
        # area (10/08/2026): a matriz tem o mesmo perfil grafado de dois jeitos
        # ('IC_CONSULTA' x 'IC CONSULTA', 'GERENTE REGIONAL' x 'GERENTE_REGIONAL'
        # — 17 grupos assim na base), e o dedup por string exata transformava
        # isso em "2 perfis esperados", inflando a lista de opcoes que a tela
        # mostra ("9 opcoes" e "8 opcoes" eram a MESMA lista). Regra: se dois
        # nomes casariam como o mesmo perfil na hora de aderir, sao o mesmo
        # perfil na lista de opcoes. Vence a primeira grafia vista (a matriz e'
        # avaliada antes da CCO).
        _vistos: Dict[str, Tuple[str, bool, str]] = {}
        for _p, _m, _o in perfis:
            k = _chave(_p)
            if k not in _vistos:
                _vistos[k] = (_p, _m, _o)
        perfis = list(_vistos.values())

        acessos_atuais = {
            perfil for sis, perfil in acessos_por_matricula.get(func.matricula, [])
            if sis == sistema_valor
        }

        def _adere(esperado: str) -> bool:
            if aproximado:
                alvo = _norm_perfil(esperado)
                return any(_norm_perfil(a) == alvo for a in acessos_atuais)
            alvo = _norm(esperado)
            return any(_norm(a) == alvo for a in acessos_atuais)

        # Sistema SEM nenhum dado de acesso no banco (fora de escopo / extrato
        # nao recebido): nao da pra validar -> SEM_DADOS (NAO gera pendencia).
        # Vem ANTES do EM_ANALISE: senao a CCO de sistemas sem dados (SIG, Oracle,
        # etc.) viraria enxurrada de EM_ANALISE falso.
        if sistema_valor not in sistemas_com_dados:
            return [base | {
                "sistema": sistema_valor,
                "perfil_esperado": perfis[0][0] if perfis else "",
                "perfil_atual": "",
                "acesso_manual": bool(perfis[0][1]) if perfis else False,
                "status": StatusValidacao.SEM_DADOS.value,
                "origem_matriz": perfis[0][2] if perfis else "",
            }]

        # REGRA OK (por sistema): se ha PELO MENOS UM perfil esperado aderente,
        # a linha vira OK (conforme) — oculta as demais opcoes e sai das
        # pendencias, mas APARECE na grid como OK. Vale tanto pra 1 perfil
        # esperado quanto pra varios (Em Analise resolvido).
        aderentes = [(p, m, o) for p, m, o in perfis if _adere(p)]
        if aderentes:
            p_ok, m_ok, o_ok = aderentes[0]

            # PERFIL EXCESSIVO — acesso que a pessoa TEM e que NENHUM perfil
            # esperado explica.
            #
            # Ate 28/08/2026 esta linha gravava `perfil_atual = p_ok` e pronto:
            # quem tinha o perfil esperado MAIS dez outros aparecia na tela como
            # "Aderente / perfil X" e os dez sumiam. Nao era so' falta de
            # pendencia — a tela AFIRMAVA o que a pessoa tem, e afirmava errado.
            # Medido nos 7 sistemas (ENTRADA 05/08): 196 pares (pessoa, sistema)
            # escondendo 2.153 perfis (ORACLE_EBS 148 · SYSTUR 47 · IC 1). Caso
            # real: matricula 1590, esperado 'CVC - HELP DESK DE DESPESAS COM
            # INTERNET', tem 10 a mais — entre eles 'CVC AP BRASIL MASTER'.
            #
            # Pedido da area no 1o retorno (29/07): "Acessos necessario analise
            # — acessos onde ele pode ter mais um perfil". `PERFIL_EXCESSIVO` ja'
            # existia no enum e no Excel desde sempre, sem nunca ser gerado.
            #
            # Duas coisas separadas, de proposito:
            #   VER    (sempre) - o extra entra em perfil_atual e a linha ganha
            #                     motivo_status='PERFIL_EXCESSIVO'. A Consulta
            #                     ja' renderiza a diferenca ("2 a mais: X, Y").
            #   COBRAR (flag)   - so' com excesso_gera_pendencia=True o status
            #                     vira EM_ANALISE. Ligar isso muda o numero de
            #                     pendencias que a area ve; e' decisao dela.
            #
            # Dedup por _chave, igual a lista de esperados acima: a matriz e o
            # extrato grafam o mesmo perfil de dois jeitos ('IC_CONSULTA' x
            # 'IC CONSULTA') e sem isso o mesmo acesso contaria como dois extras.
            #
            # OS OUTROS PERFIS QUE ELA TEM (22/09/2026) — ate aqui a linha so'
            # gravava `p_ok` + os extras NAO previstos. O perfil que ela TEM e
            # que a matriz PREVE, mas que nao foi o escolhido como `p_ok`,
            # sumia do campo: a tela dizia "tem 1 perfil" para quem tem dois.
            # E' o mesmo defeito do perfil excessivo pre-28/08 (a tela AFIRMA
            # posse, e afirmava errado), so' que do lado de dentro da matriz —
            # por isso nao aparecia: os dois perfis estavam "certos".
            # Medido em 22/09 na base de 15/09: 107 linhas escondiam um perfil
            # (ORACLE_EBS 59, SIG 33, SYSTUR 15). Caso real: matricula 14389,
            # SYSTUR, tem PARAMETROS_DE_CAIXA e N2_FINANCEIRO no MESMO login e
            # a tela mostrava so' PARAMETROS_DE_CAIXA.
            # Sem isso a regra de mais-de-um-perfil abaixo ficaria cega
            # justamente nos casos que a area levantou.
            esperados_k = {_chave(p) for p, _, _ in perfis}
            _k_ok = _chave(p_ok)
            _outros: Dict[str, str] = {}
            _ext: Dict[str, str] = {}
            for a in sorted(acessos_atuais):
                k = _chave(a)
                if k == _k_ok:
                    continue
                if k in esperados_k:
                    _outros.setdefault(k, a)
                elif k not in _ext:
                    _ext[k] = a
            outros = list(_outros.values())
            extras = list(_ext.values())

            # QUANTOS PERFIS A PESSOA PODE TER (area, 23/09/2026). Ate aqui a
            # linha Aderente gravava APENAS o perfil que casou, e a coluna
            # "Perfil Esperado" dizia UM para quem a matriz autoriza varios.
            # Retorno da area sobre a matricula 90001455: "Ela pode ter acesso
            # a 3 perfis do oracle e tem um so entao esta errado" — a CCO da'
            # 4 perfis a funcao dela ("Atendimento a fornecedores CVC e
            # VISUAL"), ela TEM os 4, e a tela mostrava so' 'CVC AP NOVA VISUAL
            # Consulta'. E' o mesmo defeito do perfil excessivo pre-28/08 e do
            # perfil_atual pre-22/09, agora na coluna do ESPERADO.
            #
            # VALE PARA AS DUAS ORIGENS. A regra do usuario — "para matriz ele
            # traz somente o que casa PARA INCLUIR, para cco precisa trazer
            # todos" — fala das linhas de INCLUSAO, que saem uma por perfil
            # esperado num ramo proprio, mais abaixo, e nao mudaram.
            #
            # Aqui e' outra coisa: este campo e' o que a tela compara contra o
            # que a pessoa TEM para dizer "falta X / tem Y a mais". Guardar so'
            # o perfil que casou faz a tela acusar como excesso tudo o que a
            # matriz preve e nao foi o escolhido.
            # Medido na validacao visual de 23/09/2026 — GILDA (34530435),
            # ANALISTA CUSTOS SR: o perfil INTERCOMPANY dela autoriza 47
            # acessos do Oracle, ela tem 42, dos quais 41 AUTORIZADOS e UM
            # fora (o relatorio de despesas). A tela dizia "41 a mais". Um
            # alarme falso de 41 para 1, na direcao que mais assusta.
            #
            # As linhas SEM_ACESSO / EM_ANALISE / DIVERGENTE ja' saem uma por
            # perfil esperado: o colapso so' existia no ramo Aderente.
            _esp: Dict[str, str] = {}
            for _p, _, _o in perfis:
                _esp.setdefault(_chave(_p), _p)
            esperado_txt = ", ".join(
                [p_ok] + [x for k, x in _esp.items() if k != _k_ok])

            reg = base | {
                "sistema": sistema_valor,
                "perfil_esperado": esperado_txt,
                "perfil_atual": ", ".join([p_ok] + outros + extras),
                "acesso_manual": bool(m_ok),
                "status": StatusValidacao.OK.value,
                "origem_matriz": o_ok,
            }
            if extras:
                self._excesso_casos += 1
                self._excesso_perfis += len(extras)
                reg["motivo_status"] = "PERFIL_EXCESSIVO"
                if self._excesso_gera_pendencia:
                    reg["status"] = StatusValidacao.EM_ANALISE.value
            return [reg]

        # REGRA TEMPORARIA (sai na fase de desligados): a pessoa JA foi aderente
        # neste sistema (tinha o acesso) e agora esta SEM NENHUM acesso ->
        # provavel DESLIGAMENTO. Nao gera pendencia. Se tiver sido engano, o
        # acesso e' reincluido no sistema e ela reaparece como Aderente no
        # proximo extrato (auto-corrige). Conta para o log auditavel.
        #
        # PRECISA TAMBEM TER SUMIDO do arquivo de ativos mais recente (usuario,
        # 15/09/2026: "se estao ativos e' porque ainda tem acesso, pode seguir
        # normalmente"). A regra nasceu em 12/06, quando NAO havia base de
        # desligados, e "perdeu o acesso" era a unica pista. Hoje ha' duas
        # melhores: a base de desligados e a presenca no arquivo de ativos.
        # Sem isso a regra escondia gente ATIVA: a area listou ADMILSON (1152) e
        # SILVIA (7550) entre os "ativos que nao vem na aplicacao" — ambos no RH
        # de 15/09, fora dos desligados e com conta Oracle ATIVA, mas sem o
        # SYSTUR que tinham em julho. O certo para eles e' "Incluir Acesso".
        if (not acessos_atuais
                and (func.matricula, sistema_valor) in self._aderentes_anteriores
                and func.matricula in self._desatualizados):
            self._prov_deslig += 1
            return []

        # Daqui pra baixo: NENHUM perfil esperado e' aderente.

        # SEM ACESSO no sistema: e' INFORMATIVO ("esperado"), NAO pendencia
        # (retorno da Bruna, Fase 1). A pessoa nao tem o acesso, mas o cargo
        # preve — isso NAO vai para Em Análise nem conta como pendencia; aparece
        # so na Consulta (bloco "Acessos esperados"). Lista TODOS os perfis
        # esperados para a Consulta mostrar o que ela poderia ter.
        if not acessos_atuais:
            # B1: cargo com adesao baixa ao sistema => matriz abrangente demais
            # => suprime (nao inunda a Consulta com esperados irrelevantes).
            cg = _norm(func.cargo_descricao or "")
            if self._adocao(sistema_valor, cg) < self._limiar_inclusao:
                self._inclusao_suprimida += 1
                return []
            return [
                base | {
                    "sistema": sistema_valor,
                    "perfil_esperado": perfil,
                    "perfil_atual": "",
                    "acesso_manual": bool(manual),
                    "status": StatusValidacao.SEM_ACESSO.value,
                    "origem_matriz": origem,
                }
                for perfil, manual, origem in {(p, m, o) for p, m, o in perfis}
            ]

        # TEM acesso, mas nenhum aderente:
        #  - 2+ acessos OU 2+ perfis esperados => Em Análise (excesso/ambiguidade,
        #    "pode ter um perfil a mais" — precisa analise humana);
        #  - 1 acesso e 1 esperado que nao casam => Divergente (perfil errado).
        if len(perfis) > 1 or len(acessos_atuais) > 1:
            perfil_atual = ", ".join(sorted(acessos_atuais))
            return [
                base | {
                    "sistema": sistema_valor,
                    "perfil_esperado": perfil,
                    "perfil_atual": perfil_atual,
                    "acesso_manual": bool(manual),
                    "status": StatusValidacao.EM_ANALISE.value,
                    "origem_matriz": origem,
                }
                for perfil, manual, origem in {(p, m, o) for p, m, o in perfis}
            ]

        perfil_esperado, acesso_manual, origem_p = perfis[0]
        return [base | {
            "sistema": sistema_valor,
            "perfil_esperado": perfil_esperado,
            "perfil_atual": ", ".join(sorted(acessos_atuais)),
            "acesso_manual": acesso_manual,
            "status": StatusValidacao.DIVERGENTE.value,
            "origem_matriz": origem_p,
        }]

    # ------------------------------------------------------------------
    # SIG — validacao por ESPELHO dinamico (decidido com a usuaria 24/06/2026)
    # ------------------------------------------------------------------
    _SIG_LIMIAR_ESPELHO = 0.70   # perfil "padrao" = presente em >=70% dos colegas que usam SIG

    def _reg_sig(self, func, perfil_esperado: str, perfil_atual: str,
                 status: StatusValidacao) -> Dict:
        return self._registro_base(func) | {
            "sistema": Sistema.SIG.value,
            "perfil_esperado": perfil_esperado,
            "perfil_atual": perfil_atual,
            "acesso_manual": False,
            "status": status.value,
            "origem_matriz": "ESPELHO",
        }

    def _validar_sig_espelho(
        self,
        ativos: List["RhAtivo"],
        acessos_por_matricula: Dict[str, List[Tuple[str, str]]],
        sistemas_com_dados: Set[str],
    ) -> List[Dict]:
        """SIG nao tem matriz por cargo nem usa CCO: o perfil esperado e'
        INFERIDO do proprio extrato (espelho). Agrupa por (CC+gestor+CARGO) com
        fallback (CC+gestor); o 'padrao' do grupo = perfis presentes em
        >=LIMIAR dos colegas que USAM o SIG (>=2 colegas exigidos).

        Por usuario (regra da usuaria 24/06):
          - tem o padrao, sem sobra            -> OK (Aderente)
          - nao tem SIG, mas os pares tem      -> SEM_ACESSO (Incluir)
          - tem perfil mas falta parte do padrao (sem excesso) -> DIVERGENTE (Alterar)
          - tem acesso ALEM do padrao (excesso) -> EM_ANALISE
          - grupo sem padrao / sem par         -> EM_ANALISE
        Excesso => Em Analise (governanca de acesso excessivo).
        """
        SIG = Sistema.SIG.value
        if SIG not in sistemas_com_dados:
            return []

        # SIG espelho e' so para CLT; terceiro/franqueado/prestador tem espelho
        # proprio (_validar_espelho_vinculo), que ja cobre o SIG — sem isso a
        # mesma pessoa sairia duas vezes no SIG.
        ativos = [f for f in ativos
                  if (getattr(f, "tipo_vinculo", "") or "").upper() not in _VINCULOS_ESPELHO
                  and f.matricula not in getattr(self, "_sig_pela_cco", ())]

        # mat -> set(perfis SIG) — so quem tem acesso ao SIG
        perfis_sig: Dict[str, Set[str]] = defaultdict(set)
        for mat, lst in acessos_por_matricula.items():
            for sis, perfil in lst:
                if sis == SIG and perfil:
                    perfis_sig[mat].add(perfil)

        def k_full(f):
            return (_norm(f.centro_custo_codigo or ""), _norm(getattr(f, "gestor", "") or ""),
                    _norm(f.cargo_descricao or ""))

        def k_wide(f):
            return (_norm(f.centro_custo_codigo or ""), _norm(getattr(f, "gestor", "") or ""))

        # colegas que USAM SIG por chave (definem o espelho)
        sig_full: Dict[Tuple, List[str]] = defaultdict(list)
        sig_wide: Dict[Tuple, List[str]] = defaultdict(list)
        for f in ativos:
            if perfis_sig.get(f.matricula):
                sig_full[k_full(f)].append(f.matricula)
                sig_wide[k_wide(f)].append(f.matricula)

        def espelho(mats: List[str]) -> Set[str]:
            n = len(mats)
            cont: Dict[str, int] = defaultdict(int)
            for m in mats:
                for p in perfis_sig.get(m, ()):
                    cont[p] += 1
            return {p for p, c in cont.items() if c / n >= self._SIG_LIMIAR_ESPELHO}

        regs: List[Dict] = []
        for f in ativos:
            u = perfis_sig.get(f.matricula, set())
            usa_sig = bool(u)
            # escolhe o grupo-espelho: >=2 colegas que usam SIG (cargo -> fallback gestor)
            if len(sig_full[k_full(f)]) >= 2:
                grupo = sig_full[k_full(f)]
            elif len(sig_wide[k_wide(f)]) >= 2:
                grupo = sig_wide[k_wide(f)]
            else:
                # sem par: so reporta se a propria pessoa usa SIG (senao SIG nao se aplica a ela)
                if usa_sig:
                    regs.append(self._reg_sig(f, "", ", ".join(sorted(u)),
                                              StatusValidacao.EM_ANALISE))
                continue

            esp = espelho(grupo)
            if not esp:
                if usa_sig:
                    regs.append(self._reg_sig(f, "", ", ".join(sorted(u)),
                                              StatusValidacao.EM_ANALISE))
                continue

            esp_str = ", ".join(sorted(esp))
            if not u:
                # REGRA DO SIG (area, 23/09/2026): o espelho NAO sugere mais
                # inclusao. Textual: "o SIG nao tem matriz, eu tiraria ele do
                # processo de inclusao, deixaria exclusivamente para o CCO (...)
                # tipo ele nao validar se a pessoa precisa ter, mas se alguem
                # tiver, ele fazer as validacoes que colocamos".
                # Quem esta na CCO ja' recebeu a inclusao no caminho normal e
                # nem chega aqui (_sig_pela_cco). Quem nao esta, e nao tem
                # acesso, deixa de receber sugestao tirada dos colegas.
                self._sig_inclusao_suprimida += 1
                continue
            elif u - esp:
                regs.append(self._reg_sig(f, esp_str, ", ".join(sorted(u)),
                                          StatusValidacao.EM_ANALISE))                    # Excesso
            elif esp - u:
                regs.append(self._reg_sig(f, esp_str, ", ".join(sorted(u)),
                                          StatusValidacao.DIVERGENTE))                    # Alterar
            else:
                regs.append(self._reg_sig(f, esp_str, ", ".join(sorted(u)),
                                          StatusValidacao.OK))                            # Aderente
        return regs

    # ------------------------------------------------------------------
    # FRANQUEADO — MATRIZ PROPRIA (cargo x tipo de atendimento x tipo de loja)
    # Pedido da area em 31/08: "para franqueado nao tem a questao de espelho".
    # ------------------------------------------------------------------
    # A matriz casa por CARGO + TIPO DE LOJA + TIPO DE ATENDIMENTO, e as duas
    # ultimas NAO EXISTEM no cadastro. Medido em 01/09/2026:
    # `rh_ativos.local_trabalho` 100% vazio (13.059 linhas) e
    # `acessos_sistemas.filial` do SYSTUR 100% vazio (6.754). `departamento`
    # traz o nome da loja ("6400 - SUZANO SHOPPING"), nao o tipo.
    #
    # Mas o NOME DO PERFIL codifica as duas: ATEND_PUBLIC_LJT_GERENTE_VC =
    # ATENDimento PUBLICo + Loja Terceirizada. Logo a regra so' fecha AO
    # CONTRARIO: nao da' para dizer, do cadastro, QUAL perfil a pessoa deveria
    # ter; da' para dizer, do perfil que ela TEM, se o CARGO dela o justifica.
    #
    # Consequencia deliberada: para franqueado esta regra valida ADERENCIA e
    # NAO gera INCLUSAO. Franqueado sem acesso, ou com perfil fora da matriz,
    # continua no espelho (_validar_espelho_vinculo) — por isso este metodo
    # devolve tambem as matriculas que tratou, para o espelho nao duplicar.
    _FRANQ_SISTEMA = Sistema.SYSTUR.value

    def _avisar_franqueado_fora_da_matriz(self, ativos, acessos_por_matricula):
        """Franqueado com acesso num sistema que a matriz NAO cobre.

        A area respondeu em 04/09/2026, fechando a pergunta: **franqueado so'
        pode ter acesso ao SYSTUR — por isso existe so' essa matriz, e nao vai
        haver caso fora dela.** Ou seja: isto NAO e' uma lacuna a preencher com
        outras matrizes, e nao precisa virar pendencia no painel.

        O aviso fica como verificacao de invariante, nada mais. Como o
        franqueado saiu do espelho, um acesso dele fora do SYSTUR nao seria
        julgado por caminho nenhum; se a premissa um dia falhar, isto e' o que
        impede o caso de sumir calado. Medido em 04/09 na base do cliente:
        ZERO — os 4.857 acessos de franqueado sao todos SYSTUR, exatamente como
        ela disse.
        """
        fora = defaultdict(int)
        for f in ativos:
            if (getattr(f, "tipo_vinculo", "") or "").upper() != "FRANQUEADO":
                continue
            for sis, p in acessos_por_matricula.get(f.matricula, ()):
                if sis != self._FRANQ_SISTEMA and p:
                    fora[sis] += 1
        if fora:
            detalhe = ", ".join(f"{s}: {n}" for s, n in sorted(fora.items()))
            logger.warning(
                f"[franqueado] {sum(fora.values())} acesso(s) de franqueado em "
                f"sistema(s) que a matriz NAO cobre ({detalhe}). Como o "
                f"franqueado saiu do espelho, esses acessos ficam SEM validacao. "
                f"A area afirmou em 04/09 que isso NAO acontece — se apareceu, "
                f"a premissa mudou e precisa ser levada a ela."
            )

    def _reg_franq(self, func, perfil_esperado: str, perfil_atual: str,
                   status: StatusValidacao, motivo: str) -> Dict:
        return self._registro_base(func) | {
            "sistema": self._FRANQ_SISTEMA,
            "perfil_esperado": perfil_esperado,
            "perfil_atual": perfil_atual,
            "acesso_manual": False,
            "status": status.value,
            "motivo_status": motivo,
            "origem_matriz": "MATRIZ_FRANQUEADO",
        }

    def _validar_franqueado_matriz(
        self,
        ativos: List["RhAtivo"],
        acessos_por_matricula: Dict[str, List[Tuple[str, str]]],
        sistemas_com_dados: Set[str],
    ) -> List[Dict]:
        """Valida o franqueado pela matriz de lojas.

        Com a matriz carregada o franqueado NAO passa mais pelo espelho (ver
        executar()), entao quem nao tem acesso, ou so' tem perfil fora da
        matriz, simplesmente nao gera registro — em vez de receber um perfil
        esperado inventado a partir dos colegas."""
        regras = self._matriz_franqueado or []
        if not regras or self._FRANQ_SISTEMA not in sistemas_com_dados:
            return []

        cpp = cargos_por_perfil(regras)
        excecoes = perfis_de_excecao(regras)
        if not cpp:
            return []

        # perfis que a matriz autoriza para cada cargo (para mostrar na
        # divergencia o que o cargo DARIA direito, em todas as combinacoes)
        perfis_do_cargo: Dict[str, Set[str]] = defaultdict(set)
        for r in regras:
            if not r.excecao:
                perfis_do_cargo[_nnc(r.cargo)].add(r.perfil)

        franqueados = [
            f for f in ativos
            if (getattr(f, "tipo_vinculo", "") or "").upper() == "FRANQUEADO"
            and _norm(f.situacao or "") in ("", "ATIVO")
        ]
        if not franqueados:
            return []

        # o que cada franqueado TEM no SYSTUR
        tem: Dict[str, Set[str]] = {}
        for f in franqueados:
            ps = {p for sis, p in acessos_por_matricula.get(f.matricula, ())
                  if sis == self._FRANQ_SISTEMA and p}
            if ps:
                tem[f.matricula] = ps

        # DE-PARA de cargo, derivado do uso destes mesmos acessos
        cargo_de: Dict[str, str] = {f.matricula: _nnc(f.cargo_descricao or "")
                                    for f in franqueados}
        pares = [(cargo_de.get(m, ""), _nnc(p))
                 for m, ps in tem.items() for p in ps]
        self._franq_depara = derivar_depara(
            pares, cpp, limiar=self._FRANQ_LIMIAR_DEPARA)

        regs: List[Dict] = []
        for f in franqueados:
            u = tem.get(f.matricula)
            if not u:
                continue          # sem acesso: a matriz nao prescreve — vai p/ o espelho
            cargo_rh = cargo_de.get(f.matricula, "")
            equiv = self._franq_depara.get(cargo_rh)
            cargo_efetivo = equiv.cargo_matriz if equiv else cargo_rh

            de_excecao = sorted(p for p in u if _nnc(p) in excecoes)
            da_matriz = [p for p in u if _nnc(p) in cpp]
            if not de_excecao and not da_matriz:
                continue          # nenhum perfil conhecido: deixa com o espelho

            nota_depara = ("; " + equiv.descricao()) if equiv else ""

            if de_excecao:
                # Nao e' "errado": e' liberacao que EXIGE aval formal. Vira
                # analise para a area conferir se a aprovacao existe.
                self._franq_excecao += len(de_excecao)
                regs.append(self._reg_franq(
                    f, "", ", ".join(sorted(u)), StatusValidacao.EM_ANALISE,
                    "PERFIL_EXCECAO_GOVERNANCA: %s - a matriz so' libera com "
                    "aprovacao da area de Governanca de Seguranca da Informacao%s"
                    % (", ".join(de_excecao), nota_depara)))
                continue

            nao_autorizados = sorted(
                p for p in da_matriz if cargo_efetivo not in cpp[_nnc(p)])
            if nao_autorizados:
                self._franq_divergentes += len(nao_autorizados)
                autoriza = ", ".join(sorted(perfis_do_cargo.get(cargo_efetivo, ()))) or "(nenhum)"
                regs.append(self._reg_franq(
                    f, autoriza, ", ".join(sorted(u)), StatusValidacao.DIVERGENTE,
                    "CARGO_NAO_AUTORIZA_PERFIL: o cargo '%s' nao consta na matriz "
                    "para %s%s" % (f.cargo_descricao or "(vazio)",
                                   ", ".join(nao_autorizados), nota_depara)))
            else:
                self._franq_aderentes += 1
                regs.append(self._reg_franq(
                    f, ", ".join(sorted(da_matriz)), ", ".join(sorted(u)),
                    StatusValidacao.OK,
                    "MATRIZ_FRANQUEADO: o cargo '%s' autoriza o perfil%s"
                    % (f.cargo_descricao or "(vazio)", nota_depara)))
        return regs

    # ------------------------------------------------------------------
    # TERCEIROS — ESPELHO por (Empresa+Supervisor), em TODOS os sistemas
    # (decidido com a usuaria 24/06/2026). Terceiros nao tem CC/cargo/gestor;
    # espelham entre TERCEIROS (nao com CLT). Supervisor = coluna `departamento`.
    # ------------------------------------------------------------------
    _TERC_LIMIAR_ESPELHO = 0.70

    # Grupo do espelho SEM padrao (sem par comparavel, ou os pares nao convergem
    # em >=LIMIAR): nao da' para afirmar o que era esperado. Medido em 30/07 na
    # base real: 4.187 dos 4.221 "Em Analise" de FRANQUEADO eram exatamente isso
    # (franqueado do SYSTUR nao tem par) — ruido que inunda a pendencia. Fica
    # como INFORMACAO (contador no log), nao como pendencia. Trocar para True
    # devolve o comportamento antigo.
    _ESPELHO_SEM_PADRAO_GERA_PENDENCIA = False

    def _reg_terc(self, func, sistema: str, perfil_esperado: str,
                  perfil_atual: str, status: StatusValidacao,
                  origem: str = "ESPELHO_TERC") -> Dict:
        return self._registro_base(func) | {
            "sistema": sistema,
            "perfil_esperado": perfil_esperado,
            "perfil_atual": perfil_atual,
            "acesso_manual": False,
            "status": status.value,
            "origem_matriz": origem,
        }

    def _validar_espelho_vinculo(
        self,
        ativos: List["RhAtivo"],
        acessos_por_matricula: Dict[str, List[Tuple[str, str]]],
        sistemas_com_dados: Set[str],
        vinculo: str,
    ) -> List[Dict]:
        """Populacao SEM matriz de cargo (terceiro/franqueado/prestador) validada
        por ESPELHO, aplicado a CADA sistema: agrupa pelos pares da MESMA
        populacao (chave cheia -> fallback ampla) e o 'padrao' do grupo sao os
        perfis presentes em >=LIMIAR dos colegas que USAM o sistema.

        Mesmas 4 saidas do SIG: Aderente / Inclusao(SEM_ACESSO) /
        Alteracao(DIVERGENTE) / Em Analise (excesso, grupo sem padrao ou sem par).
        """
        pop = [
            f for f in ativos
            if (getattr(f, "tipo_vinculo", "") or "").upper() == vinculo
            and _norm(f.situacao or "") in ("", "ATIVO")
        ]
        if not pop or not sistemas_com_dados:
            return []
        terceiros = pop     # nome curto usado no corpo abaixo
        campos_full, campos_wide = _CHAVES_ESPELHO.get(
            vinculo, (("empresa", "departamento"), ("departamento",)))
        origem = "ESPELHO_TERC" if vinculo == "TERCEIRO" else f"ESPELHO_{vinculo}"

        def _campo(f, nome):
            return _norm(getattr(f, nome, "") or "")

        def k_full(f):
            return tuple(_campo(f, c) for c in campos_full)

        def k_wide(f):
            return tuple(_campo(f, c) for c in campos_wide)

        regs: List[Dict] = []
        for sistema in sorted(sistemas_com_dados):
            # perfis desse sistema por terceiro, chaveados pela forma NORMALIZADA
            # (_norm: caixa, acento, espaco). Retorno da area em 09/09 ("Testes
            # 2.pdf"): 'gestao de acessos' x 'GESTAO DE ACESSOS' caia em Em
            # Analise como se fossem perfis diferentes — e ainda dividia a
            # contagem do espelho entre as duas grafias. O texto ORIGINAL segue
            # para a tela: o da propria pessoa no atual, o primeiro visto no grupo
            # no esperado.
            perfis_s: Dict[str, Dict[str, str]] = defaultdict(dict)
            rotulo: Dict[str, str] = {}
            for f in terceiros:
                for sis, p in acessos_por_matricula.get(f.matricula, ()):
                    if sis == sistema and p:
                        k = _norm(p)
                        perfis_s[f.matricula].setdefault(k, p)
                        rotulo.setdefault(k, p)
            # grupos de terceiros que USAM esse sistema (definem o espelho)
            full: Dict[Tuple, List[str]] = defaultdict(list)
            wide: Dict[Tuple, List[str]] = defaultdict(list)
            for f in terceiros:
                if perfis_s.get(f.matricula):
                    full[k_full(f)].append(f.matricula)
                    wide[k_wide(f)].append(f.matricula)
            if not full:
                continue   # nenhum terceiro usa esse sistema

            def espelho(mats: List[str]) -> Set[str]:
                n = len(mats)
                cont: Dict[str, int] = defaultdict(int)
                for m in mats:
                    for p in perfis_s.get(m, ()):
                        cont[p] += 1
                return {p for p, c in cont.items() if c / n >= self._TERC_LIMIAR_ESPELHO}

            for f in terceiros:
                u_map = perfis_s.get(f.matricula, {})
                u = set(u_map)                       # chaves normalizadas
                atual_str = ", ".join(sorted(u_map.values()))   # grafia dela
                usa = bool(u)
                if len(full[k_full(f)]) >= 2:
                    grupo = full[k_full(f)]
                elif len(wide[k_wide(f)]) >= 2:
                    grupo = wide[k_wide(f)]
                else:
                    # SEM PAR comparavel: nao da' para dizer o que era esperado.
                    # Isso NAO e' pendencia (retorno da area: nao inflar
                    # pendencia com ruido) — so conta no log.
                    if usa:
                        self._espelho_sem_padrao += 1
                        if self._ESPELHO_SEM_PADRAO_GERA_PENDENCIA:
                            regs.append(self._reg_terc(f, sistema, "", atual_str,
                                                       StatusValidacao.EM_ANALISE, origem))
                    continue
                esp = espelho(grupo)
                if not esp:
                    # grupo existe mas nao converge num padrao (>=LIMIAR): idem.
                    if usa:
                        self._espelho_sem_padrao += 1
                        if self._ESPELHO_SEM_PADRAO_GERA_PENDENCIA:
                            regs.append(self._reg_terc(f, sistema, "", atual_str,
                                                       StatusValidacao.EM_ANALISE, origem))
                    continue
                esp_str = ", ".join(sorted(rotulo[k] for k in esp))
                if not u:
                    # SIG fora da inclusao por espelho (area, 23/09/2026) — a
                    # mesma regra vale aqui: sem matriz, so' a CCO diz quem
                    # DEVERIA ter SIG.
                    if sistema == Sistema.SIG.value:
                        self._sig_inclusao_suprimida += 1
                        continue
                    regs.append(self._reg_terc(f, sistema, esp_str, "",
                                               StatusValidacao.SEM_ACESSO, origem))  # Incluir
                elif u - esp:
                    regs.append(self._reg_terc(f, sistema, esp_str, atual_str,
                                               StatusValidacao.EM_ANALISE, origem))    # Excesso
                elif esp - u:
                    regs.append(self._reg_terc(f, sistema, esp_str, atual_str,
                                               StatusValidacao.DIVERGENTE, origem))    # Alterar
                else:
                    regs.append(self._reg_terc(f, sistema, esp_str, atual_str,
                                               StatusValidacao.OK, origem))            # Aderente
        return regs
