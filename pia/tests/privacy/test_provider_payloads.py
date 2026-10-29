"""Privacy findings B1, B2/B4 and B3: what an external model provider is sent.

Use case (Option B): the lab runs a local model by default but the admin has also connected an
external, OpenAI-compatible provider. The harness plays that provider with a scripted server that
records every request it receives (`upstream`). The tests only read those recorded requests.
No test depends on what a model answers.

B1     A question about an attached document sends the retrieved passages (with the names, e-mail
       addresses and phone numbers in them) to the provider.
B2/B4  When embeddings are computed by the external provider, every chunk of every uploaded document
       is sent at upload time, and no per-document rule exists to keep a sensitive file local.
B3     Title, tag and follow-up generation are extra requests that carry the whole chat to the
       provider, unless the admin has set a local task model.

GDPR: Art. 5(1)(b)(c) (purpose and minimisation), 25 (data protection by design), 28 (processor),
Ch. V (transfers). All data is synthetic.

Pass condition (the mitigation under test): none of the personal identifiers of the data subject
reaches the provider. A pseudonymisation gateway or a rule that keeps the call local both satisfy it.
They FAIL on Open WebUI v0.12.2.
"""

from __future__ import annotations

import time

import pytest

from harness.chat import ask

from .pia_support import IDENTIFIERS, TRANSCRIPT, leaked, upload

pytestmark = [pytest.mark.regression, pytest.mark.api, pytest.mark.requires_source]

TASKS_ON = {
    "ENABLE_TITLE_GENERATION": True,
    "ENABLE_FOLLOW_UP_GENERATION": True,
    "ENABLE_TAGS_GENERATION": True,
}


def _attached(file_id: str, name: str) -> dict:
    return {"type": "file", "id": file_id, "url": f"/api/v1/files/{file_id}", "name": name}


def _bodies(upstream, suffix: str) -> list[dict | None]:
    return [entry.body for entry in upstream.requests_to(suffix)]


def _no_leak(counts: dict[str, int], where: str) -> None:
    assert not any(counts.values()), f"identifiers reached the provider ({where}): {counts}"


# ------------------------------------------------------------------------------------- B1


def test_b1_retrieved_passages_do_not_carry_identifiers_to_the_provider(instance, make_user, upstream):
    member = make_user()
    with member.client() as client:
        file_id = upload(client, "interview_07.txt", TRANSCRIPT)
        upstream.reset()  # forget the embedding requests of the upload; B1 is about the chat
        _, message = ask(
            client,
            "What does the participant say about the co-author?",
            chat_files=[_attached(file_id, "interview_07.txt")],
        )

    assert message.get("sources"), "precondition failed: the document was not retrieved for the turn"
    _no_leak(leaked(upstream.chat_requests()), "chat completions")


# ------------------------------------------------------------------------------------- B2 / B4


def test_b2_b4_uploaded_chunks_do_not_carry_identifiers_to_the_embedding_provider(
    instance, make_user, upstream
):
    with make_user().client() as client:
        upload(client, "interview_07.txt", TRANSCRIPT)

    embedding_requests = upstream.requests_to("/embeddings")
    assert embedding_requests, "precondition failed: no embedding request reached the provider"
    _no_leak(leaked(_bodies(upstream, "/embeddings")), "embeddings at upload")


# ------------------------------------------------------------------------------------- B3


@pytest.fixture
def tasks_on(admin, preserve):
    preserve("tasks")
    with admin.client() as client:
        current = client.get("/api/v1/tasks/config").json()
        client.post("/api/v1/tasks/config/update", json={**current, **TASKS_ON}).raise_for_status()


def test_b3_background_tasks_do_not_carry_the_chat_to_the_provider(instance, make_user, upstream, tasks_on):
    question = f"Please summarise what {IDENTIFIERS[0]} told us, her address is {IDENTIFIERS[1]}."
    with make_user().client() as client:
        ask(
            client,
            question,
            background_tasks={"title_generation": True, "tags_generation": True, "follow_up_generation": True},
        )
        # the tasks run after the reply is stored; give them time to reach the provider
        deadline = time.monotonic() + 15
        tasks = []
        while time.monotonic() < deadline and len(tasks) < 3:
            tasks = [body for body in upstream.chat_requests() if not body.get("stream")]
            time.sleep(0.3)

    assert tasks, "precondition failed: no background task request reached the provider"
    _no_leak(leaked(tasks), f"{len(tasks)} background task request(s)")
