import uuid
from typing import List
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.perfil_esperado import PerfilEsperado
from ..entidades.funcionario_ativo import FuncionarioAtivo
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia


class RegraPerfilInvalido:

    def __init__(self, perfis_esperados: List[PerfilEsperado]):
        self._perfis_esperados = perfis_esperados

    def verificar(
        self,
        acessos: List[PerfilAcesso],
        ativos: List[FuncionarioAtivo],
    ) -> List[Divergencia]:
        mapa_ativos = {f.matricula: f for f in ativos}

        divergencias = []
        for acesso in acessos:
            funcionario = mapa_ativos.get(acesso.matricula_vinculada)
            if not funcionario:
                continue

            perfis_validos = {
                pe.perfil
                for pe in self._perfis_esperados
                if pe.cargo_codigo == funcionario.cargo.codigo
                and pe.sistema == acesso.sistema
            }

            if perfis_validos and acesso.perfil not in perfis_validos:
                divergencias.append(
                    Divergencia(
                        id=str(uuid.uuid4()),
                        tipo=TipoDivergencia.PERFIL_INVALIDO,
                        sistema=acesso.sistema,
                        usuario=acesso.usuario,
                        nome_usuario=acesso.nome_usuario,
                        matricula=acesso.matricula_vinculada,
                        perfil_encontrado=acesso.perfil,
                        perfil_esperado=", ".join(sorted(perfis_validos)),
                        descricao=(
                            f"Perfil '{acesso.perfil}' não permitido para o cargo "
                            f"'{funcionario.cargo.descricao}' "
                            f"no sistema {acesso.sistema.value}"
                        ),
                    )
                )
        return divergencias
