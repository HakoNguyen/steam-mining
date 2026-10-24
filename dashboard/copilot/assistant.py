"""Điểm vào duy nhất cho giao diện: from copilot.assistant import ask, PROVIDERS, DEFAULT, configured, key_status, model.

Có 3 nhà cung cấp AI, cùng công cụ (tools.py), cùng prompt, cùng kết quả {answer, trace, usage, stop_reason, error_code}:
gemini (llm_gemini.py, gói miễn phí), openrouter (llm_openrouter.py, DeepSeek V4, trả phí theo credit), anthropic
(llm.py, Claude). Giao diện chọn cho từng câu hỏi (ask(..., provider=...)); COPILOT_PROVIDER trong .env là lựa chọn
mặc định. Module của mỗi nhà cung cấp chỉ được import khi dùng tới, nên thiếu thư viện của một bên không làm hỏng bên khác.
"""
import importlib
import inspect
from functools import lru_cache

import requests

from copilot import tools

PROVIDERS = {  # thứ tự hiển thị trên giao diện
    "gemini": {"module": "copilot.llm_gemini", "key": "GEMINI_API_KEY", "name": "Gemini", "paid": False},
    "openrouter": {"module": "copilot.llm_openrouter", "key": "OPENROUTER_API_KEY", "name": "DeepSeek", "paid": True},
    "anthropic": {"module": "copilot.llm", "key": "ANTHROPIC_API_KEY", "name": "Claude", "paid": True},
}
# Tên stop_reason riêng của từng nhà cung cấp -> bộ chung mà giao diện hiểu
_STOP_REASONS = {"end_turn": "stop", "pause_turn": "stop", "tool_use": "no_answer"}


def configured():
    """Các nhà cung cấp đã có khóa API trong .env (theo thứ tự hiển thị)."""
    return [p for p, cfg in PROVIDERS.items() if tools.ENV.get(cfg["key"])]


_wanted = (tools.ENV.get("COPILOT_PROVIDER") or "").strip().lower()
DEFAULT = _wanted if _wanted in configured() else (configured() or ["gemini"])[0]


@lru_cache(maxsize=None)
def _load(provider):
    return importlib.import_module(PROVIDERS[provider]["module"])


def model(provider):
    """Tên mô hình đang cấu hình cho nhà cung cấp (vd. gemini-flash-lite-latest, deepseek/deepseek-v4-flash)."""
    return _load(provider).MODEL


def key_status(provider):
    """'ok' | 'missing' | 'invalid' (khóa sai / hết hạn) | 'unknown' (không kiểm tra được).
    OpenRouter có endpoint kiểm tra khóa miễn phí; các bên khác chỉ kiểm tra khóa có trong .env hay không."""
    key = tools.ENV.get(PROVIDERS[provider]["key"])
    if not key:
        return "missing"
    if provider != "openrouter":
        return "ok"
    try:
        r = requests.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"}, timeout=10)
    except requests.RequestException:
        return "unknown"
    return "ok" if r.status_code == 200 else "invalid" if r.status_code in (401, 403) else "unknown"


def ask(question, history=(), cancel=None, provider=None):
    """Hỏi Copilot bằng nhà cung cấp đã chọn (mặc định DEFAULT). cancel (threading.Event) chỉ truyền cho bản hỗ trợ dừng."""
    fn = _load(provider or DEFAULT).ask
    res = fn(question, history, cancel=cancel) if "cancel" in inspect.signature(fn).parameters else fn(question, history)
    res["stop_reason"] = _STOP_REASONS.get(res.get("stop_reason"), res.get("stop_reason"))
    res.setdefault("error_code", None)
    return res
