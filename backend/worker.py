"""One durable worker per deployment; checkpoint/cache safe on restart."""
import json
import os
import threading
import time
from . import db
from .pipeline import run
from .cleanup import cleanup

def heartbeat():
    while True:
        with db.connection() as conn:
            conn.execute('INSERT OR REPLACE INTO worker_state VALUES(1,?)',(time.time(),))
        time.sleep(5)

def main():
    db.init()
    # Deployment contract: a single worker owns the queue. Reclaim work left by its prior process.
    with db.connection() as conn:
        conn.execute("UPDATE jobs SET status='queued',stage='恢复中' WHERE status='running'")
    threading.Thread(target=heartbeat,daemon=True).start()
    last_cleanup=0
    while True:
        if time.time()-last_cleanup>3600:
            cleanup()
            last_cleanup=time.time()
        with db.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row:
                conn.execute("UPDATE jobs SET status='running',stage='准备处理',updated=? WHERE id=?",(time.time(),row['id']))
        if not row:
            time.sleep(1)
            continue
        job = db.get(row['id'])
        try:
            run(job)
        except Exception as error:
            message = str(error) if isinstance(error,RuntimeError) else '任务中断。已保留中间结果，可重试。'
            db.update(job['id'],status='failed',stage='任务中断',error=message)

if __name__ == '__main__':
    main()
