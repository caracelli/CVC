"""Leitor dos exports do diretorio (Active Directory) por OU.

Layout unico dos 3 arquivos (CSV `;`, cp1252/latin-1):
    Nome;Email;Login;CPF;Escritorio;Cargo;Departamento;Empresa;Status;Manager;Criacao

Cada OU vira uma populacao (tipo_vinculo): FRANQUEADO, PRESTADOR. Serve para
dar dono aos acessos ORFAOS (sem vinculo RH/terceiro) — a chave forte e' o
Login, que == `usuario`/CD_LOGIN do extrato de acesso. Cada identidade vira um
FuncionarioAtivo com matricula namespaced (ex.: FRANQ-<login>) para nao colidir
com matricula CLT.
"""
import re
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from loguru import logger

from .leitor_base import LeitorArquivoBase, ler_tabela
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.objetos_valor.cargo import Cargo


# Prefixo da matricula por populacao (evita colisao com matricula CLT/terceiro)
_PREFIXO = {"FRANQUEADO": "FRANQ", "PRESTADOR": "PREST", "DESLIGADO_AD": "ADESL"}


def _v(row: pd.Series, col: str) -> str:
    if col not in row.index:
        return ""
    val = row[col]
    return "" if pd.isna(val) else str(val).strip()


def _nome_do_dn(v: str) -> str:
    """O 'Manager' do AD vem como Distinguished Name (ex.:
    'CN=Erika Paulin,OU=Franqueado,DC=intra,DC=cvc'). Extrai so o CN (o nome) e
    normaliza p/ MAIUSCULO, ficando homogeneo com o 'gestor' do RH. Sem 'CN='
    (ja e' nome puro), devolve o proprio valor. Vazio -> ''."""
    if not v:
        return ""
    m = re.match(r"\s*CN=([^,]+)", v, flags=re.IGNORECASE)
    nome = m.group(1) if m else v
    return " ".join(nome.strip().upper().split())


class LeitorDiretorioAd(LeitorArquivoBase):

    def __init__(self, pasta_processados: str = None, pasta_erros: str = None):
        super().__init__(pasta_processados, pasta_erros)

    def ler(self, arquivo: Path, tipo_vinculo: str) -> List[FuncionarioAtivo]:
        """Le UM arquivo AD e devolve identidades com o tipo_vinculo dado.
        Dedup por login (primeiro vence). Registro sem login E sem cpf e' descartado
        (sem chave de vinculo util)."""
        enc = self.detectar_encoding(arquivo) if arquivo.suffix.lower() == ".csv" else "utf-8"
        df = ler_tabela(arquivo, dtype=str, encoding=enc, separador=";")
        df.columns = [str(c).strip() for c in df.columns]

        prefixo = _PREFIXO.get(tipo_vinculo, "AD")
        out: List[FuncionarioAtivo] = []
        vistos = set()
        descartados = 0
        for _, row in df.iterrows():
            login = _v(row, "Login")
            cpf = _v(row, "CPF")
            nome = _v(row, "Nome")
            if not login and not cpf:
                descartados += 1
                continue
            chave = (login or cpf).upper()
            if chave in vistos:
                continue
            vistos.add(chave)
            # matricula estavel: prefixo + login (ou cpf quando sem login)
            matricula = f"{prefixo}-{(login or cpf)}"
            out.append(FuncionarioAtivo(
                matricula=matricula,
                nome=nome,
                cpf=cpf,
                cargo=Cargo(codigo="", descricao=_v(row, "Cargo"),
                            departamento=_v(row, "Departamento"), centro_custo=""),
                email=_v(row, "Email") or None,
                data_admissao=None,
                situacao="ATIVO",
                tipo_vinculo=tipo_vinculo,
                login=login or None,
                empresa=_v(row, "Empresa") or None,
                # "Manager" do AD == gestor (mesma semantica do "Nome Gestor" do
                # RH); da' gestor aos franqueados/prestadores nas grids. Vem como
                # DN (CN=Nome,OU=...) — extrai so o nome.
                gestor=_nome_do_dn(_v(row, "Manager")) or None,
            ))
        if descartados:
            logger.warning(f"Diretorio AD [{tipo_vinculo}]: {descartados} sem login/cpf ignorado(s).")
        logger.success(f"Diretorio AD [{tipo_vinculo}]: {len(out)} identidades de '{arquivo.name}'.")
        return out

    def ler_desligados(self, arquivo: Path) -> List["FuncionarioDesligado"]:
        """OU_Desligados: identidades de quem SAIU (B2 = sim, 29/07). Nao sao
        identidades ativas — viram DESLIGADOS, com `login` como chave (o export
        do AD nao tem matricula de RH). A matricula fica namespaced ADESL-<login>
        para nao colidir com matricula de RH."""
        enc = self.detectar_encoding(arquivo) if arquivo.suffix.lower() == ".csv" else "utf-8"
        df = ler_tabela(arquivo, dtype=str, encoding=enc, separador=";")
        df.columns = [str(c).strip() for c in df.columns]

        prefixo = _PREFIXO["DESLIGADO_AD"]
        out: List[FuncionarioDesligado] = []
        vistos = set()
        descartados = 0
        for _, row in df.iterrows():
            login = _v(row, "Login")
            cpf = _v(row, "CPF")
            if not login and not cpf:
                descartados += 1
                continue
            chave = (login or cpf).upper()
            if chave in vistos:
                continue
            vistos.add(chave)
            out.append(FuncionarioDesligado(
                matricula=f"{prefixo}-{(login or cpf)}",
                # contas de servico/genericas do OU vem SEM nome; a entidade
                # exige nome, entao cai para o login (e depois o CPF) — melhor
                # que descartar a identidade e perder o acesso vivo dela.
                nome=_v(row, "Nome") or login or cpf,
                cpf=cpf,
                cargo=Cargo(codigo="", descricao=_v(row, "Cargo"),
                            departamento=_v(row, "Departamento"), centro_custo=""),
                email=_v(row, "Email") or None,
                data_admissao=None,
                # o export nao traz data de desligamento (so a OU); fica vazia —
                # o corte temporal esta fora de escopo (decisao da usuaria).
                data_desligamento=None,
                login=login or None,
            ))
        if descartados:
            logger.warning(f"Diretorio AD [DESLIGADOS]: {descartados} sem login/cpf ignorado(s).")
        logger.success(f"Diretorio AD [DESLIGADOS]: {len(out)} identidades de '{arquivo.name}'.")
        return out
