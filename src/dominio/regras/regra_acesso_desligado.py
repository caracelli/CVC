import re
import uuid
from typing import List, Optional
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.funcionario_desligado import FuncionarioDesligado
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia


# Status que indicam conta SEM acesso efetivo (revogada/desativada, mas ainda
# listada no extrato). Uma conta bloqueada de um desligado NAO e' irregularidade
# de acesso — ja esta revogada. Ex.: o SIG traz ~90% das contas como BLOQUEADO.
_STATUS_SEM_ACESSO = {
    "INATIVO", "INACTIVE", "BLOQUEADO", "BLOCKED",
    "SUSPENSO", "DESATIVADO", "CANCELADO", "I", "B",
}


def _conta_ativa(situacao: Optional[str]) -> bool:
    """True se a conta tem acesso efetivo. Vazio/None conta como ativo (alguns
    extratos deixam status em branco = ativo)."""
    return (situacao or "").strip().upper() not in _STATUS_SEM_ACESSO


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
    Fase 1): o acesso e' de um desligado se a MATRICULA vinculada OU o CPF do
    extrato baterem com um desligado. Casar so por matricula subconta (o passo
    de vinculo cruza contra ATIVOS, entao o acesso de um desligado costuma ficar
    sem matricula anexada); o CPF do extrato fecha essa lacuna. Uma linha que
    bate pelas duas chaves gera UMA divergencia (sem dobra).
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

            if not casou_matricula and matricula_por_cpf is None:
                continue

            # Matricula da divergencia: a vinculada (quando bateu) ou a resolvida
            # pelo CPF do desligado.
            matricula = mat_vinc if casou_matricula else matricula_por_cpf
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
