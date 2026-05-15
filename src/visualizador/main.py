import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# main.py → src/visualizador → src → raiz do projeto
_script_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_script_dir)
PROJECT_ROOT = os.path.dirname(_src_dir)

EXPRESSIONS_FILES = [
    os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS', 'POWER_BI',
                 'CVC_IAM_Analytics.Dataset', 'definition', 'expressions.tmdl'),
    os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS', 'POWER_BI_DEV',
                 'CVC_IAM_Analytics.Dataset', 'definition', 'expressions.tmdl'),
]

PBIP_FILE = os.path.join(
    PROJECT_ROOT, 'CVC_IAM_ANALYTICS', 'POWER_BI', 'CVC_IAM_Analytics.pbip'
)

_PATTERN = re.compile(r'(expression CaminhoBase = ")([^"]*)(" meta )')


def atualizar_caminho_base():
    caminho_base = os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS') + os.sep

    for tmdl in EXPRESSIONS_FILES:
        if not os.path.isfile(tmdl):
            print(f"  [AVISO] não encontrado: {tmdl}")
            continue

        with open(tmdl, 'r', encoding='utf-8') as f:
            original = f.read()

        atualizado = _PATTERN.sub(
            lambda m: m.group(1) + caminho_base + m.group(3),
            original
        )

        if atualizado != original:
            with open(tmdl, 'w', encoding='utf-8') as f:
                f.write(atualizado)
            print(f"  [ATUALIZADO] {tmdl}")
        else:
            print(f"  [SEM ALTERAÇÃO] {tmdl}")

    return caminho_base


def abrir_power_bi():
    if not os.path.isfile(PBIP_FILE):
        print(f"  [ERRO] arquivo .pbip não encontrado: {PBIP_FILE}")
        return
    print(f"  Abrindo: {PBIP_FILE}")
    os.startfile(PBIP_FILE)


def main():
    print("=" * 55)
    print("  IAM Analytics — Visualizador CVC")
    print("=" * 55)

    print(f"\nRaiz do projeto: {PROJECT_ROOT}\n")

    print("Atualizando CaminhoBase nos arquivos TMDL...")
    caminho_base = atualizar_caminho_base()
    print(f"  CaminhoBase -> {caminho_base}\n")

    print("Abrindo Power BI Desktop...")
    abrir_power_bi()

    print("\nConcluído.")


if __name__ == "__main__":
    main()
