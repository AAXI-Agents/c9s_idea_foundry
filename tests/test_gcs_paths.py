"""Tests for services/gcs_paths — unified GCS bucket + path resolution."""

import os
from unittest.mock import patch

from crewai_productfeature_planner.services.gcs_paths import (
    build_idea_key,
    build_idea_prefix,
    build_knowledge_key,
    get_bucket_name,
)


class TestGetBucketName:
    def test_defaults_to_dev(self):
        with patch.dict(os.environ, {}, clear=True):
            # No SERVER_ENV → defaults to DEV
            assert get_bucket_name() == "dev-idea-foundry"

    def test_dev_env(self):
        with patch.dict(os.environ, {"SERVER_ENV": "DEV"}):
            assert get_bucket_name() == "dev-idea-foundry"

    def test_uat_env(self):
        with patch.dict(os.environ, {"SERVER_ENV": "UAT"}):
            assert get_bucket_name() == "uat-idea-foundry"

    def test_prod_env(self):
        with patch.dict(os.environ, {"SERVER_ENV": "PROD"}):
            assert get_bucket_name() == "prod-idea-foundry"

    def test_lowercases_env(self):
        with patch.dict(os.environ, {"SERVER_ENV": "Prod"}):
            assert get_bucket_name() == "prod-idea-foundry"

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"SERVER_ENV": " UAT "}):
            assert get_bucket_name() == "uat-idea-foundry"


class TestBuildKnowledgeKey:
    def test_standard_key(self):
        key = build_knowledge_key(
            enterprise_id="ent1",
            organization_id="org2",
            project_id="proj3",
            doc_id="doc4",
            filename="report.pdf",
        )
        assert key == "ent1/org2/projects/proj3/knowledge/doc4/report.pdf"


class TestBuildIdeaKey:
    def test_standard_key(self):
        key = build_idea_key(
            enterprise_id="ent1",
            organization_id="org2",
            project_id="proj3",
            idea_id="idea5",
            filename="prd_v1.md",
        )
        assert key == "ent1/org2/projects/proj3/ideas/idea5/prd_v1.md"

    def test_ux_design_filename(self):
        key = build_idea_key(
            enterprise_id="e",
            organization_id="o",
            project_id="p",
            idea_id="i",
            filename="ux_design_draft.md",
        )
        assert key == "e/o/projects/p/ideas/i/ux_design_draft.md"


class TestBuildIdeaPrefix:
    def test_trailing_slash(self):
        prefix = build_idea_prefix(
            enterprise_id="ent1",
            organization_id="org2",
            project_id="proj3",
            idea_id="idea5",
        )
        assert prefix == "ent1/org2/projects/proj3/ideas/idea5/"
        assert prefix.endswith("/")

    def test_concat_with_filename(self):
        prefix = build_idea_prefix("e", "o", "p", "i")
        full_key = f"{prefix}prd_v2.md"
        assert full_key == "e/o/projects/p/ideas/i/prd_v2.md"
