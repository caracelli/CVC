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
        df = self._corrigir_tipos(df)
        table = pa.Table.from_pandas(df, preserve_index=False)
        table = self._corrigir_colunas_null(table)
        pq.write_table(table, str(arquivo))
        logger.info(f"Parquet salvo: {arquivo} ({len(df)} registros)")

    def salvar_fixo(self, df: pd.DataFrame, caminho: str, nome: str):
        self.salvar(df, caminho, f"{nome}.parquet")

    @staticmethod
    def _corrigir_tipos(df: pd.DataFrame) -> pd.DataFrame:
        """Garante que colunas booleanas tenham dtype bool, não object."""
        for col in df.columns:
            if df[col].dtype == object:
                sample = df[col].dropna()
                if len(sample) > 0 and all(isinstance(v, bool) for v in sample.head(10)):
                    df = df.copy()
                    df[col] = df[col].astype("bool")
        return df

    @staticmethod
    def _corrigir_colunas_null(table: pa.Table) -> pa.Table:
        """Substitui colunas com tipo null (all-None) por string vazia."""
        arrays, fields = [], []
        for i, field in enumerate(table.schema):
            col = table.column(i)
            if pa.types.is_null(field.type):
                col = pa.array([""] * len(col), type=pa.string())
                field = field.with_type(pa.string())
            arrays.append(col)
            fields.append(field)
        return pa.table(
            {f.name: a for f, a in zip(fields, arrays)},
            schema=pa.schema(fields),
        )
