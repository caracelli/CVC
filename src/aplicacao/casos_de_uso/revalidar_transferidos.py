"""Card 23 — revalidacao de acessos POS-TRANSFERENCIA.

O Card 22 detecta quem mudou de cargo/CC/departamento/gestor e marca TODOS os
acessos da pessoa como "revisar". Aqui cada acesso e' julgado: ele ainda faz
sentido na funcao/equipe NOVA, ou so fazia na ANTIGA?

Para responder, monta o "esperado" nos DOIS momentos, com o mesmo criterio que
a validacao normal usa em cada sistema:

  - sistemas com MATRIZ: perfis de (centro de custo, cargo) + CCO de
    (centro de custo, gestor);
  - SIG: nao tem matriz — o esperado e' o PADRAO DO GRUPO (espelho), perfil
    presente em >= _SIG_LIMIAR_ESPELHO dos colegas que usam SIG, agrupando por
    (CC, gestor, cargo) com fallback (CC, gestor) e minimo de 2 colegas.

O estado ANTERIOR vem da tabela `transferidos` (gravada pelo Card 22) — antes
dela esse dado era calculado e descartado, e esta revalidacao nao era possivel.

Para o grupo ANTIGO usamos quem esta HOJE naquela chave: sao os colegas que a
pessoa deixou para tras. E' a leitura honesta de "a equipe de onde ela saiu
tem esses perfis; a equipe onde ela entrou, nao".
"""
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from loguru import logger

from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema, _norm
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    AcessoSistema, RevalidacaoTransferidoModel, RhAtivo, TransferidoModel)
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite

MANTEM, SOBROU, EXCESSO, FALTA = "MANTEM", "SOBROU", "EXCESSO", "FALTA"

# Populacoes com espelho proprio (nao entram no espelho do SIG por cargo)
_VINCULOS_ESPELHO = {"TERCEIRO", "FRANQUEADO", "PRESTADOR"}
_MIN_PARES = 2


