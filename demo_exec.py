import re
import csv
from pydriller import Repository
from typing import Tuple


# Regexs principais
promise_re     = re.compile(r'\bnew\s+Promise\s*\(|\.then\s*\(')
async_await_re = re.compile(r'\basync\b|\bawait\b')
comment_start_re = re.compile(r'^\s*/\*')          # início de bloco de comentário
comment_end_re   = re.compile(r'.*\*/\s*$')        # fim de bloco de comentário
line_comment_re  = re.compile(r'^\s*//')           # comentário de linha

identifier_re   = re.compile(r'\b[a-zA-Z_]\w*\b')   # para checar palavras em comum

def strip_inline_comments(line: str) -> str:
    # remove //… e /*…*/ inline simplificadamente
    line = re.sub(r'//.*', '', line)
    line = re.sub(r'/\*.*?\*/', '', line)
    return line

def is_comment_line(line: str, in_block: bool) -> Tuple[bool, bool]:
    """Retorna (é_comentário, novo_estado_em_block_comment)."""
    if in_block:
        # estamos dentro de /* … */
        if comment_end_re.match(line):
            return True, False
        return True, True
    else:
        if comment_start_re.match(line):
            # inicia bloco
            return True, not bool(comment_end_re.match(line))
        if line_comment_re.match(line):
            return True, False
    return False, False

def is_promise_line(line: str) -> bool:
    return bool(promise_re.search(line))

def is_async_line(line: str) -> bool:
    return bool(async_await_re.search(line))

def detect_migrations_by_lineno(removed, added, window=5):
    """
    removed e added são listas de tuplas (lineno, texto).
    Retorna lista de (old_text, new_text) que correspondem a migração.
    """
    migrations = []
    # pré-filtragem: ignora comentários e aplica critérios de conteúdo
    filtered_removed = {}
    in_block = False
    for lineno, text in removed:
        line = strip_inline_comments(text)
        is_comment, in_block = is_comment_line(text, in_block)
        if is_comment:
            continue
        if is_promise_line(line) and not is_async_line(line):
            filtered_removed[lineno] = line

    filtered_added = {}
    in_block = False
    for lineno, text in added:
        line = strip_inline_comments(text)
        is_comment, in_block = is_comment_line(text, in_block)
        if is_comment:
            continue
        if is_async_line(line) and not is_promise_line(line):
            filtered_added[lineno] = line

    # faz o casamento por proximidade de linhas
    for lineno, old_line in filtered_removed.items():
        for offset in range(window + 1):
            new_lineno = lineno + offset
            new_line = filtered_added.get(new_lineno)
            if not new_line:
                continue
            # checagens finais de descarte
            if is_async_line(old_line) or is_promise_line(new_line):
                continue
            # checar identificador em comum (opcional)
            migrations.append((old_line.strip(), new_line.strip()))
            break

    return migrations

CSV_HEADERS = [
    "commit_hash","author","message",
    "file_path","commit_url","removed_lines","added_lines"
]

with open('repositorios.txt', 'r', encoding='utf-8') as f:
    repos = [l.strip() for l in f if l.strip()]

for repo in repos:
    project = repo.rstrip("/").split("/")[-1]
    out_csv = f"migracoes_{project}.csv"
    print(f"🔍 Analisando {repo}")
    with open(out_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
        writer.writeheader()
        try:
            for commit in Repository(repo).traverse_commits():
                if commit.merge: continue
                for mod in commit.modified_files:
                    if not mod.diff_parsed: continue
                    if not mod.filename.endswith((".js",".ts")): continue
                    if mod.filename.endswith((".min.js",".min.ts")): continue

                    removed = mod.diff_parsed.get('deleted', [])
                    added   = mod.diff_parsed.get('added',   [])

                    migs = detect_migrations_by_lineno(removed, added)
                    if not migs: continue

                    old_lines, new_lines = zip(*migs)
                    writer.writerow({
                        "commit_hash": commit.hash,
                        "author": commit.author.name,
                        "message": commit.msg.strip(),
                        "file_path": mod.new_path or mod.old_path,
                        "commit_url": f"{repo}/commit/{commit.hash}",
                        "removed_lines": "\n".join(old_lines),
                        "added_lines":   "\n".join(new_lines),
                    })
        except Exception as e:
            print(f"⚠️ Erro em {repo}: {e}")
