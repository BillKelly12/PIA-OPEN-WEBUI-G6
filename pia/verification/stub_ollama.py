"""Protocol stub standing in for a local Ollama server (verification only).

It answers the few Ollama endpoints Open WebUI calls and writes EVERY request it
receives (method, path, headers, body) to a JSONL log. That log is the evidence of
what Open WebUI sends to the model server. It is NOT a model: replies are fixed.

Usage: python stub_ollama.py <port> <log.jsonl>
"""
import hashlib
import json
import os
import sys
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 11434
LOG = sys.argv[2] if len(sys.argv) > 2 else 'stub_ollama.jsonl'
DIM = 16
app = FastAPI()


def _embed(text: str) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    return [(h[i] - 128) / 128.0 for i in range(DIM)]


@app.middleware('http')
async def log_everything(request: Request, call_next):
    body = await request.body()
    try:
        parsed = json.loads(body) if body else None
    except Exception:
        parsed = body.decode(errors='replace')
    with open(LOG, 'a') as f:
        f.write(
            json.dumps(
                {
                    't': time.time(),
                    'method': request.method,
                    'path': request.url.path,
                    'headers': dict(request.headers),
                    'body': parsed,
                }
            )
            + '\n'
        )

    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': False}

    request._receive = receive
    return await call_next(request)


@app.get('/api/version')
async def version():
    return {'version': '0.0.0-stub'}


@app.get('/api/tags')
async def tags():
    m = {
        'name': 'stub-model:latest',
        'model': 'stub-model:latest',
        'modified_at': '2026-01-01T00:00:00Z',
        'size': 1,
        'digest': 'stub',
        'details': {'family': 'stub', 'parameter_size': '0B', 'quantization_level': 'none'},
    }
    return {'models': [m]}


@app.get('/api/ps')
async def ps():
    return {'models': []}


@app.post('/api/embed')
async def embed(request: Request):
    data = await request.json()
    inputs = data.get('input') or []
    if isinstance(inputs, str):
        inputs = [inputs]
    return {'model': data.get('model'), 'embeddings': [_embed(t) for t in inputs]}


def _canned_reply(messages: list[dict]) -> str:
    """Fixed fixture replies. Task prompts get the JSON shape Open WebUI expects; everything
    else gets a constant sentence. No inference happens here."""
    text = ' '.join(str(m.get('content', '')) for m in messages)
    head = text[:600].lower()
    if 'search queries' in head:
        return json.dumps({'queries': ['stub query']})
    if 'generate a concise' in head and 'title' in head:
        return json.dumps({'title': 'Stub chat title'})
    if 'tags' in head and 'categor' in text.lower()[:900]:
        return json.dumps({'tags': ['stub-tag-a', 'stub-tag-b']})
    if 'follow' in head and 'up' in head:
        return json.dumps({'follow_ups': ['stub follow-up?']})
    n = int(os.environ.get('STUB_REPLY_CHARS', '0'))
    return ('stub reply. ' * (n // 12 + 1))[:n] if n else 'stub reply'


@app.post('/api/chat')
async def chat(request: Request):
    data = await request.json()
    reply = _canned_reply(data.get('messages') or [])
    now = '2026-01-01T00:00:00Z'
    done_part = {'done': True, 'done_reason': 'stop', 'total_duration': 1, 'prompt_eval_count': 1, 'eval_count': 1}

    if data.get('stream') is False:
        return JSONResponse({'model': data.get('model'), 'created_at': now, 'message': {'role': 'assistant', 'content': reply}, **done_part})

    async def gen():
        yield json.dumps({'model': data.get('model'), 'created_at': now, 'message': {'role': 'assistant', 'content': reply}, 'done': False}) + '\n'
        yield json.dumps({'model': data.get('model'), 'created_at': now, 'message': {'role': 'assistant', 'content': ''}, **done_part}) + '\n'

    return StreamingResponse(gen(), media_type='application/x-ndjson')


@app.api_route('/{path:path}', methods=['GET', 'POST', 'DELETE', 'PUT'])
async def fallback(path: str):
    return JSONResponse({})


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='warning')
