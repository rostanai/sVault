"""M2 document-vault tests — storage helpers + endpoint auth guards."""
import httpx
import pytest

from app.core import storage
from app.main import app


def test_sanitize_filename_strips_paths_and_unsafe_chars():
    assert storage.sanitize_filename("../../etc/passwd") == "passwd"
    assert storage.sanitize_filename("my policy (2026).pdf") == "my_policy_2026_.pdf"
    assert storage.sanitize_filename("") == "file"


def test_build_object_path_is_tenant_scoped():
    path = storage.build_object_path("tid", "pid", "doc.pdf")
    assert path.startswith("tid/pid/")
    assert path.endswith("_doc.pdf")


def test_allowed_mime_and_size():
    assert "application/pdf" in storage.ALLOWED_MIME
    assert "application/x-msdownload" not in storage.ALLOWED_MIME
    assert storage.MAX_SIZE_BYTES == 20 * 1024 * 1024


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("post", "/api/v1/policies/00000000-0000-0000-0000-000000000000/documents/upload-url"),
    ("post", "/api/v1/policies/00000000-0000-0000-0000-000000000000/documents"),
    ("get", "/api/v1/policies/00000000-0000-0000-0000-000000000000/documents"),
    ("delete", "/api/v1/documents/00000000-0000-0000-0000-000000000000"),
])
async def test_document_endpoints_require_auth(method, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(ac, method)(path, **kwargs)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
