"""Semantica UNICA dos status de conta que vem dos extratos dos sistemas.

Cada sistema escreve o status do seu jeito (ATIVO, ACTIVE, BLOQUEADO, A, P, D,
I, vazio...). Antes de existir este modulo cada regra interpretava por conta
propria — e a validacao de perfil simplesmente IGNORAVA o status, tratando uma
conta BLOQUEADA como se fosse acesso vivo.

Regra combinada com a area (22/07/2026) e confirmada nos dados (29/07):
  - BLOQUEADO / INATIVO / suspensa  -> conta SEM acesso efetivo (ja revogada):
    nao e' acesso para nenhuma regra;
  - ATIVO (e sinonimos)             -> acesso vivo;
  - DESLIGADO ('D' do IC)           -> a conta continua VIVA (por isso e' acesso,
    e alimenta o motor de desligados); 100% dos 'D' medidos no extrato do IC
    estao na base de RH desligados — dai o significado;
  - qualquer outra coisa, inclusive VAZIO e 'P' (pendente) -> INDEFINIDA: NAO se
    assume ativo. O acesso e' considerado existente, mas a validacao sai como
    "Em Analise" para revisao humana.
"""

# Conta listada no extrato mas sem acesso efetivo (revogada/desativada).
SEM_ACESSO = {
    "INATIVO", "INACTIVE", "BLOQUEADO", "BLOCKED",
    "SUSPENSO", "DESATIVADO", "CANCELADO", "I", "B",
}

# Conta com acesso efetivo.
ATIVA = {"ATIVO", "ACTIVE", "A", "HABILITADO", "LIBERADO", "ENABLED"}

# Conta de pessoa desligada que continua existindo no sistema. E' acesso vivo
# (por isso NAO entra em SEM_ACESSO) e o motor de desligados a captura.
DESLIGADA = {"DESLIGADO", "D", "TERMINATED"}


def normalizar(situacao) -> str:
    return str(situacao or "").strip().upper()


def sem_acesso_efetivo(situacao) -> bool:
    """True quando a conta esta revogada/desativada no proprio sistema."""
    return normalizar(situacao) in SEM_ACESSO


def conta_ativa(situacao) -> bool:
    """True quando a conta representa acesso vivo. Compatibilidade: tudo que
    NAO esta em SEM_ACESSO conta como acesso (inclusive vazio e indefinido) —
    quem trata o indefinido de forma especial e' a validacao de perfil."""
    return not sem_acesso_efetivo(situacao)


def indefinida(situacao) -> bool:
    """True quando o extrato nao diz se a conta esta ativa: vazio, 'P'
    (pendente) ou qualquer valor desconhecido. Nao se assume ATIVO — a
    validacao marca "Em Analise"."""
    s = normalizar(situacao)
    return s not in ATIVA and s not in SEM_ACESSO and s not in DESLIGADA
