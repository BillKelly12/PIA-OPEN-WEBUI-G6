"""Privacy finding B7: a shared chat reveals passages the colleague has no right to read.

Alice keeps interview transcripts in a private knowledge base, attaches it to a chat, asks a
question and shares the chat with Bob. Bob has no access to the knowledge base or its files (the
API refuses them). But the shared copy of the chat carries the retrieved passages, so Bob reads the
interviewee's name and contact details anyway. The interviewee never agreed to this reader
(GDPR Art. 5(1)(f) integrity and confidentiality, Art. 25 data protection by design).

Scope note (checked in the code, `utils/access_control/files.py`): when a file is stored on a chat
message, a reader of the shared chat is allowed to open that file too, by design. The leak therefore
concerns material that reaches the chat through retrieval and is *not* stored on the message, such
as a knowledge base. That is the case tested here.

Pass condition (the mitigation under test): the shared view leaves out passages the reader may not
read. FAILS on Open WebUI v0.12.2. No model output is involved.
"""

from __future__ import annotations

import json

import pytest

from harness.chat import ask
from harness.knowledge_bases import add_text_file, knowledge_base

from .pia_support import INTERVIEWEE_EMAIL, TRANSCRIPT

pytestmark = [pytest.mark.regression, pytest.mark.api, pytest.mark.requires_source]


@pytest.fixture
def members_may_create_knowledge(admin, preserve):
    preserve("permissions")
    with admin.client() as client:
        current = client.get("/api/v1/users/default/permissions").json()
        current["workspace"]["knowledge"] = True
        client.post("/api/v1/users/default/permissions", json=current).raise_for_status()


def test_b7_a_shared_chat_does_not_show_passages_of_a_knowledge_base_the_reader_cannot_open(
    members_may_create_knowledge, make_user, upstream
):
    alice, bob = make_user(), make_user()
    with alice.client() as client, knowledge_base(client, "Interviews") as kb_id:
        file_id = add_text_file(client, kb_id, "interview_07.txt", TRANSCRIPT)
        turn, message = ask(
            client,
            "What does the participant say about the co-author?",
            files=[{"type": "collection", "id": kb_id, "name": "Interviews"}],
        )
        assert message.get("sources"), "precondition failed: the knowledge base was not retrieved"
        shared = client.post(f"/api/v1/chats/{turn.chat_id}/share", json={})
        assert shared.status_code == 200, shared.text
        share_id = shared.json()["share_id"]
        granted = client.post(
            f"/api/v1/chats/shared/{turn.chat_id}/access/update",
            json={"access_grants": [{"principal_type": "user", "principal_id": bob.id, "permission": "read"}]},
        )
        assert granted.status_code == 200, granted.text

        with bob.client() as bobs:
            file_access = bobs.get(f"/api/v1/files/{file_id}/data/content")
            kb_access = bobs.get(f"/api/v1/knowledge/{kb_id}")
            assert file_access.status_code in (401, 403, 404) and kb_access.status_code in (401, 403, 404), (
                "precondition failed: Bob can open the knowledge base or its file himself "
                f"(file HTTP {file_access.status_code}, knowledge base HTTP {kb_access.status_code})"
            )
            view = bobs.get(f"/api/v1/chats/share/{share_id}")
            assert view.status_code == 200, f"precondition failed: Bob cannot open the share: {view.text}"

    assert INTERVIEWEE_EMAIL not in json.dumps(view.json()), (
        "Bob, who cannot open the knowledge base, can read its contact details in the shared chat"
    )