class RevalidarTransferidos:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao
        self._limiar = ValidarAcessosSistema._SIG_LIMIAR_ESPELHO

    # ------------------------------------------------------------------
    def executar(self) -> int:
        with self._conexao.sessao() as sessao:
            movimentos = sessao.query(TransferidoModel).all()
            if not movimentos:
                sessao.query(RevalidacaoTransferidoModel).delete()
                sessao.commit()
                logger.info("=== Revalidacao pos-transferencia: nenhum movimento ===")
                return 0
            dados = self._carregar(sessao)
            regs = []
            for t in movimentos:
                regs.extend(self._revalidar(t, *dados))
            sessao.query(RevalidacaoTransferidoModel).delete()
            for r in regs:
                sessao.add(RevalidacaoTransferidoModel(**r))
            sessao.commit()

        por_sit = defaultdict(int)
        for r in regs:
            por_sit[r["situacao"]] += 1
        logger.info(
            "=== Revalidacao pos-transferencia: "
            f"{por_sit[SOBROU]} acesso(s) sobraram da funcao anterior, "
            f"{por_sit[FALTA]} faltando na nova, "
            f"{por_sit[MANTEM]} mantidos, {por_sit[EXCESSO]} fora dos dois padroes ===")
        return por_sit[SOBROU] + por_sit[FALTA]

    # ------------------------------------------------------------------
    def _carregar(self, sessao):
        ativos = sessao.query(RhAtivo).all()
        acessos = defaultdict(lambda: defaultdict(set))     # mat -> sis -> perfis
        for a in sessao.query(AcessoSistema).all():
            if a.matricula_vinculada and a.perfil:
                acessos[a.matricula_vinculada][a.sistema].add(a.perfil)

        repo = RepositorioMatrizSqlite(self._conexao)
        matriz = defaultdict(lambda: defaultdict(set))      # (cc,cargo) -> sis -> perfis
        for pe in repo.obter_perfis_esperados():
            matriz[(_norm(pe.cargo_codigo), _norm(pe.cargo_descricao))][
                pe.sistema.value].add(pe.perfil)
        cco = defaultdict(lambda: defaultdict(set))         # (cc,gestor) -> sis -> perfis
        for r in repo.obter_cco():
            cco[(_norm(r["cc"]), _norm(r.get("gestor", "")))][r["sistema"]].add(r["perfil"])

        # grupos do espelho do SIG (so CLT, so quem usa SIG)
        sig = Sistema.SIG.value
        full, wide = defaultdict(list), defaultdict(list)
        for f in ativos:
            if (getattr(f, "tipo_vinculo", "") or "").upper() in _VINCULOS_ESPELHO:
                continue
            if acessos.get(f.matricula, {}).get(sig):
                cc, g, cg = (_norm(f.centro_custo_codigo), _norm(f.gestor or ""),
                             _norm(f.cargo_descricao or ""))
                full[(cc, g, cg)].append(f.matricula)
                wide[(cc, g)].append(f.matricula)
        return acessos, matriz, cco, full, wide

    # ------------------------------------------------------------------
    def _padrao_sig(self, mats, acessos, excluir) -> Tuple[Set[str], int]:
        mats = [m for m in mats if m != excluir]
        if len(mats) < _MIN_PARES:
            return set(), 0
        cont = defaultdict(int)
        for m in mats:
            for p in acessos.get(m, {}).get(Sistema.SIG.value, ()):
                cont[p] += 1
        return ({p for p, n in cont.items() if n / len(mats) >= self._limiar},
                len(mats))

    def _esperado_sig(self, cc, gestor, cargo, acessos, full, wide, excluir):
        p, n = self._padrao_sig(full.get((_norm(cc), _norm(gestor), _norm(cargo)), []),
                                acessos, excluir)
        if n:
            return p, n
        return self._padrao_sig(wide.get((_norm(cc), _norm(gestor)), []), acessos, excluir)

    def _esperado_matriz(self, cc, cargo, gestor, matriz, cco):
        out = defaultdict(set)
        for sis, ps in matriz.get((_norm(cc), _norm(cargo)), {}).items():
            out[sis] |= ps
        for sis, ps in cco.get((_norm(cc), _norm(gestor)), {}).items():
            # SIG nao usa CCO (e' espelho) — mesma excecao da validacao normal
            if sis and _norm(sis) != Sistema.SIG.value:
                out[sis] |= ps
        return out

    # ------------------------------------------------------------------
    def _revalidar(self, t, acessos, matriz, cco, full, wide) -> List[Dict]:
        sig = Sistema.SIG.value
        mat = t.matricula
        meus = acessos.get(mat, {})

        novo = self._esperado_matriz(t.centro_custo_atual, t.cargo_atual,
                                     t.gestor_atual, matriz, cco)
        velho = self._esperado_matriz(t.centro_custo_anterior, t.cargo_anterior,
                                      t.gestor_anterior, matriz, cco)
        sig_novo, n_depois = self._esperado_sig(t.centro_custo_atual, t.gestor_atual,
                                                t.cargo_atual, acessos, full, wide, mat)
        sig_velho, n_antes = self._esperado_sig(t.centro_custo_anterior, t.gestor_anterior,
                                                t.cargo_anterior, acessos, full, wide, mat)
        novo[sig] |= sig_novo
        velho[sig] |= sig_velho

        def _reg(sistema, perfil, situacao):
            espelho = sistema == sig
            return {"matricula": mat, "nome": t.nome or "", "sistema": sistema,
                    "perfil": perfil, "situacao": situacao,
                    "origem": "ESPELHO" if espelho else "MATRIZ/CCO",
                    "pares_antes": n_antes if espelho else None,
                    "pares_depois": n_depois if espelho else None}

        regs = []
        for sistema, perfis in meus.items():
            esp_n, esp_v = novo.get(sistema, set()), velho.get(sistema, set())
            # Sistema sem esperado em NENHUM dos dois momentos: a revalidacao nao
            # tem o que dizer (a regra geral ja trata). Nao inventamos veredito.
            if not esp_n and not esp_v:
                continue
            for perfil in sorted(perfis):
                if perfil in esp_n:
                    regs.append(_reg(sistema, perfil, MANTEM))
                elif perfil in esp_v:
                    regs.append(_reg(sistema, perfil, SOBROU))
                else:
                    regs.append(_reg(sistema, perfil, EXCESSO))
        # o que a funcao/equipe NOVA espera e a pessoa nao tem
        for sistema, esperados in novo.items():
            for perfil in sorted(esperados - meus.get(sistema, set())):
                regs.append(_reg(sistema, perfil, FALTA))
        return regs
