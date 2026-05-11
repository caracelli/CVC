import uuid
from typing import List
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.transferido import Transferido
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia


class RegraAcessoTransferido:

    def verificar(
        self,
        acessos: List[PerfilAcesso],
        transferidos: List[Transferido],
    ) -> List[Divergencia]:
        matriculas_para_revisao = {
            t.funcionario.matricula
            for t in transferidos
            if t.precisa_revisao_acessos
        }

        divergencias = []
        for acesso in acessos:
            if acesso.matricula_vinculada in matriculas_para_revisao:
                divergencias.append(
                    Divergencia(
                        id=str(uuid.uuid4()),
                        tipo=TipoDivergencia.ACESSO_TRANSFERIDO,
                        sistema=acesso.sistema,
                        usuario=acesso.usuario,
                        nome_usuario=acesso.nome_usuario,
                        matricula=acesso.matricula_vinculada,
                        perfil_encontrado=acesso.perfil,
                        descricao=(
                            f"Funcionário transferido de departamento com acesso "
                            f"pendente de revisão no sistema {acesso.sistema.value}"
                        ),
                    )
                )
        return divergencias
