"""
Bản Gemini của llm.py (dùng tạm khi chưa có khóa Claude): cùng công cụ (tools.py), cùng prompt, cùng kết quả trả về
{answer, trace, usage, stop_reason} nên giao diện không cần biết đang dùng nhà cung cấp nào. Chọn bằng
COPILOT_PROVIDER=gemini trong .env (xem copilot/assistant.py).

stop_reason: stop | max_tokens | no_answer | rate_limit | refusal | cancelled | error (giống llm_openrouter.py);
error_code khi stop_reason = error: auth | network | server | unexpected (giao diện dịch sang đúng ngôn ngữ).
Cần GEMINI_API_KEY trong .env. Mô hình: COPILOT_GEMINI_MODEL. Mặc định gemini-flash-lite-latest: ở gói miễn phí
(20/10/2026) bản Flash-Lite trả lời ~1 giây, bản Flash thường quá tải (504), bản Pro không được dùng (429).
"""
import functools
import json
import logging
from contextvars import ContextVar
from pathlib import Path

from google import genai
from google.genai import errors, types

from copilot import tools

log = logging.getLogger(__name__)
MODEL = tools.ENV.get("COPILOT_GEMINI_MODEL", "gemini-flash-lite-latest")
# Mỗi lượt gọi tối đa 30 giây, chỉ thử lại lỗi máy chủ (không thử lại 429: thử lại chỉ tốn thêm lượt miễn phí)
HTTP = types.HttpOptions(timeout=30_000, retry_options=types.HttpRetryOptions(
    attempts=2, http_status_codes=[500, 502, 503, 504]))
SYSTEM = (Path(__file__).parent / "prompts" / "market_assistant.md").read_text(encoding="utf-8")
MAX_TOOL_CALLS = 5  # mỗi vòng là 1 request: gói miễn phí chỉ ~15 request/phút
REFUSALS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}
_cancel = ContextVar("copilot_cancel", default=None)  # threading.Event của câu hỏi đang chạy (người dùng bấm Dừng)


def _safe(fn):
    """Công cụ lỗi (tên tag sai, SQL hỏng...) thì trả lỗi cho AI tự sửa và gọi lại, không làm hỏng cả câu trả lời
    (giống is_error của bản Claude). functools.wraps giữ chữ ký + docstring để SDK sinh mô tả công cụ."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if (cancel := _cancel.get()) is not None and cancel.is_set():
            # SDK tự gọi công cụ nên không chen ngang được giữa các vòng: báo mô hình dừng tra cứu
            return json.dumps({"error": "Người dùng đã dừng câu hỏi. Không gọi thêm công cụ."}, ensure_ascii=False)
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - lỗi nào cũng báo lại cho mô hình
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    return wrapper


TOOLS = [_safe(fn) for fn in tools.TOOLS]


def _history(history):
    role = {"user": "user", "assistant": "model"}
    return [types.Content(role=role[h["role"]], parts=[types.Part(text=h["content"])]) for h in history]


def ask(question, history=(), cancel=None):
    """history: các lượt trước dạng [{"role": "user"|"assistant", "content": str}], cũ trước mới sau.
    cancel: threading.Event; khi được set thì ngừng gọi công cụ (giao diện bấm Dừng hoặc quá giờ)."""
    _cancel.set(cancel)
    # Giữ client trong biến suốt lượt hỏi: client tạm bị dọn giữa chừng sẽ đóng kết nối trước lượt gọi thứ 2
    client = genai.Client(api_key=tools.ENV.get("GEMINI_API_KEY"), http_options=HTTP)
    chat = client.chats.create(
        model=MODEL,
        history=_history(history),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            tools=TOOLS,  # SDK tự gọi hàm Python rồi gửi kết quả lại cho mô hình
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=MAX_TOOL_CALLS),
        ),
    )
    with tools.tracing() as trace:
        try:
            response = chat.send_message(question)
        except errors.ClientError as e:
            if e.code == 429:
                return _result("Copilot đang quá tải (hết lượt gọi miễn phí của Gemini), vui lòng thử lại sau ít phút.",
                               trace, {}, "rate_limit")
            if e.code in (400, 401, 403) and "key" in str(e).lower():
                return _result("Khóa API Gemini không hợp lệ (GEMINI_API_KEY trong .env).", trace, {}, "error", "auth")
            log.exception("Gemini client error")
            return _result(f"Không gọi được Gemini (lỗi {e.code}). Vui lòng thử lại.", trace, {}, "error", "unexpected")
        except (errors.ServerError, errors.APIError) as e:
            log.exception("Gemini server error")
            return _result(f"Dịch vụ Gemini đang lỗi ({e.code}). Vui lòng thử lại.", trace, {}, "error", "server")
        except Exception:  # noqa: BLE001 - mất mạng (httpx), công cụ lạ... không để lỗi làm hỏng trang
            log.exception("Copilot (Gemini) failed")
            return _result("Mất kết nối tới Gemini hoặc có lỗi không mong muốn. Vui lòng thử lại.", trace, {}, "error",
                           "network")

    meta = response.usage_metadata
    usage = {"input_tokens": getattr(meta, "prompt_token_count", 0) or 0,
             "output_tokens": getattr(meta, "candidates_token_count", 0) or 0,
             "thinking_tokens": getattr(meta, "thoughts_token_count", 0) or 0,
             "cache_read_input_tokens": getattr(meta, "cached_content_token_count", 0) or 0}
    candidate = (response.candidates or [None])[0]
    reason = getattr(getattr(candidate, "finish_reason", None), "name", None) or "STOP"
    log.info("copilot usage model=%s %s finish=%s", response.model_version, usage, reason)

    if reason in REFUSALS or candidate is None:
        return _result("Xin lỗi, Copilot không thể trả lời câu hỏi này.", trace, usage, "refusal")
    answer = response.text or ""
    if cancel is not None and cancel.is_set():
        return _result("", trace, usage, "cancelled")
    if not answer.strip():
        return _result("Copilot đã tra cứu nhưng chưa đưa ra được kết luận. Hãy hỏi hẹp hơn hoặc thử câu hỏi mẫu.",
                       trace, usage, "no_answer")
    return _result(answer, trace, usage, "max_tokens" if reason == "MAX_TOKENS" else "stop")


def _result(answer, trace, usage, stop_reason, error_code=None):
    return {"answer": answer, "trace": trace, "usage": usage, "stop_reason": stop_reason, "error_code": error_code}


if __name__ == "__main__":  # chạy thử: cd dashboard && python -m copilot.llm_gemini "câu hỏi"
    import sys

    logging.basicConfig(level=logging.INFO)
    out = ask(" ".join(sys.argv[1:]) or "Thị trường game Roguelike đang thế nào?")
    print(out["answer"])
    print(json.dumps({"trace": out["trace"], "usage": out["usage"], "stop_reason": out["stop_reason"]},
                     ensure_ascii=False, indent=2, default=str))
