import re
import csv
from pydriller import Repository

# Regex para migração de Promise para async/await
promise_re     = re.compile(r'\.then\s*\(|new\s+Promise\s*\(')
async_await_re = re.compile(r'\basync\b|\bawait\b')

def is_promise_line(line: str) -> bool:
    """Retorna True se a linha contiver .then( ou new Promise(."""
    return bool(promise_re.search(line))

def is_async_line(line: str) -> bool:
    """Retorna True se a linha contiver async ou await."""
    return bool(async_await_re.search(line))

def detect_migrations_by_lineno(removed, added, window=5):
    """
    removed e added são listas de tuplas (lineno, texto).
    Para cada linha removida com .then ou new Promise, busca uma linha
    adicionada com async/await no mesmo lineno ou até `window` linhas abaixo,
    e que NÃO contenha .then ou new Promise.
    """
    migrations = []
    removed_map = {lineno: text for lineno, text in removed}
    added_map   = {lineno: text for lineno, text in added}

    for lineno, old_text in removed_map.items():
        if not is_promise_line(old_text):
            continue
        # tenta correspondência no mesmo lineno e nos próximos `window` linhas
        for offset in range(window + 1):
            new_lineno = lineno + offset
            candidate = added_map.get(new_lineno)
            if (candidate 
                and is_async_line(candidate) 
                and not is_promise_line(candidate)
            ):
                migrations.append((old_text.strip(), candidate.strip()))
                break
    return migrations

CSV_HEADERS = [
    "repo",
    "commit_hash",
    "author",
    "date",
    "message",
    "file_path",
    "commit_url",
    "removed_lines",
    "added_lines"
]

# Leitura dos repositórios e processamento
with open('repositorios.txt', 'r', encoding='utf-8') as f:
    repositorios = [line.strip() for line in f if line.strip()]

for repo in repositorios:
    project_name = repo.rstrip("/").split("/")[-1]
    output_csv = f"migracoes_{project_name}.csv"

    print(f"🔍 Analisando repositório: {repo}")

    with open(output_csv, mode="w", newline='', encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADERS)
        writer.writeheader()

        try:
            for commit in Repository(repo, only_in_branch=None).traverse_commits():
                if commit.merge:
                    continue

                for mod in commit.modified_files:
                    if not mod.filename or not mod.filename.endswith((".js", ".ts")):
                        continue
                    if mod.filename.endswith((".min.js", ".min.ts")):
                        continue
                    if not mod.diff_parsed:
                        continue

                    diff_dict = mod.diff_parsed
                    removed = diff_dict.get('deleted', [])
                    added   = diff_dict.get('added',   [])

                    migrations = detect_migrations_by_lineno(removed, added, window=5)
                    if migrations:
                        removed_lines, added_lines = zip(*migrations)
                        writer.writerow({
                            "repo": repo,
                            "commit_hash": commit.hash,
                            "author": commit.author.name,
                            "date": commit.author_date,
                            "message": commit.msg.strip(),
                            "file_path": mod.new_path or mod.old_path,
                            "commit_url": f"{repo}/commit/{commit.hash}",
                            "removed_lines": "\n".join(removed_lines),
                            "added_lines":   "\n".join(added_lines),
                        })
        except Exception as e:
            print(f"⚠️ Erro ao processar {repo}: {e}")
