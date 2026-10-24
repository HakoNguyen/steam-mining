"""
Bản OpenRouter của llm.py (mặc định DeepSeek V4 Flash, credit HUYNH nạp): cùng công cụ (tools.py), cùng prompt, cùng kết
quả trả về {answer, trace, usage, stop_reason} như bản Claude/Gemini. Chọn bằng COPILOT_PROVIDER=openrouter trong .env.

OpenRouter dùng chuẩn API của OpenAI (/chat/completions + tool_calls) nên gọi thẳng bằng requests, không cần SDK.
Cần OPENROUTER_API_KEY trong .env; mô hình: COPILOT_OPENROUTER_MODEL (mặc định deepseek/deepseek-v4-flash,
~0,0015 USD mỗi câu hỏi).

stop_reason: stop | max_tokens | no_answer (hết vòng công cụ) | rate_limit | out_of_credit | refusal | cancelled | error;
error_code khi stop_reason = error: auth | network | server | unexpected (giao diện dịch sang đúng ngôn ngữ).
"""
import json
import logging
from pathlib import Path

import requests
from anthropic import beta_tool

from copilot import tools

log = logging.getLogger(__name__)
URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = tools.ENV.get("COPILOT_OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
SYSTEM = (Path(__file__).parent / "prompts" / "market_assistant.md").read_text(encoding="utf-8")
MAX_ROUNDS = 5          # số vòng gọi công cụ tối đa cho 1 câu hỏi (mỗi vòng = 1 request tính tiền)
TIMEOUT = (10, 60)      # (kết nối, chờ trả lời) giây cho mỗi request
TOOL_FUNCS = {fn.__name__: fn for fn in tools.TOOLS}
# Mô tả công cụ dạng JSON Schema lấy từ chữ ký + docstring của HUYNH (dùng chung bộ sinh schema với bản Claude)
TOOLS = [{"type": "function", "function": {"name": d["name"], "description": d["description"],
                                           "parameters": d["input_schema"]}}
         for d in (beta_tool(fn).to_dict() for fn in tools.TOOLS)]


class _Stop(Exception):
    """Lỗi đã biết từ OpenRouter: dừng câu hỏi và trả thông báo thân thiện."""
    def __init__(self, message, stop_reason, error_code=None):
        super().__init__(message)
        self.stop_reason, self.error_code = stop_reason, error_code


def _post(payload):
    try:
        r = requests.post(URL, timeout=TIMEOUT, json=payload, headers={
            "Authorization": f"Bearer {tools.ENV.get('OPENROUTER_API_KEY', '')}",
            "X-Title": "Steam Market Copilot",
        })
    except (requests.Timeout, requests.ConnectionError) as e:
        raise _Stop("Mất kết nối tới dịch vụ AI hoặc dịch vụ không phản hồi. Vui lòng thử lại.", "error", "network") from e
    if r.status_code == 401:
        raise _Stop("Khóa OpenRouter không hợp lệ hoặc đã hết hạn (OPENROUTER_API_KEY trong .env).", "error", "auth")
    if r.status_code == 402:
        raise _Stop("Tài khoản OpenRouter đã hết credit.", "out_of_credit")
    if r.status_code == 429:
        raise _Stop("Copilot đang quá tải, vui lòng thử lại sau ít phút.", "rate_limit")
    if r.status_code >= 400:
        log.error("OpenRouter %s: %s", r.status_code, r.text[:500])
        raise _Stop(f"Dịch vụ AI đang lỗi ({r.status_code}). Vui lòng thử lại.", "error", "server")
    data = r.json()
    if "error" in data:  # OpenRouter đôi khi trả 200 kèm lỗi của nhà cung cấp mô hình
        log.error("OpenRouter error body: %s", data["error"])
        raise _Stop("Dịch vụ AI đang lỗi. Vui lòng thử lại.", "error", "server")
    return data


def _run_tool(call):
    """Chạy 1 tool_call của mô hình. Lỗi (tên tag sai, SQL hỏng...) trả về cho mô hình tự sửa, không làm hỏng câu trả lời."""
    name = call["function"]["name"]
    try:
        args = json.loads(call["function"].get("arguments") or "{}")
        if name not in TOOL_FUNCS:
            raise ValueError(f"Không có công cụ tên '{name}'. Các công cụ: {', '.join(TOOL_FUNCS)}.")
        return TOOL_FUNCS[name](**args)
    except Exception as e:  # noqa: BLE001 - lỗi nào cũng báo lại cho mô hình
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def ask(question, history=(), cancel=None):
    """history: các lượt trước dạng [{"role": "user"|"assistant", "content": str}], cũ trước mới sau.
    cancel: threading.Event; khi được set thì dừng trước request tiếp theo (giao diện bấm Dừng hoặc quá giờ)."""
    def cancelled():
        return cancel is not None and cancel.is_set()

    messages = [{"role": "system", "content": SYSTEM}, *history, {"role": "user", "content": question}]
    usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "requests": 0}

    def call(**extra):
        data = _post({"model": MODEL, "messages": messages, "tools": TOOLS, "max_tokens": 8000,
                      "usage": {"include": True}, **extra})
        u = data.get("usage") or {}
        usage["input_tokens"] += u.get("prompt_tokens", 0) or 0
        usage["output_tokens"] += u.get("completion_tokens", 0) or 0
        usage["cost_usd"] += u.get("cost", 0) or 0
        usage["requests"] += 1
        choice = data["choices"][0]
        return choice["message"], choice.get("finish_reason") or "stop"

    with tools.tracing() as trace:
        try:
            for _ in range(MAX_ROUNDS):
                if cancelled():
                    return _result("", trace, usage, "cancelled")
                message, finish = call(tool_choice="auto")
                if not message.get("tool_calls"):
                    break
                messages.append({"role": "assistant", "content": message.get("content") or "",
                                 "tool_calls": message["tool_calls"]})
                for tc in message["tool_calls"]:
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": _run_tool(tc)})
            else:
                # Hết vòng mà mô hình vẫn muốn tra tiếp: bắt nó kết luận từ những gì đã tra được
                if cancelled():
                    return _result("", trace, usage, "cancelled")
                messages.append({"role": "user", "content": "Hãy trả lời ngay bằng những gì đã tra được, "
                                 "nói rõ phần nào warehouse chưa có dữ liệu. Không gọi thêm công cụ."})
                message, finish = call(tool_choice="none")
        except _Stop as e:
            return _result(str(e), trace, usage, e.stop_reason, e.error_code)
        except Exception:  # noqa: BLE001 - không để lỗi bất ngờ làm hỏng trang
            log.exception("Copilot (OpenRouter) failed")
            return _result("Copilot gặp lỗi không mong muốn. Vui lòng thử lại.", trace, usage, "error", "unexpected")

    log.info("copilot usage model=%s %s finish=%s", MODEL, usage, finish)
    answer = (message.get("content") or "").strip()
    if finish == "content_filter":
        return _result("Xin lỗi, Copilot không thể trả lời câu hỏi này.", trace, usage, "refusal")
    if not answer:
        return _result("Copilot đã tra cứu nhưng chưa đưa ra được kết luận. Hãy hỏi hẹp hơn hoặc thử câu hỏi mẫu.",
                       trace, usage, "no_answer")
    if finish == "length":  # giao diện tự gắn nhãn "bị cắt bớt"
        return _result(answer, trace, usage, "max_tokens")
    return _result(answer, trace, usage, "stop")


def _result(answer, trace, usage, stop_reason, error_code=None):
    return {"answer": answer, "trace": trace, "usage": usage, "stop_reason": stop_reason, "error_code": error_code}


if __name__ == "__main__":  # chạy thử: cd dashboard && python -m copilot.llm_openrouter "câu hỏi"
    import sys

    logging.basicConfig(level=logging.INFO)
    out = ask(" ".join(sys.argv[1:]) or "Thị trường game Roguelike đang thế nào?")
    print(out["answer"])
    print(json.dumps({"trace": out["trace"], "usage": out["usage"], "stop_reason": out["stop_reason"]},
                     ensure_ascii=False, indent=2, default=str))
