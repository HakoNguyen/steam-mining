"""
Lớp gọi AI của Copilot - chức năng 3: trợ lý khảo sát thị trường. Đổi nhà cung cấp AI chỉ cần sửa file này;
công cụ tra cứu warehouse nằm ở tools.py.

Giao diện gọi:
    from copilot.llm import ask
    result = ask("Combo tag nào được khen nhiều mà ít đối thủ?", history=[{"role": "user", "content": "..."},
                                                                       {"role": "assistant", "content": "..."}])
    result["answer"]   # Markdown tiếng Việt
    result["trace"]    # [{tool, args, sql, n_rows | error}] cho mục "Copilot đã tra cứu gì"
    result["usage"]    # token đã dùng (cache_read_input_tokens > 0 từ lần gọi thứ 2 nghĩa là cache hoạt động)

Cần ANTHROPIC_API_KEY trong môi trường hoặc trong .env ở thư mục gốc dự án.
"""
import logging
import os
from pathlib import Path

import anthropic
from anthropic import beta_tool

from copilot import tools

log = logging.getLogger(__name__)
MODEL = tools.ENV.get("COPILOT_MODEL", "claude-opus-5-5")
EFFORT = tools.ENV.get("COPILOT_EFFORT", "medium")  # hỏi đáp có công cụ: medium đủ; tăng lên high nếu trả lời hời hợt
SYSTEM = (Path(__file__).parent / "prompts" / "market_assistant.md").read_text(encoding="utf-8")
TOOLS = [beta_tool(fn) for fn in tools.TOOLS]
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

if tools.ENV.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = tools.ENV["ANTHROPIC_API_KEY"]


def ask(question, history=()):
    """history: các lượt trước dạng [{"role": "user"|"assistant", "content": str}], cũ trước mới sau."""
    usage = dict.fromkeys(USAGE_FIELDS, 0)
    with tools.tracing() as trace:
        try:
            runner = anthropic.Anthropic().beta.messages.tool_runner(
                model=MODEL,
                max_tokens=16000,
                # system + tools không đổi giữa các lần gọi -> cache; không chèn ngày giờ vào đây kẻo mất cache
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=TOOLS,
                messages=[*history, {"role": "user", "content": question}],
                output_config={"effort": EFFORT},
                # bị bộ lọc an toàn từ chối nhầm thì máy chủ tự chạy lại bằng mô hình dự phòng
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            last = None
            for message in runner:
                last = message
                for k in USAGE_FIELDS:
                    usage[k] += getattr(message.usage, k, None) or 0
        except anthropic.AuthenticationError:
            return _result("Khóa API của Copilot không hợp lệ (ANTHROPIC_API_KEY).", trace, usage, "error")
        except TypeError as e:  # SDK báo thiếu thông tin xác thực bằng TypeError trước khi gửi request
            if "authentication" not in str(e):
                raise
            return _result("Chưa cấu hình khóa API cho Copilot (ANTHROPIC_API_KEY trong .env).", trace, usage, "error")
        except anthropic.RateLimitError:
            return _result("Copilot đang quá tải, vui lòng thử lại sau ít phút.", trace, usage, "error")
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            log.exception("Copilot API error")
            return _result(f"Không gọi được dịch vụ AI ({type(e).__name__}). Vui lòng thử lại.", trace, usage, "error")

    log.info("copilot usage model=%s %s", last.model, usage)
    if last.stop_reason == "refusal":
        return _result("Xin lỗi, Copilot không thể trả lời câu hỏi này.", trace, usage, last.stop_reason)
    answer = "".join(b.text for b in last.content if b.type == "text")
    if last.stop_reason == "max_tokens":
        answer += "\n\n_(Câu trả lời bị cắt vì quá dài - hãy hỏi hẹp hơn.)_"
    return _result(answer, trace, usage, last.stop_reason)


def _result(answer, trace, usage, stop_reason):
    return {"answer": answer, "trace": trace, "usage": usage, "stop_reason": stop_reason}


if __name__ == "__main__":  # chạy thử: cd dashboard && python -m copilot.llm "câu hỏi"
    import json
    import sys

    logging.basicConfig(level=logging.INFO)
    out = ask(" ".join(sys.argv[1:]) or "Thị trường game Roguelike đang thế nào?")
    print(out["answer"])
    print(json.dumps({"trace": out["trace"], "usage": out["usage"]}, ensure_ascii=False, indent=2, default=str))
