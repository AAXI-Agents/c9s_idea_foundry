"""Knowledge module REST API.

Endpoints for managing project knowledge documents:
- Upload files (multipart)
- Ingest URLs
- List/detail/toggle/delete documents
- Trigger Content Reviewer
- Get/regenerate aggregated summary
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from crewai_productfeature_planner.apis.admin_deps import resolve_tenant_context
from crewai_productfeature_planner.apis.sso_auth import require_sso_user
from crewai_productfeature_planner.mongodb._tenant import TenantContext, tenant_filter
from crewai_productfeature_planner.mongodb.knowledge_documents import (
    count_knowledge_documents,
    create_knowledge_document,
    delete_knowledge_document,
    find_duplicate_document,
    find_duplicate_url,
    get_knowledge_document,
    list_knowledge_documents,
    toggle_included,
    update_knowledge_document,
)
from crewai_productfeature_planner.mongodb.knowledge_documents.repository import (
    BLOCKED_MEDIA_PREFIXES,
    MAX_FILE_SIZE_BYTES,
    MAX_URL_FETCH_BYTES,
)
from crewai_productfeature_planner.mongodb.knowledge_summaries import (
    get_knowledge_summary,
)
from crewai_productfeature_planner.scripts.logging_config import get_logger
from crewai_productfeature_planner.services import knowledge_storage
from crewai_productfeature_planner.services.content_extractor import extract_text
from crewai_productfeature_planner.services.knowledge_aggregator import (
    aggregate_knowledge,
    aggregate_knowledge_async,
    review_document_async,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/projects/{project_id}/knowledge",
    tags=["Knowledge"],
    dependencies=[Depends(require_sso_user)],
)


# ── Response Models ──────────────────────────────────────────────

class KnowledgeDocResponse(BaseModel):
    doc_id: str
    project_id: str
    source_type: str
    filename: str | None = None
    url: str | None = None
    file_size: int | None = None
    content_type: str | None = None
    status: str
    included: bool
    review: dict | None = None
    created_by: str
    created_at: str
    updated_at: str


class KnowledgeDocCreated(BaseModel):
    doc_id: str
    status: str


class KnowledgeSummaryResponse(BaseModel):
    project_id: str
    unified_summary: str = ""
    unified_bullets: list[str] = Field(default_factory=list)
    contradictions: list[dict] = Field(default_factory=list)
    doc_count: int = 0
    generated_at: str | None = None


class UrlIngestRequest(BaseModel):
    url: str = Field(..., description="HTTP(S) URL to fetch and ingest")


class ToggleIncludedRequest(BaseModel):
    included: bool = Field(..., description="Whether to include in aggregation")


# ── Endpoints ────────────────────────────────────────────────────


@router.post(
    "/upload",
    summary="Upload a knowledge document",
    description="Multipart file upload. Max 25 MB. Triggers Content Reviewer asynchronously.",
    response_model=KnowledgeDocCreated,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Document created, review in progress."},
        413: {"description": "File too large."},
    },
)
async def upload_knowledge_document(
    project_id: str,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    user_id = user.get("user_id", "")

    # Size check
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )

    filename = file.filename or "untitled"
    content_type = file.content_type or "application/octet-stream"

    # Duplicate check: same project + filename + file_size
    existing = find_duplicate_document(
        project_id=project_id,
        filename=filename,
        file_size=len(contents),
        tenant=tenant,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate file already exists.",
            headers={"X-Existing-Doc-Id": existing["doc_id"]},
        )

    # Create record
    doc = create_knowledge_document(
        project_id=project_id,
        source_type="upload",
        filename=filename,
        file_size=len(contents),
        content_type=content_type,
        created_by=user_id,
        tenant=tenant,
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to create document record.")

    doc_id = doc["doc_id"]

    # Upload to GCS
    import io

    gcs_path = knowledge_storage.build_object_key(
        tenant.enterprise_id, tenant.organization_id,
        project_id, doc_id, filename,
    )
    try:
        knowledge_storage.upload_file(
            enterprise_id=tenant.enterprise_id,
            organization_id=tenant.organization_id,
            project_id=project_id,
            doc_id=doc_id,
            filename=filename,
            file_obj=io.BytesIO(contents),
            content_type=content_type,
        )
        update_knowledge_document(
            doc_id=doc_id,
            project_id=project_id,
            updates={"gcs_path": gcs_path, "status": "uploaded"},
            tenant=tenant,
        )
    except Exception as exc:
        logger.error("[KnowledgeAPI] GCS upload failed: %s", exc, exc_info=True)
        update_knowledge_document(
            doc_id=doc_id,
            project_id=project_id,
            updates={"status": "upload_failed"},
            tenant=tenant,
        )
        raise HTTPException(status_code=500, detail="File upload failed.")

    # Trigger review asynchronously
    text_content = extract_text(
        contents, filename=filename, content_type=content_type
    )
    if not text_content or not text_content.strip():
        logger.warning(
            "[KnowledgeAPI] Cannot extract text from file=%s content_type=%s",
            filename,
            content_type,
        )
        update_knowledge_document(
            doc_id=doc_id,
            project_id=project_id,
            updates={"status": "review_failed"},
            tenant=tenant,
        )
    else:
        review_document_async(
            doc_id=doc_id,
            project_id=project_id,
            content=text_content,
            title=filename,
            source=filename,
            tenant=tenant,
        )

    logger.info("[KnowledgeAPI] Upload doc=%s project=%s user=%s", doc_id, project_id, user_id)
    return KnowledgeDocCreated(doc_id=doc_id, status="uploading")


@router.post(
    "/url",
    summary="Ingest a URL as knowledge",
    description="Fetch content from a URL. Blocks media types (video/audio/image). Max 10 MB body.",
    response_model=KnowledgeDocCreated,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "URL ingestion started."},
        415: {"description": "Unsupported media type."},
    },
)
async def ingest_url(
    project_id: str,
    body: UrlIngestRequest,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    user_id = user.get("user_id", "")
    url = body.url

    # Duplicate URL check
    existing = find_duplicate_url(
        project_id=project_id,
        url=url,
        tenant=tenant,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="URL already ingested.",
            headers={"X-Existing-Doc-Id": existing["doc_id"]},
        )

    # Create record first
    doc = create_knowledge_document(
        project_id=project_id,
        source_type="url",
        url=url,
        created_by=user_id,
        tenant=tenant,
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to create document record.")

    doc_id = doc["doc_id"]

    # Fetch URL content
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            # Check content type
            ct = resp.headers.get("content-type", "")
            if any(ct.startswith(prefix) for prefix in BLOCKED_MEDIA_PREFIXES):
                update_knowledge_document(
                    doc_id=doc_id,
                    project_id=project_id,
                    updates={"status": "rejected"},
                    tenant=tenant,
                )
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Media type '{ct}' is not supported for knowledge ingestion.",
                )

            content = resp.text
            if len(content.encode()) > MAX_URL_FETCH_BYTES:
                content = content[:MAX_URL_FETCH_BYTES]

            update_knowledge_document(
                doc_id=doc_id,
                project_id=project_id,
                updates={
                    "status": "fetched",
                    "content_type": ct,
                    "file_size": len(content.encode()),
                },
                tenant=tenant,
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[KnowledgeAPI] URL fetch failed: %s", exc, exc_info=True)
        update_knowledge_document(
            doc_id=doc_id,
            project_id=project_id,
            updates={"status": "fetch_failed"},
            tenant=tenant,
        )
        raise HTTPException(status_code=502, detail="Failed to fetch URL content.")

    # Trigger review
    review_document_async(
        doc_id=doc_id,
        project_id=project_id,
        content=content,
        title=url.split("/")[-1] or url,
        source=url,
        tenant=tenant,
    )

    logger.info("[KnowledgeAPI] URL ingested doc=%s project=%s url=%s", doc_id, project_id, url)
    return KnowledgeDocCreated(doc_id=doc_id, status="fetching")


@router.get(
    "",
    summary="List knowledge documents",
    description="List all knowledge documents for a project.",
    response_model=list[KnowledgeDocResponse],
)
async def list_documents(
    project_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    docs = list_knowledge_documents(project_id=project_id, tenant=tenant)
    return docs


@router.get(
    "/summary",
    summary="Get aggregated knowledge summary",
    description="Returns the unified summary, bullets, and contradictions across all included docs.",
    response_model=KnowledgeSummaryResponse,
)
async def get_summary(
    project_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    summary = get_knowledge_summary(project_id=project_id, tenant=tenant)
    doc_count = count_knowledge_documents(project_id=project_id, tenant=tenant)
    if not summary:
        return KnowledgeSummaryResponse(project_id=project_id, doc_count=doc_count)
    # Always reflect live doc_count
    summary["doc_count"] = doc_count
    return summary


@router.post(
    "/summary/regenerate",
    summary="Regenerate aggregated summary",
    description="Re-run the aggregation across all included, reviewed documents.",
    response_model=KnowledgeSummaryResponse,
)
async def regenerate_summary(
    project_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    aggregate_knowledge(project_id=project_id, tenant=tenant)
    summary = get_knowledge_summary(project_id=project_id, tenant=tenant)
    doc_count = count_knowledge_documents(project_id=project_id, tenant=tenant)
    if not summary:
        return KnowledgeSummaryResponse(project_id=project_id, doc_count=doc_count)
    summary["doc_count"] = doc_count
    return summary


@router.get(
    "/{doc_id}",
    summary="Get knowledge document detail",
    description="Get a single knowledge document with its reviewer summary.",
    response_model=KnowledgeDocResponse,
    responses={404: {"description": "Document not found."}},
)
async def get_document(
    project_id: str,
    doc_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    doc = get_knowledge_document(doc_id=doc_id, project_id=project_id, tenant=tenant)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.patch(
    "/{doc_id}",
    summary="Toggle document inclusion",
    description="Toggle whether a document is included in the aggregated summary.",
    responses={404: {"description": "Document not found."}},
)
async def patch_document(
    project_id: str,
    doc_id: str,
    body: ToggleIncludedRequest,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)
    success = toggle_included(
        doc_id=doc_id, project_id=project_id, included=body.included, tenant=tenant
    )
    if not success:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"doc_id": doc_id, "included": body.included}


@router.delete(
    "/{doc_id}",
    summary="Delete a knowledge document",
    description="Remove document record and GCS object.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Document not found."}},
)
async def delete_document(
    project_id: str,
    doc_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)

    # Get doc to find GCS path
    doc = get_knowledge_document(doc_id=doc_id, project_id=project_id, tenant=tenant)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete GCS object if exists
    gcs_path = doc.get("gcs_path")
    if gcs_path:
        knowledge_storage.delete_file(gcs_path=gcs_path)

    # Delete record
    delete_knowledge_document(doc_id=doc_id, project_id=project_id, tenant=tenant)
    logger.info("[KnowledgeAPI] Deleted doc=%s project=%s", doc_id, project_id)


@router.post(
    "/{doc_id}/review",
    summary="Re-trigger Content Reviewer",
    description="Re-run the Content Reviewer agent on this document.",
    response_model=KnowledgeDocCreated,
    responses={
        404: {"description": "Document not found."},
        409: {"description": "Document status does not allow review."},
    },
)
async def retrigger_review(
    project_id: str,
    doc_id: str,
    user: dict[str, Any] = Depends(require_sso_user),
    organization_id: str | None = Query(default=None),
):
    tenant = resolve_tenant_context(user, organization_id)

    doc = get_knowledge_document(doc_id=doc_id, project_id=project_id, tenant=tenant)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Status guard: only allow review for docs that have content available
    REVIEWABLE_STATUSES = {"reviewed", "review_failed"}
    doc_status = doc.get("status", "")
    if doc_status not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Document status '{doc_status}' does not allow review. "
            f"Allowed: {', '.join(sorted(REVIEWABLE_STATUSES))}.",
        )

    # Get content from GCS or use URL
    content = ""
    if doc.get("gcs_path"):
        raw_bytes = knowledge_storage.download_as_bytes(gcs_path=doc["gcs_path"])
        if raw_bytes:
            filename = doc.get("filename") or ""
            ct = doc.get("content_type") or "application/octet-stream"
            content = extract_text(raw_bytes, filename=filename, content_type=ct) or ""
    elif doc.get("url"):
        # Re-fetch URL
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.get(doc["url"])
                content = resp.text[:MAX_URL_FETCH_BYTES]
        except Exception:
            raise HTTPException(status_code=502, detail="Failed to re-fetch URL.")

    if not content:
        raise HTTPException(status_code=422, detail="No content available for review.")

    title = doc.get("filename") or doc.get("url") or doc_id
    source = doc.get("filename") or doc.get("url") or "unknown"

    review_document_async(
        doc_id=doc_id,
        project_id=project_id,
        content=content,
        title=title,
        source=source,
        tenant=tenant,
    )

    return KnowledgeDocCreated(doc_id=doc_id, status="reviewing")
