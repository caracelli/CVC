from dataclasses import dataclass
from datetime import date
from typing import Optional
from .funcionario_ativo import FuncionarioAtivo
from ..objetos_valor.cargo import Cargo


@dataclass
class Transferido:
    funcionario: FuncionarioAtivo
    cargo_anterior: Cargo
    data_transferencia: date
    # gestor de ANTES da mudanca (o gestor atual esta em funcionario.gestor)
    gestor_anterior: Optional[str] = None
    motivo: Optional[str] = None

    @property
    def precisa_revisao_acessos(self) -> bool:
        """Precisa revisar os acessos quando MUDOU cargo, centro de custo OU
        gestor. O departamento saiu em 22/10/2026 (Bruna, Aplicacao_21_10:
        "Considerar apenas CENTRO de CUSTO, CARGO e GESTOR")."""
        atual = self.funcionario.cargo
        ant = self.cargo_anterior
        return (
            atual.centro_custo != ant.centro_custo
            or atual.codigo != ant.codigo
            or atual.descricao != ant.descricao
            or (self.funcionario.gestor or "") != (self.gestor_anterior or "")
        )

    @property
    def campos_mudados(self) -> str:
        """Rotulo legivel dos campos que mudaram (para a descricao da pendencia)."""
        atual = self.funcionario.cargo
        ant = self.cargo_anterior
        m = []
        if atual.codigo != ant.codigo or atual.descricao != ant.descricao:
            m.append("cargo")
        if atual.centro_custo != ant.centro_custo:
            m.append("centro de custo")
        if (self.funcionario.gestor or "") != (self.gestor_anterior or ""):
            m.append("gestor")
        return ", ".join(m)
