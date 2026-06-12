import unicodedata
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from loguru import logger
from sqlalchemy import text

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


def _norm_perfil(p: str) -> str:
    """Normaliza nome de perfil para casamento aproximado: upper, sem acento,
    '_' -> espaco e espacos colapsados. Assim 'IC_CONSULTA' == 'IC CONSULTA '."""
    s = _norm(p).replace("_", " ")
    return " ".join(s.split())


class ValidarAcessosSistema:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao
        # regra temporaria de provavel desligamento (sobrescritos no fluxo real)
        self._aderentes_anteriores: Set[Tuple[str, str]] = set()
        self._prov_deslig = 0

    def executar(self):
        ativos, acessos_por_matricula, sistemas_com_dados, perfis_por_chave, cco = self._carregar_dados()
        self._prov_deslig = 0   # contador da regra temporaria de provavel desligamento

        registros: List[Dict] = []
        for func in ativos:
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

        _STATUS_ACAO = {
            StatusValidacao.SEM_ACESSO.value,
            StatusValidacao.DIVERGENTE.value,
            StatusValidacao.EM_ANALISE.value,
        }
        # Gravamos as pendencias (acao) E os OK (conforme). O OK aparece na grid
        # mas com situacao_acao='OK' — fora da contagem de pendencias.
        _STATUS_SALVOS = _STATUS_ACAO | {StatusValidacao.OK.value}
        registros_salvos = [r for r in registros if r["status"] in _STATUS_SALVOS]
        for r in registros_salvos:
            # Fase 1: pendencia nasce PENDENTE (ciclo PENDENTE→RESOLVIDO); OK nao
            # e' pendencia (nao entra no fluxo de resolucao).
            r["situacao_acao"] = ("OK" if r["status"] == StatusValidacao.OK.value
                                  else "PENDENTE")

        repo = RepositorioMatrizSqlite(self._conexao)
        repo.salvar_validacoes(registros_salvos)

        _n_ok = sum(1 for r in registros_salvos if r["status"] == StatusValidacao.OK.value)
        logger.success(
            f"Validação de acessos concluída: {len(registros)} avaliados, "
            f"{len(registros_salvos) - _n_ok} pendência(s) + {_n_ok} OK gravados."
        )
        if self._prov_deslig:
            logger.info(
                f"[regra temporaria] {self._prov_deslig} caso(s) 'foi aderente + 0 "
                f"acesso' retirado(s) como provavel DESLIGAMENTO (sai na fase de desligados)."
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

        # matricula → lista de (sistema_valor, perfil)
        acessos_por_matricula: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for a in acessos_db:
            if a.matricula_vinculada:
                acessos_por_matricula[a.matricula_vinculada].append((a.sistema, a.perfil or ""))

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

        # Dedup por NOME de perfil: a matriz pode ter linhas repetidas (mesmo
        # cargo+sistema+perfil). EM_ANALISE deve ser decidido pelo numero de
        # perfis DISTINTOS — sem isso, uma linha duplicada viraria 2 perfis e
        # marcaria EM_ANALISE indevido (escondendo ADERENTE/SEM_ACESSO).
        _vistos: Dict[str, Tuple[bool, str]] = {}
        for _p, _m, _o in perfis:
            if _p not in _vistos:
                _vistos[_p] = (_m, _o)
        perfis = [(p, m, o) for p, (m, o) in _vistos.items()]

        acessos_atuais = {
            perfil for sis, perfil in acessos_por_matricula.get(func.matricula, [])
            if sis == sistema_valor
        }

        # Casamento de perfil:
        #  - SEMPRE case-insensitive (+ acento/trim) via _norm: a matriz pode vir
        #    'Analista_M_C' e o extrato 'ANALISTA_M_C' — e' o mesmo perfil.
        #  - Para os sistemas em _SISTEMAS_PERFIL_APROXIMADO (hoje so o IC), tambem
        #    aproxima '_' <-> espaco (extrato usa '_', matriz usa espaco).
        aproximado = sistema_valor in _SISTEMAS_PERFIL_APROXIMADO

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
        # REGRA: vai pra Em Análise quando o cargo tem 2+ perfis ESPERADOS
        # (ambiguo) OU quando a pessoa TEM 2+ perfis no sistema e nenhum e'
        # aderente (perfil excessivo sem aderencia -> precisa analise humana).
        if len(perfis) > 1 or len(acessos_atuais) > 1:
            perfil_atual = ", ".join(sorted(acessos_atuais)) if acessos_atuais else ""
            return [
                base | {
                    "sistema": sistema_valor,
                    "perfil_esperado": perfil,
                    "perfil_atual": perfil_atual,
                    "acesso_manual": bool(manual),
                    "status": StatusValidacao.EM_ANALISE.value,
                    "origem_matriz": origem,
                }
                for perfil, manual, origem in {(p, m, o) for p, m, o in perfis}  # pares distintos
            ]

        # (sistema sem dados ja retornou SEM_DADOS la em cima)
        perfil_esperado, acesso_manual, origem_p = perfis[0]
        if not acessos_atuais:
            status = StatusValidacao.SEM_ACESSO
            perfil_atual = ""
        else:
            status = StatusValidacao.DIVERGENTE
            perfil_atual = ", ".join(sorted(acessos_atuais))

        return [base | {
            "sistema": sistema_valor,
            "perfil_esperado": perfil_esperado,
            "perfil_atual": perfil_atual,
            "acesso_manual": acesso_manual,
            "status": status.value,
            "origem_matriz": origem_p,
        }]
