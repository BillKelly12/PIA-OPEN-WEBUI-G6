"""Replay the research-lab scenario against a running instance and print one line per observation.

Usage:  python run_scenario.py <work_dir>        (work_dir = the folder given to run_instance.sh)
Needs:  instance + stub Ollama + egress proxy started with run_instance.sh on a FRESH data dir.
Data:   synthetic only. Markers such as INTERVIEWEE-MARKER-7731 stand in for personal data.
Output: lines "R## OBSERVED|DIFFERS  <what was checked> -> <what was seen>".
        OBSERVED means the result matches what pia/data-flow-analysis.md states.
It describes behaviour, it does not judge it. It does not modify application code.
"""
import json, os, shutil, sqlite3, sys, tempfile, time, uuid
import requests
from scenario_common import BASE, bearer

WORK = sys.argv[1]
DATA = os.path.join(WORK, 'data')
LOGS = os.path.join(WORK, 'logs')
M_INT = 'INTERVIEWEE-MARKER-7731'   # in an interview transcript
M_SUR = 'SURVEY-RESPONDENT-MARKER-5520'
M_CHAT = 'CHAT-TEXT-MARKER-9042'
results = []


def rec(rid, expected_ok, what, seen):
    results.append((rid, 'OBSERVED' if expected_ok else 'DIFFERS', what, seen))
    print(f'{rid} {"OBSERVED" if expected_ok else "DIFFERS "} {what} -> {seen}', flush=True)


def jl(path):
    if not os.path.exists(path):
        return []
    return [json.loads(x) for x in open(path) if x.strip()]


def db_copy(checkpoint=False):
    t = tempfile.mkdtemp()
    for e in ('', '-wal', '-shm'):
        p = os.path.join(DATA, 'webui.db' + e)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(t, 'webui.db' + e))
    c = sqlite3.connect(os.path.join(t, 'webui.db'))
    if checkpoint:
        c.execute('pragma wal_checkpoint(TRUNCATE)')
    return c, t


def tables_nonempty():
    c, t = db_copy()
    out = {n: c.execute(f'select count(*) from "{n}"').fetchone()[0]
           for (n,) in c.execute("select name from sqlite_master where type='table'")}
    shutil.rmtree(t, ignore_errors=True)
    return {k: v for k, v in out.items() if v}


def where_marker(marker):
    hits = []
    for root, _, files in os.walk(DATA):
        for f in files:
            p = os.path.join(root, f)
            try:
                if marker.encode() in open(p, 'rb').read():
                    hits.append(os.path.relpath(p, DATA))
            except Exception:
                pass
    return sorted(hits)


def vector_collections():
    import chromadb
    t = tempfile.mkdtemp(); v = os.path.join(t, 'v'); shutil.copytree(os.path.join(DATA, 'vector_db'), v)
    cl = chromadb.PersistentClient(path=v)
    out = {}
    for col in cl.list_collections():
        got = col.get(include=['documents', 'metadatas'])
        out[col.name] = (col.count(), ' '.join(got['documents'] or []))
    shutil.rmtree(t, ignore_errors=True)
    return out


def api(method, path, tok=None, **kw):
    h = bearer(tok) if tok else {}
    return requests.request(method, BASE + path, headers=h, **kw)


def wait_file(tok, fid):
    for _ in range(80):
        s = api('GET', f'/api/v1/files/{fid}/process/status', tok).json().get('status')
        if s in ('completed', 'failed'):
            return s
        time.sleep(0.5)


def turn(tok, text, files=None, chat_id=None, parent=None, tasks=None):
    body = {'model': 'stub-model:latest', 'stream': True, 'messages': [{'role': 'user', 'content': text}],
            'parent_id': parent, 'id': str(uuid.uuid4()), 'session_id': 'scn',
            'user_message': {'id': str(uuid.uuid4()), 'role': 'user', 'content': text, 'parentId': parent, 'timestamp': int(time.time())}}
    if files:
        body['files'] = [{'type': 'file', 'id': f, 'name': 'doc', 'status': 'uploaded'} for f in files]
    if tasks:
        body['background_tasks'] = tasks
    if chat_id:
        body['chat_id'] = chat_id
    r = api('POST', '/api/chat/completions', tok, json=body).json()
    cid = r.get('chat_id', chat_id)
    h = {}
    for _ in range(80):
        if cid and not str(cid).startswith(('local:', 'temporary:')):
            ch = api('GET', f'/api/v1/chats/{cid}', tok).json()
            h = ch['chat']['history']
            cur = h['messages'].get(h.get('currentId'), {})
            if cur.get('role') == 'assistant' and cur.get('done'):
                break
        else:
            time.sleep(2); break
        time.sleep(0.5)
    time.sleep(2)
    return cid, h.get('currentId')


