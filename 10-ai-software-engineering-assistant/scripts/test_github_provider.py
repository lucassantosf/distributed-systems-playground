"""
Script de teste/validação rápida do Card 2.2: GithubRepositoryProvider.

Execução:
    docker compose exec api python scripts/test_github_provider.py [owner] [repo]

Exemplo com repo público pequeno (ex: octocat/Hello-World ou kennethreitz/responder):
    docker compose exec api python scripts/test_github_provider.py octocat Hello-World
"""

import sys
from src.infrastructure.github.github_repository_provider import GithubRepositoryProvider
from src.settings import settings


def main():
    owner = sys.argv[1] if len(sys.argv) > 1 else "octocat"
    repo = sys.argv[2] if len(sys.argv) > 2 else "Hello-World"

    print(f"\n🚀 Testando GithubRepositoryProvider com {owner}/{repo}...")
    token = settings.github_token or None
    if token:
        print("🔑 Usando GITHUB_TOKEN configurado.")
    else:
        print("ℹ️ Sem GITHUB_TOKEN (usando limites públicos não autenticados).")

    provider = GithubRepositoryProvider(token=token)

    try:
        files = provider.list_files(owner, repo)
        print(f"\n✅ Sucesso! Total de arquivos recuperados: {len(files)}")
        for f in files:
            preview = f.content.strip().replace("\n", " ")[:60]
            print(f"  * {f.path} ({len(f.content)} bytes) -> preview: {preview}...")

        print("\n🎉 Card 2.2 validado com sucesso!")
    except Exception as e:
        print(f"\n❌ Erro durante o teste: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
