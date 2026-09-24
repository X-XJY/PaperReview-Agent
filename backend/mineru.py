import hashlib
import io
import json
import os
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import httpx
from . import db
from .schemas import Evidence

BASE = 'https://mineru.net/api/v4'

def checked_url(url):
    host = (urlparse(url).hostname or '').lower()
    if urlparse(url).scheme != 'https' or not any(host == d or host.endswith('.'+d) for d in ('mineru.net','openxlab.org.cn','aliyuncs.com')):
        raise RuntimeError('解析服务返回了非预期文件域名。')
    return url

def parse(path: Path, paper_id, job_id):
    key = db.digest({'pdf':paper_id,'parser':'mineru-v4-vlm','adapter':1})
    cached = db.cache_get(key, job_id)
    if cached:
        return [Evidence.model_validate(x) for x in cached]
    headers = {'Authorization':'Bearer '+os.getenv('MINERU_API_KEY','')}
    ticket_key = key + ':ticket'
    ticket = db.cache_get(ticket_key)
    try:
        with httpx.Client(timeout=90, follow_redirects=False) as client:
            if not ticket:
                response = client.post(BASE+'/file-urls/batch', headers=headers, json={'files':[{'name':path.name,'data_id':paper_id}], 'model_version':'vlm'})
                response.raise_for_status()
                result = response.json()
                if result.get('code') != 0:
                    raise RuntimeError('MinerU 拒绝创建任务，请检查 Token 或额度。')
                ticket = result['data']
                # Persist ticket before upload; a retry reuses the same remote job.
                db.cache_put(ticket_key, ticket)
            if not ticket.get('uploaded'):
                with path.open('rb') as file:
                    upload = client.put(checked_url(ticket['file_urls'][0]), content=file)
                    upload.raise_for_status()
                ticket['uploaded'] = True
                db.cache_put(ticket_key, ticket)
            deadline = time.monotonic() + int(os.getenv('MINERU_TIMEOUT_SECONDS','900'))
            while time.monotonic() < deadline:
                result = client.get(BASE+'/extract-results/batch/'+ticket['batch_id'], headers=headers)
                result.raise_for_status()
                body = result.json()
                if body.get('code') != 0:
                    raise RuntimeError('MinerU 任务查询失败，请稍后重试。')
                rows = body.get('data',{}).get('extract_result',[])
                item = rows[0] if rows else {}
                if item.get('state') == 'failed':
                    with db.connection() as conn:
                        conn.execute('DELETE FROM cache WHERE key=?', (ticket_key,))
                    raise RuntimeError('MinerU 未能解析这篇 PDF，可检查文件后重试。')
                if item.get('state') == 'done':
                    buffer = bytearray()
                    with client.stream('GET', checked_url(item['full_zip_url'])) as response:
                        response.raise_for_status()
                        for part in response.iter_bytes():
                            buffer.extend(part)
                            if len(buffer) > 100 * 1024 * 1024:
                                raise RuntimeError('解析结果超过安全大小限制。')
                    evidence = unpack(bytes(buffer), paper_id)
                    db.cache_put(key, [x.model_dump() for x in evidence])
                    return evidence
                time.sleep(3)
    except httpx.HTTPError:
        raise RuntimeError('MinerU 连接或文件传输失败，已保存任务信息，可稍后重试。') from None
    raise RuntimeError('MinerU 排队或解析超时，已保留远程任务，下次重试继续查询。')

def unpack(data, paper_id):
    blocks = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 200 * 1024 * 1024:
            raise RuntimeError('解压结果超过大小限制。')
        names = archive.namelist()
        name = next((n for n in names if n.endswith('_content_list.json')), None)
        if name:
            content = json.loads(archive.read(name))
            section = ''
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get('text') or item.get('table_body') or ''
                captions = item.get('table_caption') or item.get('img_caption') or []
                text += '\n' + ('\n'.join(captions) if isinstance(captions,list) else str(captions))
                if item.get('text_level'):
                    section = text.strip()
                if text.strip():
                    blocks.append((text.strip(), item.get('page_idx'), section))
        if not blocks:
            md = next((n for n in names if n.endswith('full.md')), None)
            if not md:
                raise RuntimeError('解析包缺少可读取正文。')
            section = ''
            for part in archive.read(md).decode('utf-8').split('\n\n'):
                if part.startswith('#'):
                    section = part.lstrip('# ').strip()
                if part.strip():
                    blocks.append((part.strip(), None, section))
    if not blocks:
        raise RuntimeError('未提取到论文正文。')
    # Bound individual chunks; retain all text and deterministic locators.
    result = []
    for text, page, section in blocks:
        for start in range(0,len(text),5000):
            result.append(Evidence(id=f'{paper_id[:12]}-b{len(result)+1}', paper_id=paper_id, text=text[start:start+5000], page=page+1 if isinstance(page,int) else None, section=section))
    return result
