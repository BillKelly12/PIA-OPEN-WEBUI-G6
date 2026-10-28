"""Row counts of the tables that hold chat/file content (read from a copy of the DB)."""
import os, shutil, sqlite3, sys, tempfile
data = sys.argv[1]
tmp = tempfile.mkdtemp()
for ext in ('', '-wal', '-shm'):
    src = os.path.join(data, 'webui.db' + ext)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(tmp, 'webui.db' + ext))
c = sqlite3.connect(os.path.join(tmp, 'webui.db'))
tables = ['user', 'auth', 'chat', 'chat_message', 'chat_file', 'shared_chat', 'tag', 'file', 'memory', 'folder', 'note', 'feedback', 'access_grant', 'knowledge', 'knowledge_file', 'oauth_session', 'api_key']
print({t: c.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables})
try:
    import chromadb
    vt = os.path.join(tmp, 'v'); shutil.copytree(os.path.join(data, 'vector_db'), vt)
    cl = chromadb.PersistentClient(path=vt)
    print('vector collections:', {x.name: x.count() for x in cl.list_collections()})
except Exception as e:
    print('vector check failed', e)
shutil.rmtree(tmp, ignore_errors=True)
