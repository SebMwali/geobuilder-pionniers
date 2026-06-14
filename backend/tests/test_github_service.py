"""
Tests P2A — github_service (mocké).

Périmètre strict :
- aucun appel réseau (PyGithub mocké via unittest.mock)
- aucune modification du code de production
- valide : création (404→create_file), mise à jour (sha existant→update_file),
  push binaire, URL GitHub Pages, branche/repo via env, erreurs, singleton
"""
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from github import GithubException

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services import github_service  # noqa: E402
from services.github_service import GitHubService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_404():
    """Erreur PyGithub 'NOT FOUND' (statut 404) — déclenche create_file."""
    return GithubException(status=404, data={"message": "Not Found"}, headers={})


def _make_other_error(status=500):
    return GithubException(status=status, data={"message": "boom"}, headers={})


@pytest.fixture(autouse=True)
def _reset_singleton_and_env(monkeypatch):
    """Réinitialise le singleton + variables d'env avant chaque test."""
    # Reset singleton interne (instance + cache repo/client)
    github_service._service = None
    GitHubService._instance = None
    # On force la création d'une nouvelle instance "vierge"
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPO", "SebMwali/geobuilder-pionniers")
    monkeypatch.setenv("GITHUB_BRANCH", "main")
    monkeypatch.setenv("GITHUB_PAGES_URL", "https://sebmwali.github.io/geobuilder-pionniers")
    yield
    github_service._service = None
    GitHubService._instance = None


def _fresh_service_with_mock_repo():
    """Construit une instance GitHubService avec un repo mocké injecté directement."""
    svc = GitHubService()
    mock_repo = MagicMock(name="Repo")
    svc._repo = mock_repo  # bypass _get_repo() : on a déjà le repo
    svc._client = MagicMock(name="GhClient")
    return svc, mock_repo


# ---------------------------------------------------------------------------
# Tests — initialisation / config
# ---------------------------------------------------------------------------
class TestInit:
    def test_get_repo_raises_when_token_missing(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "")
        svc = GitHubService()
        svc._repo = None
        with pytest.raises(RuntimeError, match="GITHUB_TOKEN missing"):
            svc._get_repo()

    def test_get_repo_uses_env_repo_name(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "OtherOwner/other-repo")
        with patch.object(github_service, "Github") as MockGh:
            mock_client = MagicMock()
            MockGh.return_value = mock_client
            svc = GitHubService()
            svc._repo = None
            svc._get_repo()
            MockGh.assert_called_once_with("fake-token")
            mock_client.get_repo.assert_called_once_with("OtherOwner/other-repo")

    def test_get_repo_is_cached(self, monkeypatch):
        with patch.object(github_service, "Github") as MockGh:
            mock_client = MagicMock()
            MockGh.return_value = mock_client
            svc = GitHubService()
            svc._repo = None
            svc._get_repo()
            svc._get_repo()
            svc._get_repo()
            # Github(token) appelé 1 seule fois grâce au cache
            assert MockGh.call_count == 1
            assert mock_client.get_repo.call_count == 1


# ---------------------------------------------------------------------------
# Tests — push_file (texte)
# ---------------------------------------------------------------------------
class TestPushFile:
    def test_creates_file_when_not_found(self):
        svc, repo = _fresh_service_with_mock_repo()
        repo.get_contents.side_effect = _make_404()
        url = svc.push_file("docs/test/hello.html", "<p>hi</p>", "Add test")
        repo.create_file.assert_called_once_with(
            path="docs/test/hello.html",
            message="Add test",
            content="<p>hi</p>",
            branch="main",
        )
        repo.update_file.assert_not_called()
        assert url == "https://sebmwali.github.io/geobuilder-pionniers/test/hello.html"

    def test_updates_file_when_exists(self):
        svc, repo = _fresh_service_with_mock_repo()
        existing = MagicMock()
        existing.sha = "abc123sha"
        repo.get_contents.return_value = existing
        url = svc.push_file("docs/test/hello.html", "<p>new</p>", "Update test")
        repo.update_file.assert_called_once_with(
            path="docs/test/hello.html",
            message="Update test",
            content="<p>new</p>",
            sha="abc123sha",
            branch="main",
        )
        repo.create_file.assert_not_called()
        assert url.endswith("/test/hello.html")

    def test_propagates_non_404_errors(self):
        svc, repo = _fresh_service_with_mock_repo()
        repo.get_contents.side_effect = _make_other_error(500)
        with pytest.raises(GithubException):
            svc.push_file("docs/x.html", "x", "msg")
        repo.create_file.assert_not_called()
        repo.update_file.assert_not_called()

    def test_uses_env_branch(self, monkeypatch):
        monkeypatch.setenv("GITHUB_BRANCH", "production")
        svc, repo = _fresh_service_with_mock_repo()
        repo.get_contents.side_effect = _make_404()
        svc.push_file("docs/x.html", "y", "m")
        assert repo.create_file.call_args.kwargs["branch"] == "production"


