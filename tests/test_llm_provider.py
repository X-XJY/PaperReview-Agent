import json
import pytest
from backend import db, llm
from backend.schemas import Metadata, Extraction


def provider(monkeypatch, tmp_path, finish='stop'):
    monkeypatch.setattr(db, 'DATA', tmp_path)
    monkeypatch.delenv('LLM_THINKING', raising=False)
    monkeypatch.setenv('LLM_MAX_OUTPUT_TOKENS', '10000')
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


@pytest.mark.parametrize('repair_succeeds', [True, False])
def test_metric_type_error_gets_targeted_repair(monkeypatch, tmp_path, repair_succeeds, caplog):
    provider(monkeypatch, tmp_path)
    invalid = {'method_name':'Transformer','methods':[], 'advantages':[],
               'limitations':[], 'future_work':[], 'evaluations':[
                   {'dataset':'WMT', 'metric':None, 'value':None,
                    'setting':'PRIVATE_SOURCE_SENTINEL', 'evidence_ids':['e1']}]}
    requests = []
    class Response:
        status_code = 200
        is_success = True
        def json(self):
            value = json.loads(json.dumps(invalid))
            if repair_succeeds and len(requests) == 3:
                value['evaluations'][0]['metric'] = ''
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            requests.append(json.loads(json.dumps(kwargs['json'])))
            return Response()
    monkeypatch.setattr(llm.httpx, 'Client', Client)
    if repair_succeeds:
        result = llm.call('extract', {}, Extraction, 'j')
        assert result.evaluations[0].metric == ''
        assert result.evaluations[0].evidence_ids == ['e1']
        llm.call('extract', {}, Extraction, 'j')
    else:
        with pytest.raises(llm.ProviderError, match=r'extract: evaluations.0.metric'):
            llm.call('extract', {}, Extraction, 'j')
        with db.connection() as conn:
            assert conn.execute('SELECT count(*) FROM cache').fetchone()[0] == 0
    assert len(requests) == 3
    assert len(requests[2]['messages']) == 4
    assert requests[1]['messages'][2]['role'] == 'assistant'
    assert 'evaluations.0.metric' in requests[1]['messages'][3]['content']
    assert 'string_type' in requests[1]['messages'][3]['content']
    assert 'PRIVATE_SOURCE_SENTINEL' not in caplog.text
