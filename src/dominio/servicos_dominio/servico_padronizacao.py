import re
from typing import Optional


# Caracteres que indicam CPF mascarado (formato comum: '39328XXX', '393.28?-??').
# Quando presentes, o normalizar_cpf preserva a string original em vez de
# completar com zeros — assim a cascata multi-chave consegue extrair o CPF
# parcial e usar nivel 3 (CPF_PARCIAL_NOME) em vez de tentar nivel 1 com
# um "CPF" forjado que nao bate com ninguem.
_CHARS_MASCARA_CPF = set("X?*#")


class ServicoPadronizacao:

    @staticmethod
    def normalizar_cpf(cpf: Optional[str]) -> str:
        """Normaliza CPF para 11 digitos com zfill — ou preserva original
        se for um CPF mascarado (presenca de X, ?, *, # no input).

        Cenarios:
        - "123.456.789-00"  -> "12345678900"  (formatado)
        - "12345678900"     -> "12345678900"  (digitos)
        - "1234567890"      -> "01234567890"  (10 digitos -> zfill 11)
        - "39328XXX"        -> "39328XXX"     (MASCARADO — preserva)
        - "393.28?-??"      -> "393.28?-??"   (MASCARADO — preserva)
        - ""/None           -> ""

        Mascarado preservado permite que cascata extraia parcial via
        extrair_cpf_parcial (retorna "39328") sem confundir nivel 1.
        """
        if not cpf:
            return ""
        s = str(cpf).strip().upper()
        # Detecta mascaramento — preserva original sem zfill
        if any(c in _CHARS_MASCARA_CPF for c in s):
            return s
        digits = re.sub(r"\D", "", s)
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
