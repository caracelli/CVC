# -*- coding: utf-8 -*-
"""De-para de CARGO derivado do proprio uso.

A matriz do franqueado fala em ATENDENTE; o RH escreve VENDEDOR, VENDEDORA,
VENDENDOR, CONSULTOR VENDAS I. Sem tratar isso, a regra acusa acesso indevido
onde ha' apenas sinonimia de cargo — medido em 01/09 num unico perfil
(`ATEND_PUBLIC_LJT_VENDEDOR_VC`, 2.287 acessos): dos 173 que nao batiam, 134
eram VENDEDOR/VENDENDOR/VENDEDORA.

Pedir a lista para a area seria transferir trabalho: o dado ja' responde. Se
135 pessoas com cargo VENDEDOR carregam justamente o perfil que a matriz
reserva a ATENDENTE, o uso esta' dizendo que sao o mesmo cargo. E' a MESMA
logica de maioria que o projeto ja' usa no espelho do SIG e dos terceiros
(>=70%), aplicada a outra pergunta.

O de-para e' PROPOSTA, nao verdade: quem valida e' a area, olhando o resultado
na tela (o motivo do registro diz "cargo X tratado como Y"). Por isso ele sai
junto com a consistencia medida.
"""
from collections import defaultdict
from typing import Dict, Iterable, Mapping, NamedTuple, Set, Tuple

LIMIAR_PADRAO = 0.70

# Abaixo disso o par nao se sustenta: 2 acessos concordando e' coincidencia,
# nao padrao de uso.
MIN_ACESSOS_PADRAO = 3


class EquivalenciaCargo(NamedTuple):
    """Cargo do RH tratado como um cargo da matriz, com a prova."""
    cargo_rh: str
    cargo_matriz: str
    acessos: int
    consistencia: float

    def descricao(self) -> str:
        return ("cargo '%s' tratado como '%s' (%d acessos, %.0f%% de consistencia)"
                % (self.cargo_rh, self.cargo_matriz, self.acessos,
                   self.consistencia * 100))


def derivar_depara(
    pares_cargo_perfil: Iterable[Tuple[str, str]],
    cargos_por_perfil: Mapping[str, Set[str]],
    limiar: float = LIMIAR_PADRAO,
    min_acessos: int = MIN_ACESSOS_PADRAO,
) -> Dict[str, EquivalenciaCargo]:
    """Deriva equivalencias de cargo a partir do uso observado.

    `pares_cargo_perfil`: um par (cargo do RH, perfil que a pessoa TEM) por
    acesso, ambos ja' normalizados. `cargos_por_perfil`: o indice da matriz
    (perfil -> cargos autorizados).

    Um cargo do RH que JA' existe na matriz nao entra: ele nao precisa de
    tradutor, e mapea-lo esconderia divergencia real (um GERENTE com perfil de
    ATENDENTE viraria "ATENDENTE" e sairia aderente).
    """
    cargos_da_matriz: Set[str] = set()
    for cargos in cargos_por_perfil.values():
        cargos_da_matriz |= cargos

    # cargo do RH -> cargo da matriz -> em quantos acessos aquele cargo estava
    # entre os AUTORIZADOS do perfil usado.
    #
    # Um perfil que serve a mais de um cargo (ATEND_PUBLIC_LJT_SUPERVISOR_VC
    # vale para SUPERVISOR DE VENDAS e SUPERVISOR ADMINISTRATIVO) vota nos
    # DOIS. Descarta-lo seria pior: o cargo 'SUPERVISOR' do RH ficaria sem
    # tradutor e viraria divergencia falsa — foi o que aconteceu na primeira
    # medicao de 02/09 (626 "nao autorizados", contra 179 medidos a mao).
    # Qualquer um dos dois alvos serve, porque a aderencia so' pergunta se o
    # cargo esta' ENTRE os autorizados daquele perfil.
    votos: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    acessos: Dict[str, int] = defaultdict(int)
    for cargo_rh, perfil in pares_cargo_perfil:
        if not cargo_rh or cargo_rh in cargos_da_matriz:
            continue
        autorizados = cargos_por_perfil.get(perfil)
        if not autorizados:
            continue          # perfil fora da matriz nao vota
        acessos[cargo_rh] += 1
        for alvo in autorizados:
            votos[cargo_rh][alvo] += 1

    fora: Dict[str, EquivalenciaCargo] = {}
    for cargo_rh, contagem in votos.items():
        total = acessos[cargo_rh]
        if total < min_acessos:
            continue
        # empate resolvido pelo nome, para o resultado nao depender da ordem
        # em que os acessos foram lidos (o de-para vai para a tela e precisa
        # ser o mesmo a cada processamento).
        alvo, n = max(sorted(contagem.items()), key=lambda kv: kv[1])
        consistencia = n / total
        if consistencia >= limiar:
            fora[cargo_rh] = EquivalenciaCargo(cargo_rh, alvo, n, consistencia)
    return fora
