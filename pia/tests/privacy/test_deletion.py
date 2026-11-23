"""Privacy finding I5 and I6: deleting a file or a user must really delete their text.

GDPR Art. 17 (erasure) and Art. 5(1)(e) (storage limitation). Data subjects are the people in the
documents (interviewees, students, co-authors), not only the uploader.

I5  A user deletes a file. The file row and the stored copy go, but the text chunks stay in the
    vector store (cause seen in code: routers/files.py asks the vector client to delete the
    collection without ids or a filter, and the Chroma client then does nothing).
I6  The admin deletes a user. The account goes, but the user's files, their stored copies and the
    vector collections (file chunks and memories) stay.

Both tests FAIL on Open WebUI v0.12.2 and must PASS once the deletion is complete.
They look at the HTTP API and at the data folder, never at a model's answer.
"""

from __future__ import annotations

import pytest

from .pia_support import (
    INTERVIEWEE_EMAIL,
    TRANSCRIPT,
    stored_chunks,
    stored_copies,
    stored_vectors,
    upload,
)

pytestmark = [pytest.mark.regression, pytest.mark.api, pytest.mark.requires_source, pytest.mark.slow]


# ------------------------------------------------------------------------------------- I5


def test_i5_deleting_a_file_leaves_no_text_in_the_vector_store(instance, make_user):
    owner = make_user()
    with owner.client() as client:
        file_id = upload(client, "interview_07.txt", TRANSCRIPT)
        collection = f"file-{file_id}"
        before = stored_chunks(instance, collection)
        assert any(INTERVIEWEE_EMAIL in chunk for chunk in before), (
            "precondition failed: the uploaded text is not in the vector store at all"
        )
        assert stored_vectors(instance, collection) > 0, "precondition failed: no embedding vectors were stored"

        deleted = client.delete(f"/api/v1/files/{file_id}")
        assert deleted.status_code == 200, deleted.text

    left = stored_chunks(instance, collection)
    assert not left, f"{len(left)} chunk(s) of the deleted file are still stored, e.g. {left[0][:70]!r}"
    vectors = stored_vectors(instance, collection)
    assert vectors == 0, f"{vectors} embedding vector(s) of the deleted file are still stored"


# ------------------------------------------------------------------------------------- I6


@pytest.fixture
def erased_account(instance, admin, make_user):
    """An account with a file and a memory, deleted by the admin. Returns what it had."""
    person = make_user()
    with person.client() as client:
        file_id = upload(client, "survey_answers.txt", TRANSCRIPT)
        added = client.post(
            "/api/v1/memories/add",
            json={"content": f"My contact is {INTERVIEWEE_EMAIL}", "type": "user"},
        )
        assert added.status_code == 200, f"precondition failed: memory not stored: {added.text}"
    memory_collection = f"user-memory-{person.id}"
    file_collection = f"file-{file_id}"
    assert stored_chunks(instance, file_collection), "precondition failed: no file chunks"
    assert stored_vectors(instance, file_collection) > 0, "precondition failed: no file embedding vectors"
    assert stored_chunks(instance, memory_collection), "precondition failed: no memory vectors"
    assert stored_vectors(instance, memory_collection) > 0, "precondition failed: no memory embedding vectors"

    with admin.client() as client:
        gone = client.delete(f"/api/v1/users/{person.id}")
        assert gone.status_code == 200, gone.text
    return {"file_id": file_id, "file_collection": file_collection, "memory_collection": memory_collection}


def test_i6_deleting_a_user_removes_their_file_chunks(instance, erased_account):
    left = stored_chunks(instance, erased_account["file_collection"])
    assert not left, f"{len(left)} chunk(s) of the deleted user's file are still stored"
    vectors = stored_vectors(instance, erased_account["file_collection"])
    assert vectors == 0, f"{vectors} embedding vector(s) of the deleted user's file are still stored"


def test_i6_deleting_a_user_removes_their_memory_vectors(instance, erased_account):
    left = stored_chunks(instance, erased_account["memory_collection"])
    assert not left, f"{len(left)} memory text(s) of the deleted user are still stored"
    vectors = stored_vectors(instance, erased_account["memory_collection"])
    assert vectors == 0, f"{vectors} memory embedding vector(s) of the deleted user are still stored"


def test_i6_deleting_a_user_removes_their_uploaded_files(instance, admin, erased_account):
    with admin.client() as client:
        still_readable = client.get(f"/api/v1/files/{erased_account['file_id']}")
    on_disk = stored_copies(instance, erased_account["file_id"])
    assert still_readable.status_code == 404 and not on_disk, (
        f"file record answers HTTP {still_readable.status_code}; stored copies on disk: {on_disk}"
    )
