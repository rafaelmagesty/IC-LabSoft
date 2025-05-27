import os
import re
import csv
import subprocess
from typing import List
from pydriller import Repository
from unidiff import PatchSet

# Expressões regulares principais
promise_re     = re.compile(r'\bnew\s+Promise\s*\(|\.then\s*\(')
async_await_re = re.compile(r'\basync\b|\bawait\b')
comment_start_re = re.compile(r'^\s*/\*')
comment_end_re   = re.compile(r'.*\*/\s*$')
line_comment_re  = re.compile(r'^\s*//')

CSV_HEADERS = [
    "commit_hash", "author", "message",
    "file_path", "commit_url", "removed_chunk", "added_chunk"
]

def strip_inline_comments(line: str) -> str:
    line = re.sub(r'//.*', '', line)
    line = re.sub(r'/\*.*?\*/', '', line)
    return line

def is_comment_line(line: str, in_block: bool) -> (bool, bool):
    if in_block:
        if comment_end_re.match(line): return True, False
        return True, True
    else:
        if comment_start_re.match(line): return True, not comment_end_re.match(line)
        if line_comment_re.match(line): return True, False
    return False, False

def has_migration(removed_lines: List[str], added_lines: List[str]) -> bool:
    def contains_promise_only(lines):
        in_block = False
        found_promise = False
        for line in lines:
            clean = strip_inline_comments(line)
            is_comment, in_block = is_comment_line(line, in_block)
            if is_comment:
                continue
            if async_await_re.search(clean):  
                return False
            if promise_re.search(clean):
                found_promise = True
        return found_promise

    def contains_async_only(lines):
        in_block = False
        found_async = False
        for line in lines:
            clean = strip_inline_comments(line)
            is_comment, in_block = is_comment_line(line, in_block)
            if is_comment:
                continue
            if promise_re.search(clean):  
                return False
            if async_await_re.search(clean):  
                found_async = True
        return found_async  
    return contains_promise_only(removed_lines) and contains_async_only(added_lines)


def get_patch(repo_path: str, commit_hash: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "show", "--no-ext-diff", "--no-color", "--unified=3", commit_hash],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',       
            errors='replace'
        )
        return result.stdout if result.returncode == 0 else None
    except Exception as e:
        print(f"⚠️ Subprocesso git show falhou: {e}")
        return None

def clonar_repositorios(repos_file: str, destino: str = "repos") -> List[tuple[str, str]]:
    os.makedirs(destino, exist_ok=True)
    lista = []

    with open(repos_file, 'r', encoding='utf-8') as f:
        urls = [l.strip() for l in f if l.strip()]

    for url in urls:
        nome = url.rstrip("/").split("/")[-1]
        local_path = os.path.join(destino, nome)
        if not os.path.exists(local_path):
            print(f"🔄 Clonando {url} → {local_path}")
            result = subprocess.run(["git", "clone", url, local_path])
            if result.returncode != 0:
                print(f"❌ Falha ao clonar {url}")
                continue
        else:
            print(f"✅ Já clonado: {local_path}")
        lista.append((nome, url, local_path))

    return lista

def main():
    repositórios = clonar_repositorios("repositorios.txt")

    for nome, url, path in repositórios:
        print(f"\n🔍 Analisando {nome}")
        out_csv = f"migracoes_{nome}.csv"

        with open(out_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            writer.writeheader()

            try:
                for commit in Repository(path).traverse_commits():
                    if commit.merge:
                        continue

                    patch_text = get_patch(path, commit.hash)
                    if not patch_text:
                        continue

                    try:
                        patch = PatchSet(patch_text)
                    except Exception as e:
                        print(f"❌ Erro ao parsear patch do commit {commit.hash}: {e}")
                        continue

                    for file in patch:
                        if not file.path.endswith((".js", ".ts")):
                            continue
                        if file.path.endswith((".min.js", ".min.ts")):
                            continue

                        for hunk in file:
                            removed = [line.value for line in hunk if line.is_removed]
                            added   = [line.value for line in hunk if line.is_added]

                            if has_migration(removed, added):
                                writer.writerow({
                                    "commit_hash": commit.hash,
                                    "author": commit.author.name,
                                    "message": commit.msg.strip(),
                                    "file_path": file.path,
                                    "commit_url": f"{url}/commit/{commit.hash}",
                                    "removed_chunk": "\n".join(removed),
                                    "added_chunk": "\n".join(added),
                                })
            except Exception as e:
                print(f"⚠️ Erro ao processar {nome}: {e}")

if __name__ == "__main__":
    main()