# ---------- R03 idle baseline ----------
time.sleep(1)
tb = tables_nonempty()
rec('R03', set(tb) <= {'alembic_version', 'config'} and not jl(os.path.join(LOGS, 'egress.jsonl')) and not jl(os.path.join(LOGS, 'ollama_requests.jsonl')),
    'idle start: non-empty tables, outbound connections, model-server calls', f'tables={tb}')

# ---------- R01 accounts ----------
r = api('POST', '/api/v1/auths/signup', json={'name': 'Dr Admin', 'email': 'admin@lab.test', 'password': 'pw-admin-1', 'profile_image_url': ''})
admin = r.json(); at = admin['token']
r2 = api('POST', '/api/v1/auths/signup', json={'name': 'Mallory', 'email': 'm@lab.test', 'password': 'pw-m-1', 'profile_image_url': ''})
users = {}
for n in ('alice', 'bob'):
    j = api('POST', '/api/v1/auths/add', at, json={'name': n.title(), 'email': f'{n}@lab.test', 'password': f'pw-{n}-1', 'role': 'user'}).json()
    users[n] = j['id']
rec('R01', admin.get('role') == 'admin' and r2.status_code == 403 and all(api('GET', f'/api/v1/users/{u}', at).json().get('role') == 'user' for u in users.values()),
    'first signup role / later self-signup status / admin-created role', f"{admin.get('role')} / {r2.status_code} / user")

# ---------- R02 cookie ----------
s = requests.post(BASE + '/api/v1/auths/signin', json={'email': 'alice@lab.test', 'password': 'pw-alice-1'})
ck = s.headers.get('set-cookie', '')
tok = {n: requests.post(BASE + '/api/v1/auths/signin', json={'email': f'{n}@lab.test', 'password': f'pw-{n}-1'}).json()['token'] for n in users}
rec('R02', 'HttpOnly' in ck and 'Secure' not in ck and 'max-age=2419200' in ck.lower() and 'samesite=lax' in ck.lower(),
    'session cookie attributes', ck.split(';', 1)[1].strip() if ';' in ck else ck)

# ---------- R05 / R04 models + egress ----------
before = len(api('GET', '/api/models', tok['bob']).json().get('data', []))
api('POST', '/api/v1/models/create', at, json={'id': 'stub-model:latest', 'base_model_id': None, 'name': 'stub', 'meta': {}, 'params': {},
    'access_grants': [{'principal_type': 'user', 'principal_id': u, 'permission': 'read'} for u in users.values()], 'is_active': True})
after = len(api('GET', '/api/models', tok['bob']).json().get('data', []))
rec('R05', before == 0 and after >= 1, 'models visible to an ordinary user before / after admin grant', f'{before} / {after}')
eg = jl(os.path.join(LOGS, 'egress.jsonl'))
rec('R04', any('api.openai.com' in e['target'] for e in eg) and all('openai' in e['target'] for e in eg),
    'outbound connection attempts seen after 2 model listings (only destinations are recorded, no payload)', f"{len(eg)} attempt(s) to {sorted({e['target'] for e in eg})}")

# ---------- R06 upload ----------
doc = f'Interview transcript P07. Participant name: Jane Roe. {M_INT} says the supervisor pressured them.\n' * 3
fid = api('POST', '/api/v1/files/', tok['alice'], files={'file': ('interview_p07.txt', doc.encode(), 'text/plain')}).json()
file_id = fid['id']; st = wait_file(tok['alice'], file_id)
f = api('GET', f'/api/v1/files/{file_id}', tok['alice']).json()
c, t = db_copy(); row = c.execute('select data from file where id=?', (file_id,)).fetchone(); shutil.rmtree(t, ignore_errors=True)
in_db_row = bool(row) and M_INT in str(row[0])
vc = vector_collections().get(f'file-{file_id}', (0, ''))
oll = jl(os.path.join(LOGS, 'ollama_requests.jsonl'))
embed_has = any('/api/embed' in o.get('path', '') and M_INT in json.dumps(o.get('body')) for o in oll)
hits = where_marker(M_INT)
rec('R06', st == 'completed' and any(h.startswith('uploads/') for h in hits) and in_db_row and any('vector_db' in h for h in hits) and embed_has and vc[0] > 0,
    'upload: marker found on disk in (raw bytes) / marker in file.data row / chunk count / embed request carried text / path in response', f"{hits} / {in_db_row} / {vc[0]} / {embed_has} / {fid.get('path') or f.get('path')}")