# ---------------------------------------------------------------------------
# Tests — push_binary_file (PDF/PNG)
# ---------------------------------------------------------------------------
class TestPushBinary:
    def test_creates_binary_when_not_found(self):
        svc, repo = _fresh_service_with_mock_repo()
        repo.get_contents.side_effect = _make_404()
        url = svc.push_binary_file("docs/cartes/PIO-1/carte.png", b"\x89PNG...", "Add PNG")
        repo.create_file.assert_called_once_with(
            path="docs/cartes/PIO-1/carte.png",
            message="Add PNG",
            content=b"\x89PNG...",
            branch="main",
        )
        assert url == "https://sebmwali.github.io/geobuilder-pionniers/cartes/PIO-1/carte.png"

    def test_updates_binary_when_exists(self):
        svc, repo = _fresh_service_with_mock_repo()
        existing = MagicMock()
        existing.sha = "deadbeef"
        repo.get_contents.return_value = existing
        svc.push_binary_file("docs/p.pdf", b"%PDF-1.4", "Update PDF")
        repo.update_file.assert_called_once_with(
            path="docs/p.pdf",
            message="Update PDF",
            content=b"%PDF-1.4",
            sha="deadbeef",
            branch="main",
        )

    def test_propagates_non_404_binary(self):
        svc, repo = _fresh_service_with_mock_repo()
        repo.get_contents.side_effect = _make_other_error(403)
        with pytest.raises(GithubException):
            svc.push_binary_file("docs/x.pdf", b"x", "m")


# ---------------------------------------------------------------------------
# Tests — URL GitHub Pages
# ---------------------------------------------------------------------------
class TestPublicUrl:
    def test_strips_docs_prefix(self):
        svc, _ = _fresh_service_with_mock_repo()
        assert svc._public_url("docs/passeports/INST-1/index.html") == (
            "https://sebmwali.github.io/geobuilder-pionniers/passeports/INST-1/index.html"
        )

    def test_keeps_path_without_docs_prefix(self):
        svc, _ = _fresh_service_with_mock_repo()
        assert svc._public_url("portail/PIO-1/index.html") == (
            "https://sebmwali.github.io/geobuilder-pionniers/portail/PIO-1/index.html"
        )

    def test_respects_env_pages_url(self, monkeypatch):
        monkeypatch.setenv("GITHUB_PAGES_URL", "https://custom.example.com/sub")
        svc, _ = _fresh_service_with_mock_repo()
        assert svc._public_url("docs/a/b.html") == "https://custom.example.com/sub/a/b.html"

    def test_trims_trailing_slash_on_base(self, monkeypatch):
        monkeypatch.setenv("GITHUB_PAGES_URL", "https://x.example.com/")
        svc, _ = _fresh_service_with_mock_repo()
        # Pas de double slash
        url = svc._public_url("docs/a.html")
        assert url == "https://x.example.com/a.html"
        assert "//a" not in url.replace("https://", "")


# ---------------------------------------------------------------------------
# Tests — singleton get_github_service()
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_get_github_service_returns_same_instance(self):
        a = github_service.get_github_service()
        b = github_service.get_github_service()
        assert a is b
