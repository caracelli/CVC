from dataclasses import dataclass


@dataclass(frozen=True)
class Cargo:
    codigo: str
    descricao: str
    departamento: str
    centro_custo: str
