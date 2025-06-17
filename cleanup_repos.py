import os

# Caminhos
repos_pasta = "repos"
repos_txt = "repositorios_star.txt"

# Lê os repositórios desejados a partir do .txt
with open(repos_txt, 'r', encoding='utf-8') as f:
    desejados = set(url.strip().split('/')[-1] for url in f if url.strip())

# Lista o que está na pasta
atuais = set(os.listdir(repos_pasta))

# Determina quais devem ser removidos
a_remover = atuais - desejados

# Remove diretórios não desejados
for repo in a_remover:
    caminho = os.path.join(repos_pasta, repo)
    if os.path.isdir(caminho):
        print(f"🗑️ Removendo: {repo}")
        os.system(f'rmdir /s /q "{caminho}"')  # para Windows
