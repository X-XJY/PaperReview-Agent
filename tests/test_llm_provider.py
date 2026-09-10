import json
import pytest
from backend import db, llm
from backend.schemas import Metadata


def provider(monkeypatch, tmp_path, finish='stop'):
    monkeypatch.setattr(db, 'DATA', tmp_path)
    monkeypatch.delenv('LLM_THINKING', raising=False)
    db.init()
    with db.connection() as conn:
        conn.execute("INSERT INTO jobs(id,session,status,stage,payload,created,updated) VALUES('j','s','running','test','{}',0,0)")
    requests = []
    class Response:
        status_code = 200
        is_success = True
        def json(self):
            content = json.dumps({'title':'Example','authors':[],'year':2020,'venue':None,'task':'QA','evidence_ids':['e']})
            return {'choices':[{'finish_reason':finish,'message':{'content':content}}], 'usage':{'completion_tokens':10000}}
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            requests.append(kwargs['json'])
            return Response()
    monkeypatch.setattr(llm.httpx, 'Client', Client)
    return requests


def test_truncated_completion_is_not_accepted_or_retried(monkeypatch, tmp_path):
    requests = provider(monkeypatch, tmp_path, 'length')
    with pytest.raises(llm.ProviderError, match='长度上限'):
        llm.call('metadata', {}, Metadata, 'j')
    assert len(requests) == 1
    assert db.get('j')['output_tokens'] == 10000
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM cache').fetchone()[0] == 0


def test_thinking_opt_in_and_cache_invalidation(monkeypatch, tmp_path):
    requests = provider(monkeypatch, tmp_path)
    llm.call('metadata', {}, Metadata, 'j')
    assert 'thinking' not in requests[0]
    monkeypatch.setenv('LLM_THINKING', 'disabled')
    llm.call('metadata', {}, Metadata, 'j')
    llm.call('metadata', {}, Metadata, 'j')
    assert len(requests) == 2
    assert requests[1]['thinking'] == {'type':'disabled'}
    monkeypatch.setenv('LLM_MAX_OUTPUT_TOKENS', '16000')
    llm.call('metadata', {}, Metadata, 'j')
    assert len(requests) == 3 and requests[2]['max_tokens'] == 16000
