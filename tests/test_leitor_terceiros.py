"""Testes do roteamento RH CLT x Terceiro no LeitorRh.

Cobre:
  - deteccao do layout (EMPRESA FORNECEDORA / STATUS RH = terceiro;
    Matricula = CLT);
  - parsing de terceiros: chave TERC-<codigo>, dedupe, supervisor no
    'departamento', empresa, situacao mapeada, tipo_vinculo;
  - limpeza de CODIGO -> CPF (zfill+validacao, residual cru);
  - CLT continua com tipo_vinculo=FUNCIONARIO.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from infraestrutura.leitores_arquivos.leitor_rh import (  # noqa: E402
    LeitorRh, _cpf_de_codigo, _norm_nome, _eh_terceiro, _tem_matricula_clt,
)


def _df_terceiros(linhas):
    return pd.DataFrame(linhas, columns=[
        "EMPRESA FORNECEDORA", "CNPJ", "NOME DO SUPERVISOR",
        "NOME", "CÓDIGO", "STATUS RH"])


def test_cpf_de_codigo():
    # CPF valido de 11 digitos permanece
    assert _cpf_de_codigo("50165575867") == "50165575867"
    # CPF valido com zero a esquerda (salvo como numero) e' re-padronizado
    assert _cpf_de_codigo("3357965160") == "03357965160"
    # codigo curto que nao e' CPF valido -> devolve digitos crus
    assert _cpf_de_codigo("22086830") == "22086830"
    # formatado -> so digitos
    assert _cpf_de_codigo("501.655.758-67") == "50165575867"
    assert _cpf_de_codigo("") == ""


def test_norm_nome_remove_nbsp():
    assert _norm_nome("Joneilson\xa0Pereira  Lima") == "Joneilson Pereira Lima"


def test_deteccao_layout():
    terc = _df_terceiros([["E", "1", "SUP", "FULANO", "50165575867", "Ativo"]])
    assert _eh_terceiro(terc) and not _tem_matricula_clt(terc)

    clt = pd.DataFrame([["714", "JOAO", "05072102980"]],
                       columns=["Matricula", "Nome da Pessoa", "Numero do CPF"])
    assert _tem_matricula_clt(clt) and not _eh_terceiro(clt)


def test_parse_terceiros():
    df = _df_terceiros([
        ["ACME LTDA", "61750246000175", "FERNANDA PARANHOS", "ANA SILVA", "50165575867", "Ativo"],
        ["ACME LTDA", "61750246000175", "HUGO NUNES", "BIANCA SOARES", "46313720873", "Inativo"],
        # duplicado (mesmo codigo) -> ignorado
        ["ACME LTDA", "61750246000175", "OUTRO", "ANA SILVA", "50165575867", "Ativo"],
        # sem nome -> ignorado
        ["ACME LTDA", "61750246000175", "SUP", "", "11122233396", "Ativo"],
    ])
    res = LeitorRh()._parse_terceiros(df)
    assert len(res) == 2  # 1 dup + 1 sem nome descartados

    a = {f.matricula: f for f in res}
    assert "TERC-50165575867" in a and "TERC-46313720873" in a
    f0 = a["TERC-50165575867"]
    assert f0.tipo_vinculo == "TERCEIRO"
    assert f0.nome == "ANA SILVA"
    assert f0.cpf == "50165575867"
    assert f0.cargo.departamento == "FERNANDA PARANHOS"   # supervisor reaproveitado
    assert f0.empresa == "ACME LTDA"
    assert f0.situacao == "ATIVO"
    assert a["TERC-46313720873"].situacao == "INATIVO"


def test_parse_clt_marca_funcionario():
    df = pd.DataFrame([["714", "JOAO SILVA", "05072102980"]],
                      columns=["Matricula", "Nome da Pessoa", "Numero do CPF"])
    res = LeitorRh()._parse_clt(df)
    assert len(res) == 1
    assert res[0].tipo_vinculo == "FUNCIONARIO"
    assert res[0].matricula == "714"
