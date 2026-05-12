from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
from loguru import logger

from dominio.entidades.divergencia import Divergencia


_COLUNAS = [
    "Tipo",
    "Sistema",
    "Usuario",
    "Nome Usuario",
    "Matricula",
    "Perfil Encontrado",
    "Perfil Esperado",
    "Descricao",
    "Data Identificacao",
]

_LABEL_TIPOS = {
    "ACESSO_DESLIGADO":     "Acesso Desligado",
    "PERFIL_INVALIDO":      "Perfil Invalido",
    "ACESSO_SEM_VINCULO_RH": "Sem Vinculo RH",
    "ACESSO_TRANSFERIDO":   "Acesso Transferido",
    "PERFIL_EXCESSIVO":     "Perfil Excessivo",
}


def _para_linha(d: Divergencia) -> dict:
    return {
        "Tipo":              d.tipo.value,
        "Sistema":           d.sistema.value,
        "Usuario":           d.usuario,
        "Nome Usuario":      d.nome_usuario,
        "Matricula":         d.matricula or "",
        "Perfil Encontrado": d.perfil_encontrado or "",
        "Perfil Esperado":   d.perfil_esperado or "",
        "Descricao":         d.descricao,
        "Data Identificacao": d.data_identificacao.strftime("%d/%m/%Y %H:%M:%S") if d.data_identificacao else "",
    }


class EscritorExcel:

    def salvar_divergencias(self, divergencias: List[Divergencia], pasta: str) -> str:
        Path(pasta).mkdir(parents=True, exist_ok=True)
        data_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = str(Path(pasta) / f"DIVERGENCIAS_{data_str}.xlsx")

        df_all = pd.DataFrame([_para_linha(d) for d in divergencias], columns=_COLUNAS)

        with pd.ExcelWriter(caminho, engine="xlsxwriter") as writer:
            df_all.to_excel(writer, sheet_name="TODAS", index=False)
            _formatar_aba(writer, "TODAS", df_all)

            for tipo_valor in df_all["Tipo"].unique():
                df_tipo = df_all[df_all["Tipo"] == tipo_valor].copy()
                nome_aba = _label_aba(tipo_valor)
                df_tipo.to_excel(writer, sheet_name=nome_aba, index=False)
                _formatar_aba(writer, nome_aba, df_tipo)

        logger.success(f"Excel de divergencias gerado: {caminho} ({len(divergencias)} registros)")
        return caminho


def _label_aba(tipo_valor: str) -> str:
    return _LABEL_TIPOS.get(tipo_valor, tipo_valor)[:31]


def _formatar_aba(writer: pd.ExcelWriter, nome_aba: str, df: pd.DataFrame) -> None:
    workbook = writer.book
    worksheet = writer.sheets[nome_aba]

    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#1F3864",
        "font_color": "#FFFFFF",
        "border": 1,
        "align": "center",
    })

    for col_num, col_name in enumerate(df.columns):
        worksheet.write(0, col_num, col_name, header_fmt)
        col_width = max(len(col_name) + 2, df[col_name].astype(str).str.len().max() + 2)
        worksheet.set_column(col_num, col_num, min(col_width, 60))
