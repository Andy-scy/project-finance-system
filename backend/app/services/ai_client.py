"""AI 客户端：OpenAI 兼容 Chat Completions（智谱 GLM / OpenAI / DeepSeek 等通用）。

API Key 只在后端使用，绝不返回给前端。
"""
from __future__ import annotations

import json
import re

import httpx
from sqlalchemy.orm import Session

from .settings_svc import get_settings


class AIError(Exception):
    pass


def chat(db: Session, messages: list[dict], *, model: str | None = None,
         temperature: float = 0.1, max_tokens: int = 4096, timeout: float = 180.0) -> str:
    s = get_settings(db)
    key = s.get("ai_api_key") or ""
    base = (s.get("ai_base_url") or "").strip().rstrip("/")
    if not key:
        raise AIError("未配置 AI API Key，请先到「系统设置」填写并保存。")
    if not base:
        raise AIError("未配置 AI 接口地址（Base URL），请到「系统设置」填写。")
    url = f"{base}/chat/completions"
    payload = {
        "model": model or s.get("ai_model") or "glm-4.6",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as e:
        raise AIError(f"AI 接口请求超时：{e}") from e
    except httpx.HTTPError as e:
        raise AIError(f"无法连接 AI 接口：{e}") from e

    if resp.status_code in (401, 403):
        raise AIError(f"AI 接口鉴权失败（HTTP {resp.status_code}），请检查 API Key。")
    if resp.status_code == 404:
        raise AIError("AI 接口返回 404，请检查 Base URL 与模型名称是否正确。")
    if resp.status_code >= 400:
        try:
            err = resp.json().get("error", {})
            msg = err.get("message") if isinstance(err, dict) else str(err)
        except Exception:
            msg = resp.text[:300]
        raise AIError(f"AI 接口错误（HTTP {resp.status_code}）：{msg}")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"] or ""
    except Exception as e:
        raise AIError(f"AI 返回格式无法解析：{e}") from e


def extract_json(text: str) -> dict:
    """从模型输出中稳健提取 JSON（容忍 ```json 围栏、前后说明文字）。"""
    if not text:
        raise AIError("AI 未返回内容。")
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", t, flags=re.S)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    # 兜底：取第一个 { 到与之配对的 }
    start = t.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(t)):
            if t[i] == "{":
                depth += 1
            elif t[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except json.JSONDecodeError:
                        break
    raise AIError("AI 输出中未找到有效 JSON，请重试或更换模型。")


def test_ai(db: Session) -> dict:
    s = get_settings(db)
    reply = chat(
        db,
        [{"role": "user", "content": "请只回复两个字：正常"}],
        max_tokens=16, temperature=0, timeout=30,
    )
    return {"ok": True, "model": s.get("ai_model"), "reply": reply.strip()[:50]}
