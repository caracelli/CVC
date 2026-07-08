import uuid
from typing import List
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia


class RegraAcessoSemVinculo:

    def verificar(self, acessos: List[PerfilAcesso]) -> List[Divergencia]:
        # "Sem Vínculo RH" é um achado POR LOGIN/SISTEMA (a pessoa não está no
        # RH), não por perfil. Um login com N perfis no sistema gera 1 achado,
        # não N. Deduplica por (login normalizado, sistema) — caixa é ignorada
        # (INTADM527 == intadm527). Mantém o primeiro acesso visto como amostra.
        divergencias = []
        vistos = set()
        for acesso in acessos:
            if acesso.cpf and not acesso.matricula_vinculada:
                chave = ((acesso.usuario or "").strip().lower(), acesso.sistema)
                if chave in vistos:
                    continue
                vistos.add(chave)
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
