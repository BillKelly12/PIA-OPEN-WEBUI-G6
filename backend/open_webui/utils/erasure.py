"""Complete erasure of deleted data (Group 6 PIA, findings D1-D4).

GDPR Art. 17 (erasure) and Art. 5(1)(e) (storage limitation). When a user deletes a file or a
chat, or an admin deletes an account, Open WebUI v0.12.2 removed the main database rows but left
copies elsewhere. The helpers below remove those copies:

D1  a deleted file's text chunks in the vector store          -> drop_collection()
D2  a deleted user's files, memories, notes, folders, ratings -> erase_user_data()
D3  deleted text in SQLite's write-ahead file                  -> scrub_deleted_text()
    (free pages inside the database file are zeroed by PRAGMA secure_delete, see internal/db.py)
D4  the chat copy saved with every answer rating               -> strip_rating_copies()

Each helper logs and continues on failure, so a cleanup problem never blocks the deletion the
user asked for.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import ASYNC_SQLALCHEMY_DATABASE_URL, async_engine, get_async_db_context
from open_webui.models.feedbacks import Feedback
from open_webui.models.files import FileModel, Files
from open_webui.models.folders import Folder
from open_webui.models.knowledge import Knowledges
from open_webui.models.memories import Memories
from open_webui.models.notes import Note
from open_webui.retrieval.vector.async_client import ASYNC_VECTOR_DB_CLIENT
from open_webui.storage.provider import Storage

log = logging.getLogger(__name__)


async def drop_collection(collection_name: str) -> None:
    """Remove a whole vector collection (D1).

    The original code called `ASYNC_VECTOR_DB_CLIENT.delete(collection_name=...)` with no ids
    and no filter, which the Chroma client treats as "delete nothing".
    """
    try:
        if await ASYNC_VECTOR_DB_CLIENT.has_collection(collection_name):
            await ASYNC_VECTOR_DB_CLIENT.delete_collection(collection_name)
    except Exception as e:
        log.warning('erasure: could not drop vector collection %s: %s', collection_name, e)


async def _erase_file(file: FileModel, db: AsyncSession) -> None:
    """Remove one file everywhere: knowledge-base embeddings, row, stored copy, chunks."""
    for knowledge in await Knowledges.get_knowledges_by_file_id(file.id, db=db):
        await Knowledges.remove_file_from_knowledge_by_id(knowledge.id, file.id, db=db)
        try:
            await ASYNC_VECTOR_DB_CLIENT.delete(collection_name=knowledge.id, filter={'file_id': file.id})
        except Exception as e:
            log.warning('erasure: knowledge-base cleanup for %s: %s', knowledge.id, e)
    await Files.delete_file_by_id(file.id, db=db)
    if file.path:
        try:
            await asyncio.to_thread(Storage.delete_file, file.path)
        except Exception as e:
            log.warning('erasure: could not delete stored copy of %s: %s', file.id, e)
    await drop_collection(f'file-{file.id}')


async def erase_user_data(user_id: str, db: Optional[AsyncSession] = None) -> None:
    """Remove what a deleted account leaves behind (D2).

    `Users.delete_user_by_id` removes the account, group memberships and chats. This removes the
    rest: uploaded files (row, stored copy, extracted text, chunks), memories and their vectors,
    notes, folders and answer ratings. Knowledge bases are left alone on purpose, because other
    users may have been granted access to them; the report lists this as a limitation.
    """
    async with get_async_db_context(db) as session:
        for file in await Files.get_files_by_user_id(user_id, db=session):
            await _erase_file(file, session)

        await Memories.delete_memories_by_user_id(user_id, db=session)
        await drop_collection(f'user-memory-{user_id}')

        await session.execute(delete(Note).where(Note.user_id == user_id))
        await session.execute(delete(Folder).where(Folder.user_id == user_id))
        await session.execute(delete(Feedback).where(Feedback.user_id == user_id))
        await session.commit()


async def strip_rating_copies(user_id: str, chat_ids: Optional[set[str]], db: Optional[AsyncSession] = None) -> int:
    """Drop the chat copies stored with a user's answer ratings (D4).

    `chat_ids=None` means every chat of the user (used when all chats are deleted). The rating
    itself (thumbs up or down, model id) is kept, so the model leaderboard still works; only the
    copy of the conversation and the link to the deleted chat are removed.
    """
    async with get_async_db_context(db) as session:
        rows = (await session.execute(select(Feedback).where(Feedback.user_id == user_id))).scalars().all()
        stripped = 0
        for feedback in rows:
            chat_id = (feedback.meta or {}).get('chat_id')
            if chat_id is None or (chat_ids is not None and chat_id not in chat_ids):
                continue
            feedback.snapshot = None
            feedback.meta = {k: v for k, v in (feedback.meta or {}).items() if k not in ('chat_id', 'message_id')}
            stripped += 1
        if stripped:
            await session.commit()
        return stripped


async def scrub_deleted_text() -> None:
    """Make deleted rows unreadable in SQLite's write-ahead file (D3).

    With WAL on (the default), the old page versions that still hold the deleted text stay in
    `webui.db-wal` until a checkpoint. A TRUNCATE checkpoint copies the current (zeroed, thanks
    to `secure_delete`) pages into the database file and empties the log. No-op on PostgreSQL.
    """
    if 'sqlite' not in ASYNC_SQLALCHEMY_DATABASE_URL:
        return
    try:
        async with async_engine.connect() as conn:
            await conn.exec_driver_sql('PRAGMA wal_checkpoint(TRUNCATE)')
    except Exception as e:
        log.warning('erasure: write-ahead checkpoint failed: %s', e)
