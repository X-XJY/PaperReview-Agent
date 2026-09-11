"""A separate single worker; never reclaims the batch analysis queue."""
import threading
import time
from . import db
from .tutor import run, set_state

def heartbeat():
    while True:
        with db.connection() as c:
            c.execute('INSERT OR REPLACE INTO tutor_worker_state VALUES(1,?)',(time.time(),))
        time.sleep(5)

def main():
    db.init()
    with db.connection() as c:
        c.execute("UPDATE tutor_tasks SET status='queued',stage='恢复中' WHERE status='running'")
    threading.Thread(target=heartbeat,daemon=True).start()
    while True:
        with db.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute("SELECT id FROM tutor_tasks WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row:
                c.execute("UPDATE tutor_tasks SET status='running',stage='准备中',updated=? WHERE id=?",(time.time(),row[0]))
        if not row:
            time.sleep(1)
            continue
        try:
            run(row[0])
        except Exception as error:
            message=str(error) if isinstance(error,RuntimeError) else '本轮未完成，已保留历史。请重试或缩小问题。'
            set_state(row[0],'回答失败',status='failed',error=message)

if __name__=='__main__':
    main()
