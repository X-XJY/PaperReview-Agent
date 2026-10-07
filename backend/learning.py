"""Session-owned learning state; changed statements invalidate old mastery."""
import time
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Literal
from . import db

class LearningEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    node_id: str
    fingerprint: str
    status: Literal['not_started', 'review', 'mastered']

def nodes_for(job, paper_id):
    paper = next((p for p in (job.get('result') or {}).get('papers', []) if p['id'] == paper_id), None)
    if paper is None:
        raise HTTPException(404, '未找到论文。')
    theory = paper.get('theory') or {}
    return theory.get('nodes', []), theory.get('status') == 'pending'

def fingerprint(node):
    return db.digest({key: node.get(key) for key in ('kind', 'label', 'statement', 'conditions', 'evidence_ids')})

def progress(job, paper_id):
    nodes, pending = nodes_for(job, paper_id)
    with db.connection() as conn:
        stored = {r['node']: dict(r) for r in conn.execute('SELECT * FROM learning_progress WHERE job=? AND paper=?', (job['id'], paper_id))}
    return {'pending': pending, 'nodes': {n['id']: {'fingerprint': fingerprint(n),
        'status': stored[n['id']]['status'] if n['id'] in stored and stored[n['id']]['fingerprint'] == fingerprint(n) else 'not_started'} for n in nodes}}

def save(job, paper_id, value):
    nodes, pending = nodes_for(job, paper_id)
    node = next((n for n in nodes if n['id'] == value.node_id), None)
    if node is None:
        raise HTTPException(404, '未找到理论节点。')
    if pending or fingerprint(node) != value.fingerprint:
        raise HTTPException(409, '理论内容已更新，请刷新学习路径后再标记。')
    with db.connection() as conn:
        conn.execute('INSERT OR REPLACE INTO learning_progress VALUES(?,?,?,?,?,?)',
            (job['id'], paper_id, node['id'], value.fingerprint, value.status, time.time()))
    return progress(job, paper_id)
