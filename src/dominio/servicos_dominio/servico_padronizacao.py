import re
from typing import Optional


class ServicoPadronizacao:

    @staticmethod
    def normalizar_cpf(cpf: Optional[str]) -> str:
        if not cpf:
            return ""
        digits = re.sub(r"\D", "", str(cpf))
        return digits.zfill(11) if digits else ""

    @staticmethod
    def normalizar_nome(nome: Optional[str]) -> str:
        if not nome:
            return ""
        return " ".join(str(nome).strip().upper().split())

    @staticmethod
    def normalizar_matricula(matricula: Optional[str]) -> str:
        if not matricula:
            return ""
        return str(matricula).strip().lstrip("0") or "0"

    @staticmethod
    def normalizar_situacao(situacao: Optional[str]) -> str:
        if not situacao:
            return ""
        mapa = {
            "A": "ATIVO",
            "ATIVO": "ATIVO",
            "ATIVIDADE NORMAL": "ATIVO",
            "I": "INATIVO",
            "INATIVO": "INATIVO",
            "B": "BLOQUEADO",
            "BLOQUEADO": "BLOQUEADO",
            "RESCISÃO": "DESLIGADO",
            "RESCISAO": "DESLIGADO",
        }
        chave = str(situacao).strip().upper()
        return mapa.get(chave, chave)
