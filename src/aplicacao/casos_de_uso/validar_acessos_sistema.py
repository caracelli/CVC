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

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao
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

    def executar(self):
        ativos, acessos_por_matricula, sistemas_com_dados, perfis_por_chave, cco = self._carregar_dados()
        self._prov_deslig = 0   # contador da regra temporaria de provavel desligamento
        self._inclusao_suprimida = 0
        self._espelho_sem_padrao = 0
        self._calc_adocao_cargo(ativos, acessos_por_matricula)   # B1

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
            for sistema_valor, perfis in perfis_por_chave.get(chave_matriz, {}).items():
                for perfil, manual in perfis:
                    if (sistema_valor, perfil) not in _vistos_sp:
                        _vistos_sp.add((sistema_valor, perfil))
                        perfis_sis[sistema_valor].append((perfil, manual, "MATRIZ"))
            for sistema_str, perfil_esperado in cco.get(chave_cco, []):
                sistema_enum = sistema_do_texto(sistema_str)
                sistema_valor = sistema_enum.value if sistema_enum else sistema_str.upper()
                # SIG NAO usa CCO: e' validado por ESPELHO dinamico (_validar_sig_espelho)
                if sistema_valor == Sistema.SIG.value:
                    continue
                if (sistema_valor, perfil_esperado) not in _vistos_sp:
                    _vistos_sp.add((sistema_valor, perfil_esperado))
                    perfis_sis[sistema_valor].append((perfil_esperado, False, "CCO"))

            for sistema_valor, perfis_comb in perfis_sis.items():
                regs_func.extend(self._gerar_registros_sistema(
                    func, sistema_valor, perfis_comb,
                    acessos_por_matricula, sistemas_com_dados,
                ))

            # Sem nenhum mapeamento em nenhuma matriz
            if not regs_func:
                regs_func.append(self._registro_base(func) | {
                    "sistema": "",
                    "perfil_esperado": "",
                    "perfil_atual": "",
                    "acesso_manual": False,
                    "status": StatusValidacao.NAO_MAPEADO.value,
                    "origem_matriz": "",
                })

            registros.extend(regs_func)

        # SIG: validacao por ESPELHO dinamico (so CLT; terceiros vao no proprio)
        registros.extend(self._validar_sig_espelho(
            ativos, acessos_por_matricula, sistemas_com_dados))
        # Populacoes SEM matriz de cargo (terceiro/franqueado/prestador):
        # ESPELHO em TODOS os sistemas, cada uma espelhando com os SEUS pares.
        for _vinculo in sorted(_VINCULOS_ESPELHO):
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
                r["status"] = StatusValidacao.EM_ANALISE.value
                # Guarda o PORQUE: sem isso a tela mostra uma linha com perfil
                # esperado == encontrado marcada como pendencia e o analista nao
                # tem como saber que o motivo e' o status da conta no extrato
                # (retorno da area, 10/08/2026).
                r["motivo_status"] = "CONTA_INDEFINIDA"
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

        # PENDENCIAS (acao): so DIVERGENTE e EM_ANALISE. SEM_ACESSO ("esperado")
        # deixou de ser pendencia (retorno Bruna): e' informativo, so na Consulta.
        _STATUS_ACAO = {
            StatusValidacao.DIVERGENTE.value,
            StatusValidacao.EM_ANALISE.value,
        }
        # Informativos (salvos, aparecem na Consulta, NAO contam pendencia):
        # OK (encontrados/aderentes) e SEM_ACESSO (esperados).
        _STATUS_INFO = {StatusValidacao.OK.value, StatusValidacao.SEM_ACESSO.value}
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
                f"acesso' retirado(s) como provavel DESLIGAMENTO (sai na fase de desligados)."
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
        if self._inclusao_suprimida:
            logger.info(
                f"[B1] {self._inclusao_suprimida} inclusao(oes) suprimida(s): cargo com "
                f"adesao < {self._LIMIAR_INCLUSAO:.0%} ao sistema (matriz abrangente demais)."
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
        for pe in repo.obter_perfis_esperados():
            chave = (_norm(pe.cargo_codigo), _norm(pe.cargo_descricao))
            perfis_por_chave[chave][pe.sistema.value].append((pe.perfil, pe.acesso_manual))

        # (cc, gestor_norm) → lista de (sistema_str, perfil), sem duplicatas.
        # A CCO casa por centro de custo + GESTOR (nao por funcao/cargo).
        cco: Dict[Tuple[str, str], List[Tuple[str, str]]] = defaultdict(list)
        for r in repo.obter_cco():
            chave = (_norm(r["cc"]), _norm(r.get("gestor", "")))
            entry = (r["sistema"], r["perfil"])
            if entry not in cco[chave]:
                cco[chave].append(entry)

        return ativos, acessos_por_matricula, sistemas_com_dados, perfis_por_chave, cco

    # ------------------------------------------------------------------
    # B1 — adesao de acesso por (sistema, cargo)
    # ------------------------------------------------------------------
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
        }

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
            return [base | {
                "sistema": sistema_valor,
                "perfil_esperado": p_ok,
                "perfil_atual": p_ok,
                "acesso_manual": bool(m_ok),
                "status": StatusValidacao.OK.value,
                "origem_matriz": o_ok,
            }]

        # REGRA TEMPORARIA (sai na fase de desligados): a pessoa JA foi aderente
        # neste sistema (tinha o acesso) e agora esta SEM NENHUM acesso ->
        # provavel DESLIGAMENTO. Nao gera pendencia. Se tiver sido engano, o
        # acesso e' reincluido no sistema e ela reaparece como Aderente no
        # proximo extrato (auto-corrige). Conta para o log auditavel.
        if not acessos_atuais and (func.matricula, sistema_valor) in self._aderentes_anteriores:
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
            if self._adocao(sistema_valor, cg) < self._LIMIAR_INCLUSAO:
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
                  if (getattr(f, "tipo_vinculo", "") or "").upper() not in _VINCULOS_ESPELHO]

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
                regs.append(self._reg_sig(f, esp_str, "", StatusValidacao.SEM_ACESSO))   # Incluir
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
            # perfis desse sistema por terceiro
            perfis_s: Dict[str, Set[str]] = defaultdict(set)
            for f in terceiros:
                for sis, p in acessos_por_matricula.get(f.matricula, ()):
                    if sis == sistema and p:
                        perfis_s[f.matricula].add(p)
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
                u = perfis_s.get(f.matricula, set())
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
                            regs.append(self._reg_terc(f, sistema, "", ", ".join(sorted(u)),
                                                       StatusValidacao.EM_ANALISE, origem))
                    continue
                esp = espelho(grupo)
                if not esp:
                    # grupo existe mas nao converge num padrao (>=LIMIAR): idem.
                    if usa:
                        self._espelho_sem_padrao += 1
                        if self._ESPELHO_SEM_PADRAO_GERA_PENDENCIA:
                            regs.append(self._reg_terc(f, sistema, "", ", ".join(sorted(u)),
                                                       StatusValidacao.EM_ANALISE, origem))
                    continue
                esp_str = ", ".join(sorted(esp))
                if not u:
                    regs.append(self._reg_terc(f, sistema, esp_str, "",
                                               StatusValidacao.SEM_ACESSO, origem))  # Incluir
                elif u - esp:
                    regs.append(self._reg_terc(f, sistema, esp_str, ", ".join(sorted(u)),
                                               StatusValidacao.EM_ANALISE, origem))    # Excesso
                elif esp - u:
                    regs.append(self._reg_terc(f, sistema, esp_str, ", ".join(sorted(u)),
                                               StatusValidacao.DIVERGENTE, origem))    # Alterar
                else:
                    regs.append(self._reg_terc(f, sistema, esp_str, ", ".join(sorted(u)),
                                               StatusValidacao.OK, origem))            # Aderente
        return regs
