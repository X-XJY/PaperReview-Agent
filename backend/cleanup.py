"""Delete expired session-owned files and analysis data. Invoke during worker idle time."""
import os
import shutil
import time
from . import db
from .config import DATA

def cleanup():
    cutoff=time.time()-int(os.getenv('SESSION_TTL_DAYS','7'))*86400
    expired=[]
    with db.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for row in conn.execute('SELECT id FROM sessions WHERE created<?',(cutoff,)).fetchall():
            sid=row['id']
            if conn.execute("SELECT 1 FROM jobs WHERE session=? AND status IN ('queued','running')",(sid,)).fetchone():
                continue
            conn.execute('DELETE FROM revisions WHERE job IN (SELECT id FROM jobs WHERE session=?)',(sid,))
            conn.execute('DELETE FROM jobs WHERE session=?',(sid,))
            conn.execute('DELETE FROM sessions WHERE id=?',(sid,))
            expired.append(sid)
        # Cache also contains derived document text. Respect the same retention window.
        conn.execute('DELETE FROM cache WHERE created<?',(cutoff,))
    root=(DATA/'files').resolve()
    for sid in expired:
        path=(root/sid).resolve()
        if path.parent == root and path.is_dir():
            shutil.rmtree(path)
