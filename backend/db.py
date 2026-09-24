import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from .config import DATA

def uid():
    return uuid.uuid4().hex

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

@contextmanager
def connection():
    db = sqlite3.connect(DATA / 'app.db', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

def init():
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, session TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL, payload TEXT NOT NULL, result TEXT, error TEXT, created REAL NOT NULL, updated REAL NOT NULL, calls INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, cache_hits INTEGER NOT NULL DEFAULT 0, stale INTEGER NOT NULL DEFAULT 0, generation INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS jobs_session ON jobs(session, created);
        CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, created);
        CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY, job TEXT NOT NULL, paper TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS worker_state(id INTEGER PRIMARY KEY CHECK(id=1), heartbeat REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS tutor_threads(id TEXT PRIMARY KEY, session TEXT NOT NULL, job TEXT NOT NULL, scope TEXT NOT NULL, created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_tutor_threads_job ON tutor_threads(session,job,created);
        CREATE TABLE IF NOT EXISTS tutor_tasks(id TEXT PRIMARY KEY, thread TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL, snapshot TEXT NOT NULL, request TEXT NOT NULL, history TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL, answer TEXT, error TEXT, calls INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, cache_hits INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(thread,request_id));
        CREATE INDEX IF NOT EXISTS idx_tutor_tasks_queue ON tutor_tasks(status,created);
        CREATE INDEX IF NOT EXISTS idx_tutor_tasks_thread ON tutor_tasks(thread,created);
        CREATE INDEX IF NOT EXISTS idx_tutor_tasks_cache ON tutor_tasks(fingerprint,status);
        CREATE TABLE IF NOT EXISTS tutor_usage(id TEXT PRIMARY KEY, task TEXT NOT NULL, tokens INTEGER NOT NULL, created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_tutor_usage_created ON tutor_usage(created);
        CREATE TABLE IF NOT EXISTS tutor_worker_state(id INTEGER PRIMARY KEY CHECK(id=1), heartbeat REAL NOT NULL);
        ''')

def cache_get(key, job_id=None):
    with connection() as db:
        row = db.execute('SELECT value FROM cache WHERE key=?', (key,)).fetchone()
        if row and job_id:
            db.execute('UPDATE jobs SET cache_hits=cache_hits+1 WHERE id=?', (job_id,))
        return json.loads(row['value']) if row else None

def cache_put(key, value):
    with connection() as db:
        db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', (key, json.dumps(value, ensure_ascii=False), time.time()))

def update(job_id, **fields):
    allowed = {'status','stage','result','error','stale','payload'}
    assert fields.keys() <= allowed
    fields['updated'] = time.time()
    with connection() as db:
        db.execute('UPDATE jobs SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?', (*fields.values(), job_id))

def get(job_id, session=None):
    with connection() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?'+(' AND session=?' if session else ''), (job_id, session) if session else (job_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    for key in ('payload','result'):
        result[key] = json.loads(result[key]) if result[key] else None
    return result
