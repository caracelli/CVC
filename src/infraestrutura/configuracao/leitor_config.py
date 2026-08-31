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
    # Caminho do de-para de codigos -> nomes (usado por sistemas com
    # formato matricial como SIG). Vazio para sistemas que trazem o nome
    # do perfil direto no extrato (SYSTUR, SIGOT, IC, etc.).
    caminho_de_para: str = ""
    # 'longo' (padrao) = 1 linha por par usuario-perfil; 'matricial' =
    # 1 linha por usuario com colunas = codigos de perfil (X = tem).
    formato: str = "longo"
    # false = sistema declarado no config mas sem implementacao/arquivo ainda
    # (scaffold). Processador ignora.
    ativo: bool = True


@dataclass
class Configuracao:
    versao: str
    cliente: str
    raiz: Path
    rede_raiz: str
    rede_executaveis: str
    rede_interacoes: str
    banco_dados: str
    encoding_padrao: str
    separador_csv: str
    formato_data: str
    sistemas: Dict[str, ConfigSistema]
    rh_ativos_caminho: str
    rh_desligados_caminho: str
    # Escopo da fase: na Fase 1 (SYSTUR inclusao/alteracao) desligados e
    # terceiros ficam fora. Default True preserva o comportamento legado.
    rh_processar_desligados: bool
    rh_processar_terceiros: bool
    # PERFIL EXCESSIVO (perfil ALEM do que a matriz preve). O excesso SEMPRE
    # aparece na tela; esta flag decide se ele tambem COBRA acao (vira Em
    # Analise). Default False: sao 196 casos medidos e transformar isso em
    # pendencia de uma vez e' decisao da area, nao do motor.
    validacao_excesso_gera_pendencia: bool
    # CONTA DE SERVICO (robo/automacao) nos desligados. Prefixos de LOGIN; o
    # acesso deixa de entrar na lista de revogacao e passa a um tipo proprio,
    # consultavel. Vazio = regra desligada (comportamento anterior).
    # Medido em 31/08/2026: o prefixo SIST pega 297 das 432 linhas, com zero
    # falso positivo e zero robo fora do prefixo.
    conta_servico_prefixos: List[str]
    # Diretorio AD (franqueados/prestadores/desligados) — identidades p/ dar dono
    # aos orfaos. Aceita VARIOS <caminho>: desde 05/08/2026 o cliente entrega os
    # exports em pastas separadas por populacao (SISTEMAS/AD_FRANQUEADOS,
    # AD_PRESTADORES, AD_DESLIGADOS), nao mais numa pasta unica.
    rh_diretorio_ad_caminho: str            # o primeiro (compatibilidade)
    rh_diretorio_ad_caminhos: List[str]     # todos
    rh_processar_diretorio_ad: bool
    processados: str
    erros: str
    matrizes_perfis_caminho: str
    matrizes_perfis_colunas: Dict[str, str]
    matrizes_org_caminho: str
    matrizes_org_colunas: Dict[str, str]
    saida_divergencias: str
    saida_desligados: str
    saida_transferidos: str
    saida_auditoria: str
    saida_logs: str
    visualizador_sistema: str
    visualizador_quarentena_dias: int


def _ad_caminhos(root) -> List[str]:
    """Todos os <caminho> de <rh><diretorio_ad>, na ordem do arquivo.

    Um unico <caminho> (formato antigo) continua valendo — vira lista de um.
    Vazios sao descartados para um <caminho/> solto nao virar a raiz do app."""
    no = root.find("rh/diretorio_ad")
    if no is None:
        return []
    return [c.text.strip() for c in no.findall("caminho") if (c.text or "").strip()]


