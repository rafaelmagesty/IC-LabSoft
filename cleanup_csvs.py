# cleanup_csvs.py

import os
import glob

# Arquivos de lista de repositórios
FILES = ["repositorios_star.txt", "repositorios.txt"]

# Constrói o conjunto de nomes de projeto a manter
wanted = set()
for fname in FILES:
    if os.path.exists(fname):
        with open(fname, encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if not url:
                    continue
                proj = url.rstrip("/").split("/")[-1]
                wanted.add(proj)

print(f"Projetos a manter ({len(wanted)}): {sorted(wanted)}\n")

# Percorre todos os CSVs migracoes_*.csv
for path in glob.glob("migracoes_*.csv"):
    # extrai o nome do projeto do CSV
    basename = os.path.basename(path)
    proj = basename[len("migracoes_"):-len(".csv")]
    if proj in wanted:
        print(f"✅ Mantendo {basename}")
    else:
        print(f"🗑️ Removendo {basename}")
        try:
            os.remove(path)
        except Exception as e:
            print(f"   ⚠️ Erro ao remover {basename}: {e}")
