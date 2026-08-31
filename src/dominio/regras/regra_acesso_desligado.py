import re
import uuid
from typing import List, Optional, Sequence
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.funcionario_desligado import FuncionarioDesligado
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia
# Semantica do status e' UNICA no dominio (situacao_conta): uma conta bloqueada
# de um desligado NAO e' irregularidade de acesso — ja esta revogada. Ex.: o SIG
# traz ~58% das contas como BLOQUEADO.
from ..objetos_valor.situacao_conta import conta_ativa as _conta_ativa


def _norm_cpf(valor: Optional[str]) -> str:
    """CPF canonico p/ matching: 11 digitos (zfill preserva zeros a esquerda
    perdidos quando salvo como numero). Devolve '' quando nao da p/ casar com
    seguranca — !=11 digitos (parcial/mascarado/CNPJ) ou todos iguais
    (000...00 / 111...11, invalidos que colidiriam)."""
    d = re.sub(r"\D", "", valor or "")
    if not d:
        return ""
    p = d.zfill(11)
    if len(p) != 11 or len(set(p)) == 1:
        return ""
    return p


class RegraAcessoDesligado:
    """Detecta acesso ATIVO de funcionario desligado.

    Matching por UNIAO de chaves (mesma filosofia da cascata multi-chave da
    Fase 1): o acesso e' de um desligado se a MATRICULA vinculada, o CPF do
    extrato OU o LOGIN baterem com um desligado. Casar so por matricula subconta
    (o passo de vinculo cruza contra ATIVOS, entao o acesso de um desligado
    costuma ficar sem matricula anexada); o CPF do extrato fecha parte da lacuna
    e o LOGIN fecha o resto — e' a unica chave do OU_Desligados do diretorio AD,
    que nao tem matricula de RH. Uma linha que bate por varias chaves gera UMA
    divergencia (sem dobra).

    RECONTRATADO — REGRA DA AREA (Bruna, 10/08/2026), textual:
      "se tiver ativo e for o mesmo login pode considerar ok;
       agora se ele for um ativo com o login diferente precisa apontar"

    A MESMA PESSOA aparece desligada com a matricula antiga e ativa com uma nova
    (a base traz ativos '9000xxxx' e desligados '345xxxxx' — re-matriculacao).
    O motor casava pelo CPF/login da matricula antiga e marcava como "acesso de
    desligado" a conta que ela USA HOJE.

    Entao a pergunta nao e' "a pessoa esta ativa?", e sim, quando ela esta:
      - a conta e' o MESMO login que ela usa hoje -> nada a fazer, sai da lista;
      - e' um login DIFERENTE  -> APONTA: e' identidade antiga que sobrou viva,
        exatamente o que precisa ser revogado.
    Quem nao esta ativo segue pelo matching normal (e' desligado mesmo).

    Medido na base entregue: dos 1.794 pares desligado x ativo, 1.790 (99,8%)
    mantiveram o mesmo login; so 4 voltaram com login diferente — e sao esses
    que a area quer ver.
    """

    def __init__(self, prefixos_conta_servico: Optional[Sequence[str]] = None):
        # auditoria: acessos que sairam por serem o MESMO login de quem esta ativo
        self.recontratados_suprimidos = 0
        # auditoria: acessos MANTIDOS por serem login diferente de quem voltou
        self.login_diferente_apontado = 0
        # CONTA DE SERVICO — prefixos de login vindos do config.xml
        # (validacao/conta_servico/prefixos_login). Vazio = regra desligada, o
        # comportamento anterior. Ver `_e_conta_servico`.
        self._prefixos_servico = tuple(
            p.strip().upper() for p in (prefixos_conta_servico or []) if p and p.strip())
        # auditoria: acessos que viraram ACESSO_CONTA_SERVICO em vez de _DESLIGADO
        self.contas_servico = 0

    def _e_conta_servico(self, login: Optional[str]) -> bool:
        """O login e' de uma conta de servico (robo/automacao)?

        Criterio: PREFIXO do login, parametrizado no config. Medido em
        28/08-31/08/2026 sobre as 432 linhas de ACESSO_DESLIGADO do E2E dos 7
        sistemas: o prefixo `SIST` pega 297 (69%), e os dois sinais disponiveis
        concordam 297/297 — nenhum `SIST*` parece pessoa (os 10 logins sao ROBO
        MARITIMO, AUTOMACAO RPA SOLO, PROJETO JENKINS, ...) e nenhum robo tem
        login fora do prefixo. Por isso o criterio e' SO' o prefixo: uma lista
        de termos do nome nao pegaria uma linha a mais.
        O nome do robo segue util como CONFERENCIA, nao como criterio — ver
        `divergiu_do_nome`.
        """
        if not self._prefixos_servico:
            return False
        lg = (login or "").strip().upper()
        return bool(lg) and lg.startswith(self._prefixos_servico)

    # Termos que aparecem no NOME das contas de servico desta base. NAO sao
    # criterio (nao pegam nada que o prefixo ja nao pegue); servem para detectar
    # que a PREMISSA mudou: um login com nome de robo e sem o prefixo, ou um
    # login com o prefixo e nome de gente. Quando isso acontecer, a area precisa
    # rever a lista de prefixos — por isso o contador abaixo e' logado.
    _TERMOS_NOME_SERVICO = ("ROBO", "ROBÔ", "AUTOMACAO", "AUTOMAÇÃO", "RPA",
                            "JENKINS", "BRCVCSRV", "SISTEMIC", "SISTÊMIC",
                            "-- SISTEMA")

    def _nome_de_servico(self, nome: Optional[str]) -> bool:
        n = (nome or "").upper()
        return any(t in n for t in self._TERMOS_NOME_SERVICO)

    def verificar(
        self,
        acessos: List[PerfilAcesso],
        desligados: List[FuncionarioDesligado],
        ativos: Optional[List] = None,
    ) -> List[Divergencia]:
        self.recontratados_suprimidos = 0
        self.login_diferente_apontado = 0
        self.contas_servico = 0
        # Conferencia da premissa (ver `_TERMOS_NOME_SERVICO`): quantas vezes o
        # prefixo e o nome DISCORDARAM. Zero na base medida; qualquer numero
        # acima disso e' pedido de revisao da lista de prefixos.
        self.divergiu_do_nome = 0
        ativos = ativos or []
        matriculas_ativas = {a.matricula for a in ativos if a.matricula}
        cpfs_ativos = {c for c in (_norm_cpf(a.cpf) for a in ativos) if c}
        # LOGINS que as pessoas ATIVAS usam hoje: o login do diretorio (AD) mais
        # o usuario de toda conta ja vinculada a uma matricula ativa. E' contra
        # este conjunto que se decide "mesmo login" x "login diferente".
        logins_ativos = {lg for lg in (
            (getattr(a, "login", "") or "").strip().lower() for a in ativos) if lg}
        for _ac in acessos:
            if _ac.matricula_vinculada in matriculas_ativas:
                _u = (_ac.usuario or "").strip().lower()
                if _u:
                    logins_ativos.add(_u)

        matriculas_desligadas = {d.matricula for d in desligados if d.matricula}
        # matricula do desligado -> CPF, p/ saber se a PESSOA daquele desligado
        # esta ativa hoje (o CPF e' a chave estavel entre as duas matriculas)
        cpf_do_desligado = {d.matricula: _norm_cpf(d.cpf)
                            for d in desligados if d.matricula}
        # CPF -> matricula do desligado (p/ preencher a matricula quando o match
        # veio so pelo CPF). Primeiro desligado vence em caso de CPF repetido.
        cpf_para_matricula = {}
        for d in desligados:
            c = _norm_cpf(d.cpf)
            if c and c not in cpf_para_matricula:
                cpf_para_matricula[c] = d.matricula
        # LOGIN (minusculo) -> matricula do desligado. Chave do AD.
        login_para_matricula = {}
        for d in desligados:
            lg = (getattr(d, "login", "") or "").strip().lower()
            if lg and lg not in login_para_matricula:
                login_para_matricula[lg] = d.matricula

        divergencias = []
        for acesso in acessos:
            # So conta desligado com acesso REALMENTE ativo — conta bloqueada/
            # inativa ja esta revogada, nao e' divergencia.
            if not _conta_ativa(acesso.situacao):
                continue

            mat_vinc = acesso.matricula_vinculada

            casou_matricula = bool(mat_vinc) and mat_vinc in matriculas_desligadas

            cpf_acesso = _norm_cpf(acesso.cpf)
            matricula_por_cpf = cpf_para_matricula.get(cpf_acesso) if cpf_acesso else None

            login_acesso = (acesso.usuario or "").strip().lower()
            matricula_por_login = (login_para_matricula.get(login_acesso)
                                   if login_acesso else None)

            if not casou_matricula and matricula_por_cpf is None \
                    and matricula_por_login is None:
                continue

            # ---- REGRA DA AREA: a pessoa deste acesso esta ATIVA hoje? ----
            # Ela esta ativa se a propria conta ja pertence a uma matricula ativa,
            # se o CPF do extrato e' de um ativo, ou se o CPF do desligado que
            # casou aparece entre os ativos (a re-matriculacao classica).
            _mat_deslig = (mat_vinc if casou_matricula
                           else matricula_por_cpf or matricula_por_login)
            pessoa_ativa = (
                (mat_vinc and mat_vinc in matriculas_ativas)
                or (cpf_acesso and cpf_acesso in cpfs_ativos)
                or (cpf_do_desligado.get(_mat_deslig, "") in cpfs_ativos
                    if cpf_do_desligado.get(_mat_deslig, "") else False)
            )
            if pessoa_ativa:
                if login_acesso and login_acesso in logins_ativos:
                    # mesmo login de quem esta ativo -> "pode considerar ok"
                    self.recontratados_suprimidos += 1
                    continue
                # ativo com login DIFERENTE -> "precisa apontar": identidade
                # antiga que sobrou viva. Segue e vira divergencia.
                self.login_diferente_apontado += 1

            # Matricula da divergencia: a vinculada (quando bateu), senao a
            # resolvida pelo CPF e por fim a do login (AD).
            matricula = (mat_vinc if casou_matricula
                         else matricula_por_cpf or matricula_por_login)

            # ---- CONTA DE SERVICO (retorno da area, 28/08 e 31/08/2026) ----
            # "porque ta vindo uns usuarios sistemicos nos desligados" — o robo
            # foi cadastrado com o e-mail de quem o criou; quando a pessoa saiu,
            # ele virou "acesso de desligado a revogar". Revogar derruba
            # producao. Vira tipo PROPRIO: sai da revogacao, continua visivel.
            if self._e_conta_servico(acesso.usuario):
                self.contas_servico += 1
                if not self._nome_de_servico(acesso.nome_usuario):
                    self.divergiu_do_nome += 1
                divergencias.append(
                    Divergencia(
                        id=str(uuid.uuid4()),
                        tipo=TipoDivergencia.ACESSO_CONTA_SERVICO,
                        sistema=acesso.sistema,
                        usuario=acesso.usuario,
                        nome_usuario=acesso.nome_usuario,
                        matricula=matricula,
                        perfil_encontrado=acesso.perfil,
                        descricao=(
                            f"Conta de serviço (robô/automação) vinculada a uma "
                            f"pessoa desligada no sistema {acesso.sistema.value}. "
                            f"Não revogar por desligamento: o vínculo é o e-mail "
                            f"de quem cadastrou a conta, não um usuário humano."
                        ),
                    )
                )
                continue

            if self._e_conta_servico(acesso.usuario) is False \
                    and self._nome_de_servico(acesso.nome_usuario):
                # nome de robo SEM o prefixo: a premissa mudou, a area precisa
                # rever a lista. Segue como desligado (nao adivinho por nome).
                self.divergiu_do_nome += 1

            divergencias.append(
                Divergencia(
                    id=str(uuid.uuid4()),
                    tipo=TipoDivergencia.ACESSO_DESLIGADO,
                    sistema=acesso.sistema,
                    usuario=acesso.usuario,
                    nome_usuario=acesso.nome_usuario,
                    matricula=matricula,
                    perfil_encontrado=acesso.perfil,
                    descricao=(
                        f"Funcionário desligado com acesso ativo "
                        f"no sistema {acesso.sistema.value}"
                    ),
                )
            )
        return divergencias
