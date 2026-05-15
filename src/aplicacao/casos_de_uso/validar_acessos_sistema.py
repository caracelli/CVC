import unicodedata
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import pandas as pd
from loguru import logger

from dominio.objetos_valor.sistema import sistema_do_texto
from dominio.objetos_valor.status_validacao import StatusValidacao
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import AcessoSistema, RhAtivo
from infraestrutura.escritores_arquivos.escritor_parquet import EscritorParquet
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite


def _norm(s: str) -> str:
    if not s:
        return ""
    s = s.upper().strip()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


class ValidarAcessosSistema:

    def __init__(self, conexao: ConexaoBancoDados, pasta_parquet: str):
        self._conexao = conexao
        self._parquet = EscritorParquet()
        self._pasta_parquet = pasta_parquet
        self._repo_div = RepositorioDivergenciaSqlite(conexao)

    def executar(self):
        ativos, acessos_por_matricula, sistemas_com_dados, perfis_por_chave, cco = self._carregar_dados()

        registros: List[Dict] = []
        for func in ativos:
            cc = func.centro_custo_codigo or ""
            cargo_norm = _norm(func.cargo_descricao or "")
            chave = (cc, cargo_norm)

            regs_func: List[Dict] = []

            # Validação pelas matrizes de perfis (SYSTUR, SICA_RA, SIGOT, etc.)
            for sistema_valor, perfis in perfis_por_chave.get(chave, {}).items():
                regs_func.extend(
                    self._gerar_registros_sistema(
                        func, sistema_valor, perfis,
                        acessos_por_matricula, sistemas_com_dados, "MATRIZ",
                    )
                )

            # Validação pela matriz CCO
            for sistema_str, perfil_esperado in cco.get(chave, []):
                sistema_enum = sistema_do_texto(sistema_str)
                sistema_valor = sistema_enum.value if sistema_enum else sistema_str.upper()
                regs_func.extend(
                    self._gerar_registros_sistema(
                        func, sistema_valor, [(perfil_esperado, False)],
                        acessos_por_matricula, sistemas_com_dados, "CCO",
                    )
                )

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
        registros_acao = [r for r in registros if r["status"] in _STATUS_ACAO]

        repo = RepositorioMatrizSqlite(self._conexao)
        repo.salvar_validacoes(registros_acao)

        _STATUS_LABEL = {
            StatusValidacao.SEM_ACESSO.value:  "Incluir Acesso",
            StatusValidacao.DIVERGENTE.value:   "Alterar Perfil",
            StatusValidacao.EM_ANALISE.value:   "Em Análise",
        }

        df = pd.DataFrame(registros_acao)
        if not df.empty:
            df = df.astype({
                "matricula": "str",
                "cpf": "str",
                "nome": "str",
                "email": "str",
                "centro_custo_codigo": "str",
                "centro_custo_nome": "str",
                "cargo_codigo": "str",
                "cargo_descricao": "str",
                "sistema": "str",
                "perfil_esperado": "str",
                "perfil_atual": "str",
                "acesso_manual": "bool",
                "status": "str",
                "origem_matriz": "str",
            })
            df["acao"] = df["status"].map(_STATUS_LABEL).fillna("")

        # Adiciona ACESSO_SEM_VINCULO_RH como "Não Mapeado"
        nao_mapeados = [
            {
                "matricula": "", "cpf": "", "nome": d.nome_usuario or d.usuario,
                "email": "", "centro_custo_codigo": "", "centro_custo_nome": "",
                "cargo_codigo": "", "cargo_descricao": "",
                "sistema": d.sistema.value, "perfil_esperado": "",
                "perfil_atual": d.perfil_encontrado or "",
                "acesso_manual": False, "status": "NAO_MAPEADO",
                "origem_matriz": "", "acao": "Não Mapeado",
            }
            for d in self._repo_div.obter_todas()
            if d.tipo == TipoDivergencia.ACESSO_SEM_VINCULO_RH
        ]
        if nao_mapeados:
            df_nm = pd.DataFrame(nao_mapeados).astype({c: "str" for c in [
                "matricula","cpf","nome","email","centro_custo_codigo",
                "centro_custo_nome","cargo_codigo","cargo_descricao",
                "sistema","perfil_esperado","perfil_atual","status","origem_matriz","acao",
            ]})
            df_nm["acesso_manual"] = df_nm["acesso_manual"].astype("bool")
            df = pd.concat([df, df_nm], ignore_index=True)

        self._parquet.salvar_fixo(df, f"{self._pasta_parquet}/VALIDACAO", "validacao_acessos")
        logger.success(
            f"Validação de acessos concluída: {len(registros)} avaliados, "
            f"{len(registros_acao)} com ação pendente gravados."
        )

    # ------------------------------------------------------------------
    def _carregar_dados(self):
        with self._conexao.sessao() as sessao:
            ativos = sessao.query(RhAtivo).all()
            acessos_db = sessao.query(AcessoSistema).all()

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
            chave = (pe.cargo_codigo, _norm(pe.cargo_descricao))
            perfis_por_chave[chave][pe.sistema.value].append((pe.perfil, pe.acesso_manual))

        # (cc, funcao_norm) → lista de (sistema_str, perfil), sem duplicatas
        cco: Dict[Tuple[str, str], List[Tuple[str, str]]] = defaultdict(list)
        for r in repo.obter_cco():
            chave = (r["cc"], _norm(r["funcao"]))
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
        perfis: List[Tuple[str, bool]],
        acessos_por_matricula: Dict[str, List[Tuple[str, str]]],
        sistemas_com_dados: Set[str],
        origem_matriz: str,
    ) -> List[Dict]:
        base = self._registro_base(func)

        acessos_atuais = {
            perfil for sis, perfil in acessos_por_matricula.get(func.matricula, [])
            if sis == sistema_valor
        }

        # 2+ perfis possíveis → Em análise — uma linha por perfil para permitir expand no Power BI
        if len(perfis) > 1:
            perfil_atual = ", ".join(sorted(acessos_atuais)) if acessos_atuais else ""
            return [
                base | {
                    "sistema": sistema_valor,
                    "perfil_esperado": perfil,
                    "perfil_atual": perfil_atual,
                    "acesso_manual": bool(manual),
                    "status": StatusValidacao.EM_ANALISE.value,
                    "origem_matriz": origem_matriz,
                }
                for perfil, manual in {(p, m) for p, m in perfis}  # deduplica pares (perfil, manual)
            ]

        perfil_esperado, acesso_manual = perfis[0]

        if sistema_valor not in sistemas_com_dados:
            status = StatusValidacao.SEM_DADOS
            perfil_atual = ""
        elif not acessos_atuais:
            status = StatusValidacao.SEM_ACESSO
            perfil_atual = ""
        elif perfil_esperado in acessos_atuais:
            status = StatusValidacao.ADERENTE
            perfil_atual = perfil_esperado
        else:
            status = StatusValidacao.DIVERGENTE
            perfil_atual = ", ".join(sorted(acessos_atuais))

        return [base | {
            "sistema": sistema_valor,
            "perfil_esperado": perfil_esperado,
            "perfil_atual": perfil_atual,
            "acesso_manual": acesso_manual,
            "status": status.value,
            "origem_matriz": origem_matriz,
        }]