def _conta_servico_prefixos(root) -> List[str]:
    """Prefixos de login de CONTA DE SERVICO, de <validacao><conta_servico>.

    Aceita lista separada por virgula em <prefixos_login> (um so' prefixo e' o
    caso comum: `SIST`). A chave <excluir_de_desligados> desliga a regra sem
    apagar a lista — util para a area voltar atras sem perder o que configurou.
    Ausente ou vazio = regra desligada, exatamente o comportamento anterior."""
    no = root.find("validacao/conta_servico")
    if no is None:
        return []
    ligado = (no.findtext("excluir_de_desligados", "true") or "").strip().lower()
    if ligado not in ("true", "1", "sim"):
        return []
    bruto = no.findtext("prefixos_login", "") or ""
    return [p.strip() for p in bruto.split(",") if p.strip()]


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
            colunas = {c.tag: c.text for c in colunas_node} if colunas_node is not None else {}
            ativo_txt = (sis.findtext("ativo", "true") or "true").strip().lower()
            sistemas[sid] = ConfigSistema(
                id=sid,
                nome=sis.findtext("nome", ""),
                descricao=sis.findtext("descricao", ""),
                caminho_entrada=sis.findtext("caminho_entrada", ""),
                caminho_parquet=sis.findtext("caminho_parquet", ""),
                colunas=colunas,
                caminho_de_para=sis.findtext("caminho_de_para", "") or "",
                formato=(sis.findtext("formato", "longo") or "longo").strip().lower(),
                ativo=ativo_txt not in ("false", "0", "no", "nao", "n"),
            )

        proc = root.find("processamento")

        def _colunas(xpath: str) -> Dict[str, str]:
            node = root.find(xpath)
            return {c.tag: c.text for c in node} if node is not None else {}

        def _bool(xpath: str, padrao: str = "true") -> bool:
            txt = (root.findtext(xpath, padrao) or padrao).strip().lower()
            return txt not in ("false", "0", "no", "nao", "n")

        return Configuracao(
            versao=root.findtext("versao", "1.0.0"),
            cliente=root.findtext("cliente", ""),
            raiz=raiz,
            rede_raiz=root.findtext("rede/raiz", ""),
            rede_executaveis=root.findtext("rede/executaveis", "EXECUTAVEIS"),
            rede_interacoes=root.findtext("rede/interacoes", "INTERACOES"),
            banco_dados=root.findtext("rede/banco_dados", ""),
            encoding_padrao=proc.findtext("encoding_padrao", "utf-8") if proc is not None else "utf-8",
            separador_csv=proc.findtext("separador_csv", ";") if proc is not None else ";",
            formato_data=proc.findtext("formato_data", "%d/%m/%Y") if proc is not None else "%d/%m/%Y",
            sistemas=sistemas,
            rh_ativos_caminho=root.findtext("rh/ativos/caminho", ""),
            rh_desligados_caminho=root.findtext("rh/desligados/caminho", ""),
            rh_processar_desligados=_bool("rh/desligados/processar"),
            rh_processar_terceiros=_bool("rh/ativos/processar_terceiros"),
            validacao_excesso_gera_pendencia=_bool(
                "validacao/perfil_excessivo/gera_pendencia", "false"),
            conta_servico_prefixos=_conta_servico_prefixos(root),
            rh_diretorio_ad_caminho=(_ad_caminhos(root) or ["ENTRADA/RH/AD"])[0],
            rh_diretorio_ad_caminhos=_ad_caminhos(root) or ["ENTRADA/RH/AD"],
            rh_processar_diretorio_ad=_bool("rh/diretorio_ad/processar"),
            processados=root.findtext("rede/processados", "DADOS/PROCESSADOS"),
            erros=root.findtext("rede/erros", "DADOS/ERROS"),
            matrizes_perfis_caminho=root.findtext("matrizes/perfis_sistemas/caminho", ""),
            matrizes_perfis_colunas=_colunas("matrizes/perfis_sistemas/colunas"),
            matrizes_org_caminho=root.findtext("matrizes/organizacional/caminho", ""),
            matrizes_org_colunas=_colunas("matrizes/organizacional/colunas"),
            saida_divergencias=root.findtext("saidas/divergencias", ""),
            saida_desligados=root.findtext("saidas/desligados", ""),
            saida_transferidos=root.findtext("saidas/transferidos", ""),
            saida_auditoria=root.findtext("saidas/auditoria", ""),
            saida_logs=root.findtext("saidas/logs", ""),
            visualizador_sistema=root.findtext("visualizador/sistema", ""),
            visualizador_quarentena_dias=int(
                root.findtext("visualizador/quarentena_dias", "90") or "90"),
        )
