import re
import csv
from pydriller import Repository

# Lê a lista de repositórios do arquivo
with open('repositorios.txt', 'r', encoding='utf-8') as f:
    repositorios = [line.strip() for line in f if line.strip()]

# Regex para migração de Promise para async/await
promise_re = re.compile(r'\.then\s*\(|new\s+Promise\s*\(')
async_await_re = re.compile(r'\basync\b|\bawait\b')

# CSV Headers
headers = [
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

for repo in repositorios:
    project_name = repo.rstrip("/").split("/")[-1]
    output_csv = f"migracoes_{project_name}.csv"

    print(f"🔍 Analisando repositório: {repo}")

    with open(output_csv, mode="w", newline='', encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()

        try:
            for commit in Repository(repo , only_in_branch=None).traverse_commits():
                if commit.merge:
                    continue

                for mod in commit.modified_files:                    
                    if (
                        mod.filename and mod.filename.endswith((".js", ".ts")) and
                        not mod.filename.endswith((".min.js", ".min.ts")) and  # 🚫 Ignorar minificados
                        mod.source_code_before and mod.source_code
                    ):

                        removed_lines = []
                        added_lines = []

                        for line in mod.diff.split("\n"):
                            if line.startswith("-") and promise_re.search(line):
                                removed_lines.append(line.strip())
                            if line.startswith("+") and async_await_re.search(line):
                                added_lines.append(line.strip())

                        if removed_lines and added_lines:
                            writer.writerow({
                                "repo": repo,
                                "commit_hash": commit.hash,
                                "author": commit.author.name,
                                "date": commit.author_date,
                                "message": commit.msg.strip(),
                                "file_path": mod.new_path or mod.old_path,
                                "commit_url": f"{repo}/commit/{commit.hash}",
                                "removed_lines": "\n".join(removed_lines),
                                "added_lines": "\n".join(added_lines),
                            })
        except Exception as e:
            print(f"⚠️ Erro ao processar {repo}: {e}")
