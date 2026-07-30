import uuid
from typing import Dict, List
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.divergencia import Divergencia
from ..objetos_valor.situacao_conta import conta_ativa
from ..objetos_valor.tipo_divergencia import TipoDivergencia


class RegraAcessoSemVinculo:

    def verificar(self, acessos: List[PerfilAcesso]) -> List[Divergencia]:
        # "Sem Vínculo RH" é um achado POR LOGIN/SISTEMA (a pessoa não está no
        # RH), não por perfil. Um login com N perfis no sistema gera 1 achado,
        # não N. Deduplica por (login normalizado, sistema) — caixa é ignorada
        # (INTADM527 == intadm527). O achado carrega TODOS os perfis daquele
        # login no sistema (antes ia vazio e o painel mostrava "—": o analista
        # não via a que o órfão tem acesso).
        # Conta BLOQUEADA/INATIVA não é acesso — já está revogada, não vira
        # achado (mesma semântica das demais regras: situacao_conta).
        divergencias: List[Divergencia] = []
        por_chave: Dict[tuple, Divergencia] = {}
        perfis_por_chave: Dict[tuple, List[str]] = {}
        for acesso in acessos:
            if not (acesso.cpf and not acesso.matricula_vinculada):
                continue
            if not conta_ativa(acesso.situacao):
                continue
            chave = ((acesso.usuario or "").strip().lower(), acesso.sistema)
            perfil = (acesso.perfil or "").strip()
            if chave not in por_chave:
                d = Divergencia(
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
                por_chave[chave] = d
                perfis_por_chave[chave] = []
                divergencias.append(d)
            if perfil and perfil not in perfis_por_chave[chave]:
                perfis_por_chave[chave].append(perfil)

        # perfil_encontrado = os perfis do login naquele sistema (ordenados)
        for chave, d in por_chave.items():
            d.perfil_encontrado = ", ".join(sorted(perfis_por_chave[chave]))
        return divergencias
