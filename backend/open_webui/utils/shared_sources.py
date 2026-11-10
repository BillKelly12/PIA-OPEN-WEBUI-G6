"""Withhold retrieved passages a shared-chat reader may not open (Group 6 PIA, finding B7).

When a chat used a knowledge base, every assistant message stores the retrieved passages in
`sources`. Sharing the chat showed those passages to every reader, also to colleagues who have no
access to the knowledge base itself, so a share bypassed the knowledge base's access rules
(GDPR Art. 5(1)(f), 25(2)).

`withhold_unreadable_sources` runs on the shared copy only. For a reader who is not the owner it
keeps each source's label (which knowledge base or file was used) but empties the passages,
their metadata and distances when the reader could not open that source directly. The answer
text itself is unchanged: it is what the owner chose to share.
"""

from __future__ import annotations

from open_webui.models.access_grants import AccessGrants
from open_webui.models.knowledge import Knowledges
from open_webui.utils.access_control.files import has_access_to_file


async def _can_read_knowledge(knowledge_id: str, user, db, cache: dict) -> bool:
    key = ('knowledge', knowledge_id)
    if key not in cache:
        knowledge = await Knowledges.get_knowledge_by_id(knowledge_id, db=db)
        cache[key] = bool(
            knowledge
            and (
                knowledge.user_id == user.id
                or await AccessGrants.has_access(
                    user_id=user.id, resource_type='knowledge', resource_id=knowledge.id, permission='read', db=db
                )
            )
        )
    return cache[key]


async def _can_read_file(file_id: str, user, db, cache: dict) -> bool:
    key = ('file', file_id)
    if key not in cache:
        cache[key] = await has_access_to_file(file_id, 'read', user, db=db)
    return cache[key]


async def _can_read_source(item: dict, user, db, cache: dict) -> bool:
    if user is None:
        return False
    if getattr(user, 'role', None) == 'admin':
        return True
    source = item.get('source') if isinstance(item.get('source'), dict) else {}
    if source.get('type') == 'collection' and source.get('id'):
        return await _can_read_knowledge(source['id'], user, db, cache)
    file_ids = {
        meta.get('file_id') for meta in (item.get('metadata') or []) if isinstance(meta, dict) and meta.get('file_id')
    }
    if not file_ids:
        # Web search results and tool output carry no stored file: nothing to protect here.
        return True
    for file_id in file_ids:
        if not await _can_read_file(file_id, user, db, cache):
            return False
    return True


async def withhold_unreadable_sources(messages: list[dict], owner_id: str, user, db=None) -> int:
    """Empty, in place, the passages of every source the reader cannot open. Returns the count."""
    if user is not None and user.id == owner_id:
        return 0
    cache: dict = {}
    withheld = 0
    for message in messages:
        for item in message.get('sources') or []:
            if not isinstance(item, dict) or not item.get('document'):
                continue
            if await _can_read_source(item, user, db, cache):
                continue
            item['document'] = []
            item['metadata'] = []
            item['distances'] = []
            item['withheld'] = True
            withheld += 1
    return withheld
