"""Helpers shared by the privacy tests of Group 6 (KU Leuven, Privacy and Big Data).

Everything here looks at the *outside* of Open WebUI: its HTTP API, the folder it stores data
in, and the requests it sends to the model provider. No test depends on what a model answers.
All personal data below is synthetic.
"""

from __future__ import annotations

import json

import httpx

# Synthetic data subject: an interviewee in a (fictional) research interview.
INTERVIEWEE_NAME = "Marta Vandenbroeck"
INTERVIEWEE_EMAIL = "marta.vandenbroeck@example.org"
INTERVIEWEE_PHONE = "+32 470 12 34 56"
IDENTIFIERS = (INTERVIEWEE_NAME, INTERVIEWEE_EMAIL, INTERVIEWEE_PHONE)

TRANSCRIPT = (
    f"Interview 07. Participant: {INTERVIEWEE_NAME}, PhD student, reachable at "
    f"{INTERVIEWEE_EMAIL} or {INTERVIEWEE_PHONE}.\n\n"
    "She said her supervisor pressured her to add a co-author who did not contribute, and that "
    "she is afraid to report it before her thesis defence.\n"
)


def upload(client: httpx.Client, filename: str, text: str) -> str:
    """Upload a text file, processed (cut into chunks and embedded) before the call returns."""
    uploaded = client.post(
        "/api/v1/files/",
        params={"process": "true", "process_in_background": "false"},
        files={"file": (filename, text.encode(), "text/plain")},
    )
    assert uploaded.status_code == 200, f"upload failed: {uploaded.text}"
    return uploaded.json()["id"]


def stored_chunks(instance, collection: str) -> list[str]:
    """Texts held by one collection of the vector store (Chroma, read from the data folder).

    Returns [] when the collection does not exist. Reading the store directly is deliberate:
    after a deletion the API refuses to show a collection whose file is gone, so only the
    storage itself can tell whether the text is still there.
    """
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(instance.data_dir / "vector_db"),
        settings=Settings(anonymized_telemetry=False, allow_reset=False),
    )
    try:
        found = client.get_collection(collection)
    except Exception:  # chromadb raises different errors by version when it is missing
        return []
    return found.get(include=["documents"])["documents"] or []


def stored_copies(instance, file_id: str) -> list[str]:
    """Files in the uploads folder that are the stored copy of this file (named `<id>_<name>`)."""
    folder = instance.data_dir / "uploads"
    if not folder.exists():
        return []
    return [str(p.relative_to(folder)) for p in folder.rglob(f"{file_id}_*") if p.is_file()]


def leaked(requests_bodies: list[dict | None]) -> dict[str, int]:
    """For each synthetic identifier, in how many recorded provider requests it appears."""
    counts = {identifier: 0 for identifier in IDENTIFIERS}
    for body in requests_bodies:
        text = json.dumps(body, ensure_ascii=False)
        for identifier in IDENTIFIERS:
            if identifier in text:
                counts[identifier] += 1
    return counts
