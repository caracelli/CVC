from enum import Enum


class TipoDivergencia(Enum):
    ACESSO_DESLIGADO = "ACESSO_DESLIGADO"
    ACESSO_TRANSFERIDO = "ACESSO_TRANSFERIDO"
    PERFIL_INVALIDO = "PERFIL_INVALIDO"
    PERFIL_EXCESSIVO = "PERFIL_EXCESSIVO"
    ACESSO_SEM_VINCULO_RH = "ACESSO_SEM_VINCULO_RH"
    # Conta de SERVICO (robo/automacao) que casou com uma pessoa desligada
    # porque foi cadastrada com o e-mail de quem a criou. Tipo PROPRIO, e nao
    # ausencia de linha: robo nao se revoga porque quem o cadastrou saiu
    # (revogar derruba producao), mas sumir com a linha esconderia um
    # classificacao errada. Sai da lista de revogacao; continua consultavel.
    ACESSO_CONTA_SERVICO = "ACESSO_CONTA_SERVICO"
