"""
GitHub service - remplace le Module 16 défaillant.

Pousse les fichiers HTML générés (passeports, certificats, cartes, garanties)
dans le repo SebMwali/geobuilder-pionniers, dossier /docs/, branche main.
GitHub Pages sert automatiquement depuis /docs/.
"""
import os
import base64
import logging
from typing import Optional
from github import Github, GithubException, InputGitTreeElement

logger = logging.getLogger(__name__)


class GitHubService:
    _instance = None
    _client = None
    _repo = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_repo(self):
        if self._repo is not None:
            return self._repo
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if not token:
            raise RuntimeError("GITHUB_TOKEN missing in backend/.env")
        repo_name = os.environ.get("GITHUB_REPO", "SebMwali/geobuilder-pionniers")
        self._client = Github(token)
        self._repo = self._client.get_repo(repo_name)
        return self._repo

    def push_file(self, path: str, content: str, commit_message: str) -> str:
        """
        Push un fichier (texte) dans le repo. Crée ou met à jour.
        Renvoie l'URL GitHub Pages publique du fichier.
        """
        branch = os.environ.get("GITHUB_BRANCH", "main")
        repo = self._get_repo()

        try:
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(
                path=path,
                message=commit_message,
                content=content,
                sha=existing.sha,
                branch=branch,
            )
            logger.info(f"Updated {path} on {branch}")
        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    path=path,
                    message=commit_message,
                    content=content,
                    branch=branch,
                )
                logger.info(f"Created {path} on {branch}")
            else:
                raise

        return self._public_url(path)

    def push_binary_file(self, path: str, content_bytes: bytes, commit_message: str) -> str:
        """Push un fichier binaire (PDF, PNG) dans le repo."""
        branch = os.environ.get("GITHUB_BRANCH", "main")
        repo = self._get_repo()
        try:
            existing = repo.get_contents(path, ref=branch)
            repo.update_file(
                path=path,
                message=commit_message,
                content=content_bytes,
                sha=existing.sha,
                branch=branch,
            )
        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    path=path,
                    message=commit_message,
                    content=content_bytes,
                    branch=branch,
                )
            else:
                raise
        return self._public_url(path)

    def delete_file(self, path: str, commit_message: str) -> bool:
        """Supprime un fichier du repo s'il existe. Renvoie True si supprimé,
        False si déjà absent (404)."""
        branch = os.environ.get("GITHUB_BRANCH", "main")
        repo = self._get_repo()
        try:
            existing = repo.get_contents(path, ref=branch)
            repo.delete_file(
                path=path,
                message=commit_message,
                sha=existing.sha,
                branch=branch,
            )
            logger.info(f"Deleted {path} on {branch}")
            return True
        except GithubException as e:
            if e.status == 404:
                logger.info(f"Skip delete {path}: already absent")
                return False
            raise

    def _public_url(self, path: str) -> str:
        base = os.environ.get(
            "GITHUB_PAGES_URL", "https://sebmwali.github.io/geobuilder-pionniers"
        ).rstrip("/")
        # GitHub Pages sert depuis /docs sans préfixe "docs/" dans l'URL
        if path.startswith("docs/"):
            path = path[len("docs/"):]
        return f"{base}/{path}"


_service: Optional[GitHubService] = None


def get_github_service() -> GitHubService:
    global _service
    if _service is None:
        _service = GitHubService()
    return _service
