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
        # matricula -> descricao dos campos que mudaram (cargo/CC/dep/gestor)
        revisao = {
            t.funcionario.matricula: t.campos_mudados
            for t in transferidos
            if t.precisa_revisao_acessos
        }

        divergencias = []
        for acesso in acessos:
            campos = revisao.get(acesso.matricula_vinculada)
            if campos is not None:
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
                            f"Mudança de {campos or 'cadastro'} — acesso pendente de "
                            f"revisão no sistema {acesso.sistema.value}"
                        ),
                    )
                )
        return divergencias
