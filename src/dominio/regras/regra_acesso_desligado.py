import uuid
from typing import List
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.funcionario_desligado import FuncionarioDesligado
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia


class RegraAcessoDesligado:

    def verificar(
        self,
        acessos: List[PerfilAcesso],
        desligados: List[FuncionarioDesligado],
    ) -> List[Divergencia]:
        matriculas_desligadas = {d.matricula for d in desligados}

        divergencias = []
        for acesso in acessos:
            if acesso.matricula_vinculada and acesso.matricula_vinculada in matriculas_desligadas:
                divergencias.append(
                    Divergencia(
                        id=str(uuid.uuid4()),
                        tipo=TipoDivergencia.ACESSO_DESLIGADO,
                        sistema=acesso.sistema,
                        usuario=acesso.usuario,
                        nome_usuario=acesso.nome_usuario,
                        matricula=acesso.matricula_vinculada,
                        perfil_encontrado=acesso.perfil,
                        descricao=(
                            f"Funcionário desligado com acesso ativo "
                            f"no sistema {acesso.sistema.value}"
                        ),
                    )
                )
        return divergencias