# ---------- R07 RAG turn ----------
n0 = len(jl(os.path.join(LOGS, 'ollama_requests.jsonl')))
cid, mid = turn(tok['alice'], f'What does participant P07 say? {M_CHAT}', [file_id], tasks={'title_generation': True, 'tags_generation': True, 'follow_up_generation': True})
oll = jl(os.path.join(LOGS, 'ollama_requests.jsonl'))[n0:]
paths = [o['path'] for o in oll]
ans = [o for o in oll if '/api/chat' in o['path']]
ctx_in_prompt = any(M_INT in json.dumps(o.get('body')) for o in ans)
chat = api('GET', f'/api/v1/chats/{cid}', tok['alice']).json()
c, t = db_copy(); msg_sources = c.execute('select count(*) from chat_message where sources is not null and sources != "null"').fetchone()[0]
tags = c.execute('select count(*) from tag').fetchone()[0]; shutil.rmtree(t, ignore_errors=True)
rec('R07', ctx_in_prompt and len(oll) >= 3 and msg_sources >= 1,
    'one RAG turn: calls to model server / passage text inside the prompt / stored message rows with sources / tag rows / title',
    f"{len(oll)} calls {sorted(set(paths))} / {ctx_in_prompt} / {msg_sources} / {tags} / {chat.get('title')!r}")

