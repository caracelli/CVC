"""Monta ENTREGA_REDE_completo.zip — UM zip so com toda a rede pronta.

Conteudo do zip:
  ENTREGA_REDE_completo/
    LEIA-ME.txt
    REDE/
      CVC_IAM_ANALYTICS/
        EXECUTAVEIS/
          visualizador.exe, Processador.exe, CONFIG/, REPORT/, LEIA-ME.md
          launcher/
            launcher_atualizador.exe
            launcher_visualizador.exe
            launcher_processador.exe       <- TODOS os 5 exes aqui
        ENTRADA/  (com arquivos prontos pro primeiro processamento)
        DADOS/    (esqueleto vazio)
        INTERACOES/
    ATUALIZACAO/  (config v+1 pra demo do auto-update)

Tamanho final esperado: ~116 MB. **Nao cabe no limite 100 MB do GitHub** —
o .gitignore evita o push acidental, gera so localmente.

Uso:
    cd CVC
    python deploy/build_entrega_completa.py

Depois: copiar REDE/CVC_IAM_ANALYTICS/ pra Z:\\CVC\\CVC_IAM_ANALYTICS/.
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Reusa funcoes do build_entrega_rede
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_entrega_rede as B  # noqa: E402


def main():
    print("=== Build ENTREGA_REDE_completo (UM zip, ~116 MB) ===")
    B.checar_prerequisitos()

    if B.STAGING.exists():
        shutil.rmtree(B.STAGING)
    B.STAGING.mkdir(parents=True, exist_ok=True)
    B.ENTREGA.mkdir(parents=True, exist_ok=True)

    base = B.STAGING / "ENTREGA_REDE_completo"
    base.mkdir()
    (base / "LEIA-ME.txt").write_text(B.LEIA_ME, encoding="utf-8")

    # Reusa o montar_rede (sem motor) e adiciona o motor por cima
    rede_path = base / "REDE"
    B.montar_rede(rede_path)
    B._montar_motor_separado(rede_path)
    B.montar_atualizacao(base / "ATUALIZACAO")

    inicio = datetime.now()
    alvo = B.ENTREGA / "ENTREGA_REDE_completo.zip"
    B.zipar(base, alvo)
    shutil.rmtree(B.STAGING)
    sz = alvo.stat().st_size / 1024 / 1024
    print(f"\nOK -> {alvo}  ({sz:.1f} MB)")
    print(f"Concluido em {(datetime.now()-inicio).total_seconds():.1f}s.")
    print()
    print("Como usar:")
    print(f"  1. Extrair {alvo.name} em uma pasta temporaria")
    print("  2. Copiar REDE/CVC_IAM_ANALYTICS/ para Z:/CVC/CVC_IAM_ANALYTICS/")
    print("  3. Em uma maquina-cliente, abrir Z:/CVC/CVC_IAM_ANALYTICS/EXECUTAVEIS/")
    print("     ou usar o ENTREGA_REDE_cliente.zip pra instalar local")
    if sz > 100:
        print()
        print("AVISO: zip > 100 MB — nao cabe no GitHub. Foi adicionado ao "
              ".gitignore. Distribua manualmente (OneDrive/pendrive).")


if __name__ == "__main__":
    main()
