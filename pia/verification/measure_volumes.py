"""Measure storage growth per uploaded document and per RAG chat turn (synthetic data).

Usage: python measure_volumes.py <data_dir> <bob_token> [n_docs] [doc_kb] [n_chats] [turns]
Needs: the instance running with a stub Ollama that returns ~1500-char replies
(STUB_REPLY_CHARS=1500). Sizes are measured on disk; per-unit figures are derived.
"""
import json, os, random, shutil, sqlite3, sys, tempfile, time, uuid
import requests
from scenario_common import BASE, bearer

data, tok = sys.argv[1], sys.argv[2]
n_docs = int(sys.argv[3]) if len(sys.argv) > 3 else 20
doc_kb = int(sys.argv[4]) if len(sys.argv) > 4 else 60
n_chats = int(sys.argv[5]) if len(sys.argv) > 5 else 10
turns = int(sys.argv[6]) if len(sys.argv) > 6 else 4
random.seed(7)
WORDS = 'research interview participant thesis chapter method survey analysis supervisor result discussion data sample ethics consent coding theme respondent literature'.split()


def du(path):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(path) for f in fs)


def db_live_bytes():
    t = tempfile.mkdtemp()
    for e in ('', '-wal', '-shm'):
        p = os.path.join(data, 'webui.db' + e)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(t, 'webui.db' + e))
    c = sqlite3.connect(os.path.join(t, 'webui.db'))
    c.execute('pragma wal_checkpoint(TRUNCATE)')
    ps = c.execute('pragma page_size').fetchone()[0]
    pc = c.execute('pragma page_count').fetchone()[0]
    fl = c.execute('pragma freelist_count').fetchone()[0]
    shutil.rmtree(t, ignore_errors=True)
    return (pc - fl) * ps


def snap():
    cl = None
    t = tempfile.mkdtemp(); vt = os.path.join(t, 'v'); shutil.copytree(os.path.join(data, 'vector_db'), vt)
    import chromadb
    cl = chromadb.PersistentClient(path=vt)
    chunks = sum(x.count() for x in cl.list_collections())
    out = {'db_live': db_live_bytes(), 'uploads': du(os.path.join(data, 'uploads')), 'vector_dir': du(os.path.join(data, 'vector_db')), 'vector_chunks': chunks}
    shutil.rmtree(t, ignore_errors=True)
    return out


def doc_text(kb):
    out, n = [], 0
    while n < kb * 1024:
        sent = ' '.join(random.choice(WORDS) for _ in range(random.randint(8, 18))).capitalize() + '. '
        out.append(sent); n += len(sent)
    return ''.join(out)


base = snap(); print('baseline', base)
fids = []
for i in range(n_docs):
    txt = doc_text(doc_kb).encode()
    r = requests.post(f'{BASE}/api/v1/files/', headers=bearer(tok), files={'file': (f'doc_{i}.txt', txt, 'text/plain')})
    fids.append(r.json()['id'])
for fid in fids:
    for _ in range(60):
        if requests.get(f'{BASE}/api/v1/files/{fid}/process/status', headers=bearer(tok)).json().get('status') in ('completed', 'failed'):
            break
        time.sleep(0.5)
after_docs = snap(); print('after docs', after_docs)

n_turns_done = 0
for ci in range(n_chats):
    cid, parent = None, None
    fid = fids[ci % len(fids)]
    for ti in range(turns):
        q = f'Question {ci}-{ti}: ' + ' '.join(random.choice(WORDS) for _ in range(25))
        body = {'model': 'stub-model:latest', 'stream': True, 'messages': [{'role': 'user', 'content': q}], 'parent_id': parent, 'id': str(uuid.uuid4()), 'session_id': 'm',
                'user_message': {'id': str(uuid.uuid4()), 'role': 'user', 'content': q, 'parentId': parent, 'timestamp': int(time.time())},
                'files': [{'type': 'file', 'id': fid, 'name': 'doc', 'status': 'uploaded'}], 'background_tasks': {'title_generation': True, 'tags_generation': True, 'follow_up_generation': True}}
        if cid:
            body['chat_id'] = cid
        r = requests.post(f'{BASE}/api/chat/completions', headers=bearer(tok), json=body).json()
        cid = r.get('chat_id', cid)
        for _ in range(60):  # wait until the assistant message is done
            ch = requests.get(f'{BASE}/api/v1/chats/{cid}', headers=bearer(tok)).json()
            h = ch['chat']['history']; cur = h['messages'].get(h.get('currentId'), {})
            if cur.get('role') == 'assistant' and cur.get('done'):
                break
            time.sleep(0.5)
        parent = h.get('currentId'); n_turns_done += 1
time.sleep(4)
after_chats = snap(); print('after chats', after_chats)
res = {
    'params': {'n_docs': n_docs, 'doc_kb': doc_kb, 'n_chats': n_chats, 'turns_per_chat': turns, 'turns_total': n_turns_done},
    'per_doc_bytes': {k: (after_docs[k] - base[k]) / n_docs for k in ('db_live', 'uploads', 'vector_dir')},
    'chunks_per_doc': (after_docs['vector_chunks'] - base['vector_chunks']) / n_docs,
    'per_turn_bytes_db': (after_chats['db_live'] - after_docs['db_live']) / n_turns_done,
    'per_turn_bytes_vector': (after_chats['vector_dir'] - after_docs['vector_dir']) / n_turns_done,
}
print(json.dumps(res, indent=1))
json.dump({'baseline': base, 'after_docs': after_docs, 'after_chats': after_chats, 'result': res}, open(os.path.join(os.path.dirname(data), 'volumes.json'), 'w'), indent=1)
