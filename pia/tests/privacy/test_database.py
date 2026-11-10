"""Privacy finding D3 and D4: a deleted chat must not survive in the database.

GDPR Art. 17 (erasure), Art. 5(1)(e) (storage limitation) and Art. 5(1)(f) (confidentiality).
This is issue I4 of the report. The data subjects are the people a chat talks about
(interviewees, co-authors), not only the student who deletes it.

D3  A user deletes a chat. The application rows go, but SQLite keeps the deleted text in the
    database's free pages and in its write-ahead file (`webui.db-wal`), where anyone who copies
    the data folder or a backup can read it without passing the application's access checks.
D4  A user rates an answer, then deletes the chat. The browser sends a full copy of the chat with
    every rating (`ResponseMessage.svelte`, `snapshot: {chat}`), and deleting the chat leaves
    that copy in the `feedback` table, where the admin's export still returns it.

Both tests FAIL on Open WebUI v0.12.2 and must PASS once deletion is complete.
They look at the HTTP API and at the files in the data folder, never at a model's answer.
"""

from __future__ import annotations

import uuid

import pytest

from harness.chat_history import seed_chat

from .pia_support import INTERVIEWEE_NAME

pytestmark = [pytest.mark.regression, pytest.mark.api, pytest.mark.requires_source, pytest.mark.slow]


def _marker() -> str:
    """A unique string standing in for the personal data in one chat."""
    return f"PIA-DELETED-CHAT-{uuid.uuid4().hex[:12]}"


def _database_files_holding(instance, text: str) -> list[str]:
    """Which SQLite files in the data folder contain `text`, read as raw bytes.

    Reading the bytes is deliberate: it is what a person with a copy of the data folder or a
    backup can do, and it sees text that SQL no longer returns (free pages, old log frames).
    """
    needle = text.encode()
    holding = []
    for suffix in ("", "-wal"):
        path = instance.data_dir / f"webui.db{suffix}"
        if path.exists() and needle in path.read_bytes():
            holding.append(path.name)
    return holding


def _chat_about(client, marker: str) -> tuple[str, str, dict]:
    """Store a two-turn chat that talks about the interviewee. Returns (chat id, answer id, chat)."""
    question = f"Summarise interview 07 with {INTERVIEWEE_NAME}. Reference {marker}."
    answer = f"{INTERVIEWEE_NAME} reports pressure from her supervisor ({marker})."
    chat_id, answer_id = seed_chat(
        client,
        [{"role": "user", "content": question}, {"role": "assistant", "content": answer}],
    )
    stored = client.get(f"/api/v1/chats/{chat_id}")
    assert stored.status_code == 200, f"precondition failed: chat not stored: {stored.text}"
    return chat_id, answer_id, stored.json()["chat"]


# ------------------------------------------------------------------------------------- D3


def test_d3_deleting_a_chat_leaves_no_text_in_the_database_files(instance, make_user):
    marker = _marker()
    owner = make_user()
    with owner.client() as client:
        chat_id, _, _ = _chat_about(client, marker)
        assert _database_files_holding(instance, marker), (
            "precondition failed: the chat text is not in the database files at all"
        )

        deleted = client.delete(f"/api/v1/chats/{chat_id}")
        assert deleted.status_code == 200 and deleted.json() is True, deleted.text
        assert client.get(f"/api/v1/chats/{chat_id}").status_code in (401, 404), (
            "precondition failed: the API still returns the deleted chat"
        )

    left = _database_files_holding(instance, marker)
    assert not left, f"the deleted chat's text is still readable in: {left}"


# ------------------------------------------------------------------------------------- D4


def test_d4_deleting_a_rated_chat_removes_its_rating_copy(instance, admin, make_user):
    marker = _marker()
    owner = make_user()
    with owner.client() as client:
        chat_id, answer_id, chat = _chat_about(client, marker)
        # The same payload the browser sends on a thumbs-up (ResponseMessage.svelte).
        rated = client.post(
            "/api/v1/evaluations/feedback",
            json={
                "type": "rating",
                "data": {"rating": 1, "model_id": chat["models"][0]},
                "meta": {"chat_id": chat_id, "message_id": answer_id},
                "snapshot": {"chat": chat},
            },
        )
        assert rated.status_code == 200, f"precondition failed: rating not stored: {rated.text}"

    with admin.client() as client:
        before = client.get("/api/v1/evaluations/feedbacks/all/export")
        assert before.status_code == 200 and marker in before.text, (
            "precondition failed: the rating copy of the chat is not stored"
        )

    with owner.client() as client:
        deleted = client.delete(f"/api/v1/chats/{chat_id}")
        assert deleted.status_code == 200 and deleted.json() is True, deleted.text

    with admin.client() as client:
        after = client.get("/api/v1/evaluations/feedbacks/all/export")
    assert after.status_code == 200, after.text
    assert marker not in after.text, "the admin export still returns the deleted chat through its rating copy"
