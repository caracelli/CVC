import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class ConfigSistema:
    id: str
    nome: str
    descricao: str
    caminho_entrada: str
    caminho_parquet: str
    colunas: Dict[str, str] = field(default_factory=dict)


@dataclass
class Configuracao:
    versao: str
    cliente: str
    raiz: Path
    banco_dados: str
    encoding_padrao: str
    separador_csv: str
    formato_data: str
    sistemas: Dict[str, ConfigSistema]
    rh_ativos_caminho: str
    rh_desligados_caminho: str
    parquet_rh: str
    saida_divergencias: str
    saida_desligados: str
    saida_transferidos: str
    saida_auditoria: str
    saida_logs: str


class LeitorConfig:

    def __init__(self, caminho_config: str):
        self._caminho = Path(caminho_config)

    def carregar(self) -> Configuracao:
        tree = ET.parse(self._caminho)
        root = tree.getroot()

        raiz = Path(root.findtext("caminhos/raiz", "."))

        sistemas: Dict[str, ConfigSistema] = {}
        for sis in root.findall("sistemas/sistema"):
            sid = sis.get("id")
            colunas_node = sis.find("colunas")
            colunas = {c.tag: c.text for c in colunas_node} if colunas_node else {}
            sistemas[sid] = ConfigSistema(
                id=sid,
                nome=sis.findtext("nome", ""),
                descricao=sis.findtext("descricao", ""),
                caminho_entrada=sis.findtext("caminho_entrada", ""),
                caminho_parquet=sis.findtext("caminho_parquet", ""),
                colunas=colunas,
            )

        proc = root.find("processamento")

        return Configuracao(
            versao=root.findtext("versao", "1.0.0"),
            cliente=root.findtext("cliente", ""),
            raiz=raiz,
            banco_dados=root.findtext("caminhos/banco_dados", ""),
            encoding_padrao=proc.findtext("encoding_padrao", "utf-8") if proc else "utf-8",
            separador_csv=proc.findtext("separador_csv", ";") if proc else ";",
            formato_data=proc.findtext("formato_data", "%d/%m/%Y") if proc else "%d/%m/%Y",
            sistemas=sistemas,
            rh_ativos_caminho=root.findtext("rh/ativos/caminho", ""),
            rh_desligados_caminho=root.findtext("rh/desligados/caminho", ""),
            parquet_rh=str(raiz / root.findtext("caminhos/parquet", "06_DADOS_PROJETO/PARQUET") / "RH"),
            saida_divergencias=root.findtext("saidas/divergencias", ""),
            saida_desligados=root.findtext("saidas/desligados", ""),
            saida_transferidos=root.findtext("saidas/transferidos", ""),
            saida_auditoria=root.findtext("saidas/auditoria", ""),
            saida_logs=root.findtext("saidas/logs", ""),
        )
