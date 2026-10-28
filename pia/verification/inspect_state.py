"""Read-only inspection of a running/stopped Open WebUI data directory.

Usage: python inspect_state.py <data_dir> [marker ...]
Prints: files on disk, non-empty tables with row counts, vector collections (id, count,
a sample of stored text and metadata), and which files on disk contain each marker
string as raw bytes (useful to see where content physically lives or survives deletion).
Uses copies of the databases so it never writes to the instance.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

data = sys.argv[1]
markers = sys.argv[2:]

print('== files on disk (relative path, bytes) ==')
for root, _, files in os.walk(data):
    for f in sorted(files):
        p = os.path.join(root, f)
        print(f'{os.path.relpath(p, data)}\t{os.path.getsize(p)}')

tmp = tempfile.mkdtemp()
for ext in ('', '-wal', '-shm'):
    src = os.path.join(data, 'webui.db' + ext)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(tmp, 'webui.db' + ext))
c = sqlite3.connect(os.path.join(tmp, 'webui.db'))
print('\n== non-empty tables ==')
for (t,) in c.execute("select name from sqlite_master where type='table' order by name").fetchall():
    n = c.execute(f'select count(*) from "{t}"').fetchone()[0]
    if n:
        print(f'{t}\t{n}')

print('\n== vector store ==')
try:
    import chromadb

    vtmp = os.path.join(tmp, 'vector_db')
    shutil.copytree(os.path.join(data, 'vector_db'), vtmp)
    cl = chromadb.PersistentClient(path=vtmp)
    cols = cl.list_collections()
    print('collections:', [x.name for x in cols])
    for col in cols:
        got = col.get(include=['documents', 'metadatas'])
        print(f'- {col.name}: {col.count()} chunk(s)')
        for i in range(min(2, len(got['ids']))):
            print('   text   :', (got['documents'][i] or '')[:160].replace('\n', ' | '))
            print('   meta   :', json.dumps(got['metadatas'][i])[:400])
except Exception as e:
    print('vector inspection failed:', e)

if markers:
    print('\n== raw-byte search for markers ==')
    for m in markers:
        hits = []
        for root, _, files in os.walk(data):
            for f in files:
                p = os.path.join(root, f)
                try:
                    if m.encode() in open(p, 'rb').read():
                        hits.append(os.path.relpath(p, data))
                except Exception:
                    pass
        print(f'{m!r}: {hits if hits else "not found on disk"}')
shutil.rmtree(tmp, ignore_errors=True)
