"""Tests for the knowledge-source factory module."""

from unittest.mock import patch

import pytest

from crewai.knowledge.source.text_file_knowledge_source import (
    TextFileKnowledgeSource,
)

from crewai_productfeature_planner.scripts.knowledge_sources import (
    _PRD_GUIDELINES_FILE,
    _PRD_KNOWLEDGE_FILES,
    _PROJECT_ARCHITECTURE_FILE,
    _USER_PREFERENCE_FILE,
    _has_embedder_credentials,
    build_prd_guidelines_knowledge_source,
    build_prd_knowledge_sources,
    build_project_knowledge_source,
    build_user_knowledge_source,
    clear_knowledge_cache,
    get_google_embedder_config,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the knowledge source cache before and after each test."""
    clear_knowledge_cache()
    yield
    clear_knowledge_cache()


# ── Embedder configuration ───────────────────────────────────


class TestGetGoogleEmbedderConfig:
    """Tests for get_google_embedder_config()."""

    def test_returns_google_vertex_provider(self, monkeypatch):
        """Provider must be 'google-vertex' (uses google-genai SDK)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key-123")
        cfg = get_google_embedder_config()
        assert cfg["provider"] == "google-vertex"

    def test_default_model_is_gemini_embedding_001(self, monkeypatch):
        """Default model should be gemini-embedding-001."""
        monkeypatch.delenv("KNOWLEDGE_EMBEDDING_MODEL", raising=False)
        cfg = get_google_embedder_config()
        assert cfg["config"]["model_name"] == "gemini-embedding-001"

    def test_custom_model_via_env(self, monkeypatch):
        """KNOWLEDGE_EMBEDDING_MODEL overrides the default model."""
        monkeypatch.setenv("KNOWLEDGE_EMBEDDING_MODEL", "text-embedding-005")
        cfg = get_google_embedder_config()
        assert cfg["config"]["model_name"] == "text-embedding-005"

    def test_api_key_included_when_set(self, monkeypatch):
        """API key should be added to config when GOOGLE_API_KEY is set."""
        monkeypatch.setenv("GOOGLE_API_KEY", "secret-key")
        cfg = get_google_embedder_config()
        assert cfg["config"]["api_key"] == "secret-key"

    def test_api_key_omitted_when_unset(self, monkeypatch):
        """Config should not contain api_key when GOOGLE_API_KEY is absent."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        cfg = get_google_embedder_config()
        assert "api_key" not in cfg["config"]

    def test_config_is_dict(self, monkeypatch):
        """Return value should be a plain dict."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key-123")
        cfg = get_google_embedder_config()
        assert isinstance(cfg, dict)
        assert isinstance(cfg["config"], dict)

    def test_returns_fresh_dict_each_call(self, monkeypatch):
        """Each call should return a new dict (no shared mutable state)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "key")
        cfg1 = get_google_embedder_config()
        cfg2 = get_google_embedder_config()
        assert cfg1 == cfg2
        assert cfg1 is not cfg2
        assert cfg1["config"] is not cfg2["config"]


# ── Credential detection ─────────────────────────────────────


class TestHasEmbedderCredentials:
    """Tests for _has_embedder_credentials()."""

    def test_true_with_google_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "gk")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert _has_embedder_credentials() is True

    def test_true_with_openai_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
        assert _has_embedder_credentials() is True

    def test_true_with_both_keys(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "gk")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
        assert _has_embedder_credentials() is True

    def test_false_with_no_keys(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert _has_embedder_credentials() is False


# ── Individual knowledge-source factories ─────────────────────


class TestBuildUserKnowledgeSource:
    """Tests for build_user_knowledge_source()."""

    def test_returns_text_file_knowledge_source(self):
        src = build_user_knowledge_source()
        assert isinstance(src, TextFileKnowledgeSource)

    def test_file_paths_contains_user_preference(self):
        src = build_user_knowledge_source()
        assert _USER_PREFERENCE_FILE in src.file_paths

    def test_file_paths_length(self):
        src = build_user_knowledge_source()
        assert len(src.file_paths) == 1


class TestBuildProjectKnowledgeSource:
    """Tests for build_project_knowledge_source()."""

    def test_returns_text_file_knowledge_source(self):
        src = build_project_knowledge_source()
        assert isinstance(src, TextFileKnowledgeSource)

    def test_file_paths_contains_project_architecture(self):
        src = build_project_knowledge_source()
        assert _PROJECT_ARCHITECTURE_FILE in src.file_paths

    def test_file_paths_length(self):
        src = build_project_knowledge_source()
        assert len(src.file_paths) == 1


class TestBuildPrdGuidelinesKnowledgeSource:
    """Tests for build_prd_guidelines_knowledge_source()."""

    def test_returns_text_file_knowledge_source(self):
        src = build_prd_guidelines_knowledge_source()
        assert isinstance(src, TextFileKnowledgeSource)

    def test_file_paths_contains_prd_guidelines(self):
        src = build_prd_guidelines_knowledge_source()
        assert _PRD_GUIDELINES_FILE in src.file_paths

    def test_file_paths_length(self):
        src = build_prd_guidelines_knowledge_source()
        assert len(src.file_paths) == 1


# ── Composite knowledge-source factory ────────────────────────


class TestBuildPrdKnowledgeSources:
    """Tests for build_prd_knowledge_sources()."""

    def test_returns_list(self):
        sources = build_prd_knowledge_sources()
        assert isinstance(sources, list)

    def test_returns_three_sources(self):
        sources = build_prd_knowledge_sources()
        assert len(sources) == 3

    def test_all_are_text_file_knowledge_source(self):
        sources = build_prd_knowledge_sources()
        for src in sources:
            assert isinstance(src, TextFileKnowledgeSource)

    def test_covers_all_prd_knowledge_files(self):
        """All three knowledge files should be represented."""
        sources = build_prd_knowledge_sources()
        all_paths = []
        for src in sources:
            all_paths.extend(src.file_paths)
        for expected_file in _PRD_KNOWLEDGE_FILES:
            assert expected_file in all_paths

    def test_returns_same_list_when_cached(self):
        """Cached calls return the same list object."""
        clear_knowledge_cache()
        a = build_prd_knowledge_sources()
        b = build_prd_knowledge_sources()
        assert a is b
        clear_knowledge_cache()

    def test_returns_fresh_list_after_cache_clear(self):
        """After clear_knowledge_cache, a new list is built."""
        clear_knowledge_cache()
        a = build_prd_knowledge_sources()
        clear_knowledge_cache()
        b = build_prd_knowledge_sources()
        assert a is not b
        clear_knowledge_cache()

    def test_order_user_project_guidelines(self):
        """Sources should be ordered: user, project, guidelines."""
        sources = build_prd_knowledge_sources()
        assert _USER_PREFERENCE_FILE in sources[0].file_paths
        assert _PROJECT_ARCHITECTURE_FILE in sources[1].file_paths
        assert _PRD_GUIDELINES_FILE in sources[2].file_paths



