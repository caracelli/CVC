from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger


class EscritorParquet:

    def salvar(self, df: pd.DataFrame, caminho: str, nome_arquivo: str):
        pasta = Path(caminho)
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / nome_arquivo
        table = pa.Table.from_pandas(df)
        pq.write_table(table, str(arquivo))
        logger.info(f"Parquet salvo: {arquivo} ({len(df)} registros)")

    def salvar_com_data(self, df: pd.DataFrame, caminho: str, prefixo: str):
        hoje = date.today().strftime("%Y%m%d")
        self.salvar(df, caminho, f"{prefixo}_{hoje}.parquet")
