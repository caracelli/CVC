import re
import uuid
from typing import List, Optional
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.funcionario_desligado import FuncionarioDesligado
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia
# Semantica do status e' UNICA no dominio (situacao_conta): uma conta bloqueada
# de um desligado NAO e' irregularidade de acesso — ja esta revogada. Ex.: o SIG
# traz ~58% das contas como BLOQUEADO.
from ..objetos_valor.situacao_conta import conta_ativa as _conta_ativa


def _norm_cpf(valor: Optional[str]) -> str:
    """CPF canonico p/ matching: 11 digitos (zfill preserva zeros a esquerda
    perdidos quando salvo como numero). Devolve '' quando nao da p/ casar com
    seguranca — !=11 digitos (parcial/mascarado/CNPJ) ou todos iguais
    (000...00 / 111...11, invalidos que colidiriam)."""
    d = re.sub(r"\D", "", valor or "")
    if not d:
        return ""
    p = d.zfill(11)
    if len(p) != 11 or len(set(p)) == 1:
        return ""
    return p


class RegraAcessoDesligado:
    """Detecta acesso ATIVO de funcionario desligado.

    Matching por UNIAO de chaves (mesma filosofia da cascata multi-chave da
    Fase 1): o acesso e' de um desligado se a MATRICULA vinculada, o CPF do
    extrato OU o LOGIN baterem com um desligado. Casar so por matricula subconta
    (o passo de vinculo cruza contra ATIVOS, entao o acesso de um desligado
    costuma ficar sem matricula anexada); o CPF do extrato fecha parte da lacuna
    e o LOGIN fecha o resto — e' a unica chave do OU_Desligados do diretorio AD,
    que nao tem matricula de RH. Uma linha que bate por varias chaves gera UMA
    divergencia (sem dobra).
    """

    def verificar(
        self,
        acessos: List[PerfilAcesso],
        desligados: List[FuncionarioDesligado],
    ) -> List[Divergencia]:
        matriculas_desligadas = {d.matricula for d in desligados if d.matricula}
        # CPF -> matricula do desligado (p/ preencher a matricula quando o match
        # veio so pelo CPF). Primeiro desligado vence em caso de CPF repetido.
        cpf_para_matricula = {}
        for d in desligados:
            c = _norm_cpf(d.cpf)
            if c and c not in cpf_para_matricula:
                cpf_para_matricula[c] = d.matricula
        # LOGIN (minusculo) -> matricula do desligado. Chave do AD.
        login_para_matricula = {}
        for d in desligados:
            lg = (getattr(d, "login", "") or "").strip().lower()
            if lg and lg not in login_para_matricula:
                login_para_matricula[lg] = d.matricula

        divergencias = []
        for acesso in acessos:
            # So conta desligado com acesso REALMENTE ativo — conta bloqueada/
            # inativa ja esta revogada, nao e' divergencia.
            if not _conta_ativa(acesso.situacao):
                continue

            mat_vinc = acesso.matricula_vinculada
            casou_matricula = bool(mat_vinc) and mat_vinc in matriculas_desligadas

            cpf_acesso = _norm_cpf(acesso.cpf)
            matricula_por_cpf = cpf_para_matricula.get(cpf_acesso) if cpf_acesso else None

            login_acesso = (acesso.usuario or "").strip().lower()
            matricula_por_login = (login_para_matricula.get(login_acesso)
                                   if login_acesso else None)

            if not casou_matricula and matricula_por_cpf is None \
                    and matricula_por_login is None:
                continue

            # Matricula da divergencia: a vinculada (quando bateu), senao a
            # resolvida pelo CPF e por fim a do login (AD).
            matricula = (mat_vinc if casou_matricula
                         else matricula_por_cpf or matricula_por_login)
            divergencias.append(
                Divergencia(
                    id=str(uuid.uuid4()),
                    tipo=TipoDivergencia.ACESSO_DESLIGADO,
                    sistema=acesso.sistema,
                    usuario=acesso.usuario,
                    nome_usuario=acesso.nome_usuario,
                    matricula=matricula,
                    perfil_encontrado=acesso.perfil,
                    descricao=(
                        f"Funcionário desligado com acesso ativo "
                        f"no sistema {acesso.sistema.value}"
                    ),
                )
            )
        return divergencias
