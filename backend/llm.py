import json
import os
import time
import logging
import httpx
from pydantic import ValidationError
from . import db
from .prompts import PROMPTS, VERSION

class ProviderError(RuntimeError):
    pass

logger = logging.getLogger(__name__)

def validation_details(error):
    # Never log raw model output, paper text, credentials or Pydantic input values.
    return [{'path':'.'.join(str(part) for part in item['loc']) or '$',
             'type':item['type'], 'message':item['msg']}
            for item in error.errors(include_input=False, include_url=False)[:12]]

def strict_schema(value):
    if isinstance(value,list):
        return [strict_schema(item) for item in value]
    if not isinstance(value,dict):
        return value
    result = {key:strict_schema(item) for key,item in value.items() if key != 'default'}
    if result.get('type') == 'object':
        result['required'] = list(result.get('properties',{}))
        result['additionalProperties'] = False
    return result

def call(stage, data, schema, job_id):
    model = os.getenv('LLM_MODEL','')
    base = os.getenv('LLM_BASE_URL','').rstrip('/')
    thinking = os.getenv('LLM_THINKING', '').strip()
    if thinking not in ('', 'enabled', 'disabled'):
        raise ProviderError('LLM_THINKING 必须为空、enabled 或 disabled。')
    max_tokens = int(os.getenv('LLM_MAX_OUTPUT_TOKENS', '10000'))
    key = db.digest({'stage':stage,'data':data,'schema':schema.model_json_schema(),'prompt':PROMPTS[stage], 'version':VERSION,'model':model,'base':base,'temperature':0,'format':os.getenv('LLM_JSON_SCHEMA'),'thinking':thinking,'max_tokens':max_tokens})
    cached = db.cache_get(key, job_id)
    if cached is not None:
        return schema.model_validate(cached)
    messages = [{'role':'system','content':PROMPTS[stage]+'\nJSON Schema: '+json.dumps(schema.model_json_schema(), ensure_ascii=False)}, {'role':'user','content':json.dumps(data, ensure_ascii=False)}]
    if sum(len(message['content']) for message in messages) > 180000:
        raise ProviderError('当前阶段输入过长，请减少本批论文数量或使用较短论文；不会静默截断证据。')
    for attempt in range(3):
        with db.connection() as conn:
            row = conn.execute('SELECT calls FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row or row['calls'] >= int(os.getenv('LLM_MAX_CALLS_PER_JOB','100')):
                raise ProviderError('本次任务已达到模型调用上限，请检查输入或提高服务端限额。')
            conn.execute('UPDATE jobs SET calls=calls+1 WHERE id=?', (job_id,))
        fmt = {'type':'json_object'}
        if os.getenv('LLM_JSON_SCHEMA','false').lower() == 'true':
            fmt = {'type':'json_schema','json_schema':{'name':stage,'strict':True,'schema':strict_schema(schema.model_json_schema())}}
        try:
            payload = {'model':model,'messages':messages,'temperature':0,'response_format':fmt,'max_tokens':max_tokens}
            if thinking:
                payload['thinking'] = {'type':thinking}
            with httpx.Client(timeout=180) as client:
                response = client.post(base+'/chat/completions', headers={'Authorization':'Bearer '+os.getenv('LLM_API_KEY','')}, json=payload)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
            if not response.is_success:
                raise ProviderError(f'模型服务返回 HTTP {response.status_code}，请检查密钥、模型名称或服务额度。')
            body = response.json()
            usage = body.get('usage', {})
            with db.connection() as conn:
                conn.execute('UPDATE jobs SET input_tokens=input_tokens+?, output_tokens=output_tokens+? WHERE id=?', (usage.get('prompt_tokens',0),usage.get('completion_tokens',0),job_id))
            choice = body['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise ProviderError('模型输出达到长度上限，未接受不完整 JSON。请提高 LLM_MAX_OUTPUT_TOKENS，或对支持的模型设置 LLM_THINKING=disabled 后重试。')
            content = choice['message']['content']
            parsed = schema.model_validate_json(content, strict=True)
            db.cache_put(key, parsed.model_dump())
            return parsed
        except ValidationError as error:
            details = validation_details(error)
            logger.warning('Structured output rejected stage=%s attempt=%s errors=%s', stage, attempt+1, json.dumps(details, ensure_ascii=False))
            if attempt < 2:
                # Repair the actual rejected object, with precise paths and types.
                # Keep only the latest repair pair, so retries cannot grow indefinitely.
                messages[2:] = [
                    {'role':'assistant','content':content},
                    {'role':'user','content':'上一个 JSON 未通过结构校验。仅修复下面列出的字段格式，保留原有证据和事实，不补编缺失信息。严格按 schema 输出完整 JSON。只有允许 null 的字段可以为 null；字符串缺失用空字符串，数组缺失用空数组。校验错误：'+json.dumps(details,ensure_ascii=False)}]
                continue
            fields = ', '.join(item['path'] for item in details[:3])
            raise ProviderError(f'模型输出未通过结构校验（{stage}: {fields}），两次定向修复仍未成功；已保留成功阶段，可重试。') from None
        except (KeyError, ValueError, TypeError):
            if attempt < 2:
                messages[2:] = [{'role':'user','content':'接口上次未返回有效 JSON 对象。请仅输出严格符合 schema 的完整 JSON。'}]
                continue
            raise ProviderError(f'模型响应格式无效（{stage}），已保留成功阶段，可重试。') from None
        except httpx.HTTPError:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise ProviderError('模型服务连接超时或不可用，可稍后重试。') from None
    raise ProviderError('模型服务重试次数已耗尽。')
