# -*- coding: utf-8 -*-
"""Optional machine-translation fallback for strings the dictionaries miss.

Only standard library is used (urllib), so the add-on keeps working without any
extra pip package. The endpoint is any OpenAI-compatible ``/chat/completions``
API (DeepSeek by default).

The API key is read from the add-on preferences, or from the environment
variable ``USER_TRANSLATE_API_KEY`` when the preference is empty.
"""

import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BATCH = 40
DEFAULT_TIMEOUT = 60

SYSTEM_PROMPT = (
    "你是 Blender 插件界面的翻译助手。用户会给你一个 JSON 数组，里面是英文界面文本。\n"
    "请把每一项翻译成简体中文，并**只输出一个 JSON 对象**，键是原文，值是译文，不要任何解释。\n"
    "规则：\n"
    "1. 保留占位符（%s、%d、{name}）与它们的位置；\n"
    "2. 专有名词保持原文：UV、FBX、glTF、Rigify、Blender、OpenAI、mmd、API 等；\n"
    "3. 界面用语简洁，不要加句号；\n"
    "4. 原文如果已经是中文，原样返回。"
)


class MTError(Exception):
    pass


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #

def api_config():
    from .utils import preference

    prefs = preference()
    base = (getattr(prefs, "mt_api_base", "") or DEFAULT_BASE).strip().rstrip("/")
    model = (getattr(prefs, "mt_model", "") or DEFAULT_MODEL).strip()
    key = (getattr(prefs, "mt_api_key", "") or "").strip()
    if not key:
        key = os.environ.get("USER_TRANSLATE_API_KEY", "").strip()
    timeout = int(getattr(prefs, "mt_timeout", DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT)
    batch = int(getattr(prefs, "mt_batch", DEFAULT_BATCH) or DEFAULT_BATCH)
    return base, model, key, timeout, max(5, min(80, batch))


# --------------------------------------------------------------------------- #
# request / parse
# --------------------------------------------------------------------------- #

def _request_chat(base, model, key, timeout, strings):
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(strings, ensure_ascii=False)},
        ],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base + "/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        if exc.code == 401:
            raise MTError("API Key 无效（401），检查 Key 是否复制完整")
        if exc.code == 402:
            raise MTError("账户余额不足（402），去服务商平台充值")
        if exc.code == 429:
            raise MTError("请求过于频繁（429），稍后再试或调小批大小")
        raise MTError("HTTP %s：%s" % (exc.code, detail or exc.reason))
    except urllib.error.URLError as exc:
        raise MTError("网络错误：%s（如在国内网络，可能需要代理）" % exc.reason)
    except Exception as exc:
        raise MTError("请求失败：%s" % exc)

    try:
        content = json.loads(body)["choices"][0]["message"]["content"]
    except Exception as exc:
        raise MTError("响应格式异常：%s" % exc)
    return content


def _parse_reply(content, wanted):
    """Best-effort extraction of {source: translation} from the model reply."""
    text = content.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()

    parsed = None
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
        except Exception:
            parsed = None

    result = {}
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if isinstance(key, str) and isinstance(value, str):
                result[key.strip()] = value.strip()
        if result:
            return result

    # fallback: "English <tab> 中文" lines, or "English" => "中文"
    for line in text.splitlines():
        line = line.strip().strip(",")
        if not line:
            continue
        for separator in ("\t", "||", " => ", "->", "："):
            if separator in line:
                left, right = line.split(separator, 1)
                left = left.strip().strip('"').strip()
                right = right.strip().strip('"').strip()
                if left and right:
                    result[left] = right
                break
    return {k: v for k, v in result.items() if k in wanted and v}


def translate(strings, limit=None):
    """Translate a list of English strings. Returns {english: chinese}."""
    base, model, key, timeout, batch = api_config()
    if not key:
        raise MTError("没有 API Key：请在偏好设置里填写，或设置环境变量 USER_TRANSLATE_API_KEY")
    if not strings:
        return {}

    unique = []
    seen = set()
    for text in strings:
        if text not in seen:
            seen.add(text)
            unique.append(text)
    if limit:
        unique = unique[:limit]

    result = {}
    for index in range(0, len(unique), batch):
        chunk = unique[index:index + batch]
        reply = _request_chat(base, model, key, timeout, chunk)
        result.update(_parse_reply(reply, set(chunk)))
    return result