# ---------- R08 sharing ----------
sh = api('POST', f'/api/v1/chats/{cid}/share', tok['alice'], json={}).json()
share_id = sh.get('share_id')
anon = requests.get(f'{BASE}/api/v1/chats/share/{share_id}').status_code
bob_no = api('GET', f'/api/v1/chats/share/{share_id}', tok['bob']).status_code
pub = api('POST', f'/api/v1/chats/shared/{cid}/access/update', tok['alice'], json={'access_grants': [{'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}]})
c, t = db_copy(); anyone_rows = c.execute("select count(*) from access_grant where resource_type like '%chat%' and principal_id='*'").fetchone()[0]; shutil.rmtree(t, ignore_errors=True)
api('POST', f'/api/v1/chats/shared/{cid}/access/update', tok['alice'], json={'access_grants': [{'principal_type': 'user', 'principal_id': users['bob'], 'permission': 'read'}]})
bob_yes = api('GET', f'/api/v1/chats/share/{share_id}', tok['bob'])
bob_text = M_INT in bob_yes.text
bob_file = api('GET', f'/api/v1/files/{file_id}', tok['bob']).status_code
bob_content = api('GET', f'/api/v1/files/{file_id}/data/content', tok['bob']).status_code
adm_share = api('GET', f'/api/v1/chats/share/{share_id}', at).status_code
rec('R08', (anon, bob_no) == (401, 401) and anyone_rows == 0 and bob_yes.status_code == 200 and bob_text and bob_file in (401, 404) and bob_content in (401, 404),
    "share: link without login / user without grant / 'anyone' grant rows after attempt / granted user sees passages / same user on underlying file + content / admin",
    f'{anon} / {bob_no} / {anyone_rows} / {bob_yes.status_code}, passages visible={bob_text} / {bob_file}+{bob_content} / {adm_share}')

# ---------- R09 admin power ----------
checks = {
    'chat list of other user': f'/api/v1/chats/list/user/{users["alice"]}',
    'any chat': f'/api/v1/chats/{cid}',
    'export all chats': '/api/v1/chats/all/db',
    'file record': f'/api/v1/files/{file_id}',
    'extracted text': f'/api/v1/files/{file_id}/data/content',
    'raw file': f'/api/v1/files/{file_id}/content',
    'all users': '/api/v1/users/all',
    'analytics summary': '/api/v1/analytics/summary',
    'database file': '/api/v1/utils/db/download',
}
out_a, out_b = {}, {}
for k, p in checks.items():
    ra = api('GET', p, at); rb = api('GET', p, tok['bob'])
    out_a[k] = ra.status_code; out_b[k] = rb.status_code
dbsize = len(api('GET', '/api/v1/utils/db/download', at).content)
webui_out = open(os.path.join(LOGS, 'webui.out'), errors='replace').read()
admin_lines = [l for l in webui_out.splitlines() if 'admin@lab.test' in l and 'all/db' in l]
rec('R09', all(v == 200 for v in out_a.values()) and all(v in (401, 403, 404) for v in out_b.values()) and not os.path.exists(os.path.join(DATA, 'audit.log')),
    'admin status codes / ordinary user status codes / db download bytes / audit.log present / log lines naming the admin for a bulk export',
    f'{out_a} / {out_b} / {dbsize} / {os.path.exists(os.path.join(DATA, "audit.log"))} / {len(admin_lines)}')

# ---------- R13 temporary chat ----------
before_rows = tables_nonempty(); n0 = len(jl(os.path.join(LOGS, 'ollama_requests.jsonl')))
turn(tok['bob'], 'TEMP-CHAT-MARKER-3317 hello', chat_id='local:' + uuid.uuid4().hex)
after_rows = tables_nonempty(); n1 = len(jl(os.path.join(LOGS, 'ollama_requests.jsonl')))
rec('R13', after_rows.get('chat', 0) == before_rows.get('chat', 0) and not where_marker('TEMP-CHAT-MARKER-3317') and n1 > n0,
    'temporary chat: new chat rows / marker on disk / calls to model server', f"{after_rows.get('chat',0) - before_rows.get('chat',0)} / {where_marker('TEMP-CHAT-MARKER-3317')} / {n1 - n0}")

# ---------- R14 logs ----------
rec('R14', 'alice@lab.test' in webui_out and M_INT not in webui_out and M_CHAT not in webui_out,
    'default log: contains login e-mail / contains chunk text / contains chat text', f"{'alice@lab.test' in webui_out} / {M_INT in webui_out} / {M_CHAT in webui_out}")

# ---------- R10 delete chat ----------
c, t = db_copy(); pre_chat = c.execute('select count(*) from chat').fetchone()[0]; shutil.rmtree(t, ignore_errors=True)
grant_before = None
c, t = db_copy(); grant_before = c.execute("select count(*) from access_grant where resource_type like '%chat%'").fetchone()[0]; shutil.rmtree(t, ignore_errors=True)
d = api('DELETE', f'/api/v1/chats/{cid}', tok['alice']).status_code
c, t = db_copy()
rows = {n: c.execute(f'select count(*) from {n}').fetchone()[0] for n in ('chat', 'chat_message', 'shared_chat', 'tag')}
grant_after = c.execute("select count(*) from access_grant where resource_type like '%chat%'").fetchone()[0]; shutil.rmtree(t, ignore_errors=True)
wal_hit = [h for h in where_marker(M_CHAT) if h.endswith('webui.db-wal')]
c, t = db_copy(checkpoint=True); c.close()
main_hit = [h for h in where_marker(M_CHAT) if h == 'webui.db']
# main-file check on the checkpointed copy
with open(os.path.join(t, 'webui.db'), 'rb') as fh:
    in_copy = M_CHAT.encode() in fh.read()
shutil.rmtree(t, ignore_errors=True)
rec('R10', d == 200 and rows == {'chat': 0, 'chat_message': 0, 'shared_chat': 0, 'tag': 0},
    'delete chat: status / rows left (chat, chat_message, shared_chat, tag) / grant rows before->after / marker in -wal file now / marker in checkpointed main file',
    f'{d} / {rows} / {grant_before}->{grant_after} / {bool(wal_hit)} / {in_copy}')

# ---------- R11 delete file ----------
d = api('DELETE', f'/api/v1/files/{file_id}', tok['alice']).status_code
vc = vector_collections().get(f'file-{file_id}', (0, ''))
rec('R11', d == 200 and not any(h.startswith('uploads/') for h in where_marker(M_INT)) and vc[0] > 0 and M_INT in vc[1],
    'delete file: status / marker still in uploads / chunks still in vector collection file-{id} and containing text',
    f"{d} / {[h for h in where_marker(M_INT) if h.startswith('uploads/')]} / {vc[0]} chunk(s), text present={M_INT in vc[1]}")

# ---------- R12 delete user ----------
sur = api('POST', '/api/v1/files/', tok['alice'], files={'file': ('survey_q.txt', f'Survey free-text. {M_SUR} reports burnout.\n'.encode() * 3, 'text/plain')}).json()
wait_file(tok['alice'], sur['id'])
api('POST', '/api/v1/memories/add', tok['alice'], json={'content': f'Remember: {M_SUR} memory text'})
api('POST', '/api/v1/folders/', tok['alice'], json={'name': 'alice-folder'})
try:
    api('POST', '/api/v1/notes/create', tok['alice'], json={'title': 'alice-note', 'data': {'content': {'md': f'{M_SUR} note'}}})
except Exception:
    pass
time.sleep(2)
d = api('DELETE', f'/api/v1/users/{users["alice"]}', at).status_code
c, t = db_copy()
left = {}
for (n,) in c.execute("select name from sqlite_master where type='table'").fetchall():
    cols = [x[1] for x in c.execute(f'pragma table_info("{n}")')]
    if 'user_id' in cols:
        k = c.execute(f'select count(*) from "{n}" where user_id=?', (users['alice'],)).fetchone()[0]
        if k:
            left[n] = k
shutil.rmtree(t, ignore_errors=True)
un = c = None
vcs = {k: v for k, v in vector_collections().items() if M_SUR in v[1]}
files_left = [h for h in where_marker(M_SUR) if h.startswith('uploads/')]
rec('R12', d == 200 and bool(left) and bool(vcs) and bool(files_left),
    "admin deletes Alice: status / tables still holding rows with her user_id / vector collections still holding her survey text / upload files left",
    f'{d} / {left} / {sorted(vcs)} / {files_left}')

print('\nSUMMARY:', {r[0]: r[1] for r in results})
print('R15 (volumes) is produced by measure_volumes.py, not here.')
