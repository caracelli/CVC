import uuid
from typing import List
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia


class RegraAcessoSemVinculo:

    def verificar(self, acessos: List[PerfilAcesso]) -> List[Divergencia]:
        divergencias = []
        for acesso in acessos:
            if acesso.cpf and not acesso.matricula_vinculada:
                divergencias.append(
                    Divergencia(
                        id=str(uuid.uuid4()),
                        tipo=TipoDivergencia.ACESSO_SEM_VINCULO_RH,
                        sistema=acesso.sistema,
                        usuario=acesso.usuario,
                        nome_usuario=acesso.nome_usuario,
                        descricao=(
                            f"Usuário com CPF não encontrado na base RH "
                            f"no sistema {acesso.sistema.value}"
                        ),
                    )
                )
        return divergencias
