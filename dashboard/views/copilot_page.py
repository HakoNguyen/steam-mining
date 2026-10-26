"""Trang Copilot: chat hỏi đáp thị trường. Mỗi câu trả lời kèm phần "Copilot đã tra cứu gì" (công cụ, tham số, SQL,
số dòng) để người xem kiểm tra được mọi con số. Backend: copilot.assistant.ask (Gemini / OpenRouter / Claude theo .env).

Câu hỏi đang chạy được giữ trong session_state (cp_job: future + cờ hủy + giờ bắt đầu). Nhờ vậy bấm nút khác hay
đổi ngôn ngữ giữa chừng thì trang chỉ chạy lại rồi chờ tiếp, không mất câu trả lời; chỉ nút Dừng mới hủy câu hỏi.
ask() chạy trong luồng riêng, trang kiểm tra mỗi 0,5 giây để hiện số giây đã chờ và bỏ chờ sau TIMEOUT_S giây.
(File tên copilot_page.py, không phải copilot.py, để không che mất gói copilot/ khi import.)"""
import json
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import streamlit as st

from lib import fmt
from lib.i18n import STR, t
from lib.theme import palette

TIMEOUT_S = 90
COOLDOWN_S = 60       # khóa ô nhập sau khi dịch vụ AI báo quá tải
MAX_PER_MINUTE = 3    # 1 câu hỏi có thể tốn tới ~6 request tới dịch vụ AI
HISTORY_MSGS = 8      # số tin nhắn gần nhất gửi kèm làm ngữ cảnh
EXAMPLES = ["cp_ex_fps", "cp_ex_market", "cp_ex_price", "cp_ex_genre", "cp_ex_guard"]   # đã chạy thử tốt
MINING_EXAMPLES = ["cp_ex_combo", "cp_ex_similar"]                         # chỉ hiện khi đã có kết quả mining
KINDS = {"stop": "ok", "max_tokens": "ok", "no_answer": "no_answer", "rate_limit": "rate_limit",
         "out_of_credit": "out_of_credit", "refusal": "refusal", "cancelled": "stopped"}
ERRORS = {"auth": "cp_err_auth", "network": "cp_err_network", "server": "cp_err_server", "unexpected": "cp_err_unexpected"}
_CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.S)
BG = {"light": "#f9f9f7", "dark": "#141413"}  # backgroundColor trong .streamlit/config.toml

st.title(t("nav_copilot"))
st.caption(t("cp_caption"))

try:
    from copilot import tools
    from copilot.assistant import DEFAULT, PROVIDERS, ask, configured, key_status, model
except Exception as e:  # thiếu thư viện hoặc cấu hình hỏng
    st.error(t("cp_unavailable", e=type(e).__name__))
    st.stop()

ss = st.session_state
ss.setdefault("cp_msgs", [])
ss.setdefault("cp_times", [])
AVAILABLE = configured()  # nhà cung cấp đã có khóa trong .env
if ss.get("cp_provider") not in AVAILABLE:
    ss.cp_provider = DEFAULT if DEFAULT in AVAILABLE else (AVAILABLE or [DEFAULT])[0]


@st.cache_data(ttl=600, show_spinner=False)
def provider_status(provider, key_tail):
    """Khóa của nhà cung cấp còn dùng được không (key_tail: đổi khóa trong .env thì kiểm tra lại)."""
    return key_status(provider)


def model_name(provider):
    try:
        return model(provider).split("/")[-1]  # deepseek/deepseek-v4-flash -> deepseek-v4-flash
    except Exception:  # thiếu thư viện của nhà cung cấp này
        return None


def status_of(provider):
    key = tools.ENV.get(PROVIDERS[provider]["key"]) or ""
    return provider_status(provider, key[-6:]) if model_name(provider) else "unavailable"


def provider_label(provider):
    """Gemini · gemini-flash-lite-latest   /   DeepSeek · deepseek-v4-flash (kèm cảnh báo nếu khóa hỏng)"""
    label = f"{PROVIDERS[provider]['name']} · {model_name(provider) or '?'}"
    status = status_of(provider)
    return label + (f" · {t('cp_key_expired')}" if status == "invalid" else
                    f" · {t('cp_provider_unavailable')}" if status == "unavailable" else "")


@st.cache_resource
def executor():
    return ThreadPoolExecutor(max_workers=4, thread_name_prefix="copilot")


@st.cache_data(ttl=60, show_spinner=False)
def readiness():
    """Kho dữ liệu có kết nối được không, kết quả mining đã có chưa (quyết định banner và câu hỏi mẫu)."""
    try:
        row = json.loads(tools.run_readonly_sql(
            "SELECT to_regclass('mining.tag_rules') IS NOT NULL AS rules, "
            "to_regclass('mining.game_clusters') IS NOT NULL AS clusters"))[0]
        return {"db": True, "mining": bool(row["rules"] and row["clusters"])}
    except Exception:
        return {"db": False, "mining": False}


def safe_md(text):
    """$ bị Streamlit hiểu là công thức LaTeX, ~ là gạch ngang: thoát cả hai (trừ trong code và chỗ đã thoát sẵn)."""
    parts = _CODE.split(text)
    for i in range(0, len(parts), 2):  # phần chẵn nằm ngoài code
        parts[i] = re.sub(r"(?<!\\)([$~])", r"\\\1", parts[i])
    return "".join(parts)


def tool_label(name):
    return t(f"cp_tool_{name}") if f"cp_tool_{name}" in STR else name


def ok_tools(trace):
    """Công cụ có ít nhất 1 truy vấn thành công (huy hiệu nguồn không ghi công cụ chỉ toàn lỗi)."""
    return list(dict.fromkeys(e["tool"] for e in trace if "n_rows" in e and not e.get("error")))


def blocked_until():
    """Thời điểm được hỏi tiếp: sau khi hết khóa vì quá tải, và khi cửa sổ 60 giây còn chỗ (MAX_PER_MINUTE)."""
    now = time.time()
    ss.cp_times = [x for x in ss.cp_times if now - x < 60]
    throttle = ss.cp_times[0] + 60 if len(ss.cp_times) >= MAX_PER_MINUTE else 0
    return max(ss.get("cp_cooldown_until", 0), throttle)


def ask_pending(question):
    ss.cp_pending = question


def pick_example():
    if ss.get("cp_pill"):
        ss.cp_pending = t(ss.cp_pill)
        ss.cp_pill = None


def new_chat():
    ss.cp_msgs = []


def stop_job():
    job = ss.pop("cp_job", None)
    if job:
        job["cancel"].set()  # backend ngừng gọi AI ở bước tiếp theo
        ss.cp_msgs.append({"role": "assistant", "content": "", "kind": "stopped", "trace": []})


def history():
    """Các cặp hỏi-đáp thành công gần nhất, dạng {role, content} cho ask()."""
    pairs = []
    for q, a in zip(ss.cp_msgs, ss.cp_msgs[1:]):
        if q["role"] == "user" and a["role"] == "assistant" and a["kind"] == "ok":
            pairs += [{"role": "user", "content": q["content"]}, {"role": "assistant", "content": a["content"]}]
    return pairs[-HISTORY_MSGS:]


def start_job(question):
    past = history()
    ss.cp_times.append(time.time())
    ss.cp_msgs.append({"role": "user", "content": question})
    cancel = threading.Event()
    provider = ss.cp_provider
    ss.cp_job = {"future": executor().submit(ask, question + t("cp_answer_lang"), past, cancel, provider),
                 "cancel": cancel, "start": time.time(), "provider": provider,
                 "model": f"{PROVIDERS[provider]['name']} · {model_name(provider)}"}
    st.rerun()  # lần chạy sau vẽ câu hỏi + trạng thái chờ, ô nhập và các nút bị khóa


def finish_job(job):
    """Lấy kết quả (hoặc quá giờ) của câu hỏi đang chạy, ghi vào hội thoại."""
    secs = time.time() - job["start"]
    if not job["future"].done():
        job["cancel"].set()
        msg = {"kind": "timeout", "content": "", "trace": []}
    else:
        try:
            res = job["future"].result()
            msg = {"kind": KINDS.get(res["stop_reason"], "error"), "content": res.get("answer", ""),
                   "trace": res.get("trace", []), "error_code": res.get("error_code"),
                   "truncated": res["stop_reason"] == "max_tokens", "usage": res.get("usage", {})}
        except Exception:  # ask() đã tự bắt lỗi; đây là lưới an toàn cuối
            msg = {"kind": "error", "content": "", "trace": [], "error_code": "unexpected"}
    if msg["kind"] == "rate_limit":
        ss.cp_cooldown_until = time.time() + COOLDOWN_S
    ss.pop("cp_job", None)
    # .get: câu hỏi bắt đầu trước khi code được nạp lại (bản cũ chưa lưu provider/model) vẫn lấy được kết quả
    ss.cp_msgs.append({"role": "assistant", "secs": secs, "provider": job.get("provider", ss.cp_provider),
                       "model": job.get("model"), **msg})


def status_text(m):
    """Thông báo cho các câu trả lời không thành công (dùng chung cho màn hình và file tải về)."""
    kind, n = m["kind"], len(m.get("trace", []))
    return {
        "no_answer": t("cp_no_answer", n=n) if n else t("cp_no_answer_empty"),
        "rate_limit": t("cp_rate_limit"),
        "out_of_credit": t("cp_out_of_credit"),
        "refusal": t("cp_refusal"),
        "timeout": t("cp_timeout", s=TIMEOUT_S),
        "stopped": t("cp_stopped"),
    }.get(kind) or t(ERRORS.get(m.get("error_code"), "cp_err_generic"),
                     var=PROVIDERS.get(m.get("provider"), PROVIDERS[ss.cp_provider])["key"])


def transcript():
    lines = [f"# Steam Market Copilot · {datetime.now().strftime(t('cp_datefmt'))}", ""]
    for m in ss.cp_msgs:
        if m["role"] == "user":
            lines += [f"## {t('cp_you')}", m["content"], ""]
            continue
        lines += [f"## Copilot ({m.get('model', '')})", m["content"] if m["kind"] == "ok" else f"_{status_text(m)}_", ""]
        for i, e in enumerate(m.get("trace", []), 1):
            result = t("cp_rows", n=e["n_rows"]) if "n_rows" in e else e.get("error", "")
            lines += [f"**{i}. {tool_label(e['tool'])}** (`{e['tool']}`) "
                      f"`{json.dumps(e.get('args', {}), ensure_ascii=False)}` → {result}",
                      "```sql", e.get("sql", ""), "```"]
        lines.append("")
    return "\n".join(lines)


def evidence(trace, secs, expanded):
    """Phần "Copilot đã tra cứu gì": mỗi truy vấn đã chạy với công cụ, tham số, SQL và số dòng (hoặc lỗi)."""
    errors = [e for e in trace if e.get("error")]
    s = fmt.num(secs, 1)  # các nhãn này đã có sẵn chữ "giây" / "s"
    if not trace:
        label, state = t("cp_no_lookup", s=s), "complete"
    elif errors:
        label, state = t("cp_lookups_err", n=len(trace), e=len(errors), s=s), "error"
    else:
        label, state = t("cp_lookups", n=len(trace), s=s), "complete"
    with st.status(label, state=state, expanded=bool(trace) and (expanded or bool(errors))):
        for i, e in enumerate(trace, 1):
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"**{i}. {tool_label(e['tool'])}** · `{e['tool']}`")
                if e.get("error"):
                    st.badge(t("cp_error"), color="red")
                elif "n_rows" in e:
                    st.badge(t("cp_rows", n=e["n_rows"]), color="green" if e["n_rows"] else "orange")
            args = {k: v for k, v in (e.get("args") or {}).items() if v is not None}
            st.caption(", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items())
                       if args else t("cp_baseline"))
            sql = e.get("sql", "")
            st.code(sql, language="sql", wrap_lines=True, height=min(22 * (sql.count("\n") + 2), 200))
            err = e.get("error")
            if err and "mining." in err and "does not exist" in err:
                st.warning(t("cp_trace_mining"), icon=":material/hourglass_empty:")
            elif err and "kết nối" in err:
                st.warning(t("cp_trace_db"), icon=":material/cloud_off:")
            elif err:
                st.code(err, language="text", wrap_lines=True)
        if trace:
            st.caption(t("cp_sql_note"))


def render_answer(m, question, last, locked):
    """1 tin nhắn của Copilot: phần tra cứu, rồi câu trả lời hoặc thông báo tương ứng."""
    trace, kind = m.get("trace", []), m["kind"]
    if trace or kind == "ok":
        evidence(trace, m.get("secs", 0), ss.get("cp_open", False))
    if kind == "ok":
        st.markdown(safe_md(m["content"]))
        with st.container(horizontal=True):
            for name in ok_tools(trace):
                st.badge(tool_label(name), color="blue", icon=":material/database:")
            st.badge(t("cp_seconds", s=fmt.num(m.get("secs", 0), 1)), color="gray", icon=":material/timer:")
            if m.get("model"):
                st.badge(m["model"], color="violet", icon=":material/smart_toy:")
            if m.get("truncated"):
                st.badge(t("cp_truncated"), color="gray")
    elif kind == "stopped":
        st.caption(status_text(m))
    elif kind in ("no_answer", "rate_limit", "refusal"):
        icon = {"no_answer": ":material/help:", "rate_limit": ":material/hourglass_top:", "refusal": ":material/block:"}
        st.warning(status_text(m), icon=icon[kind])
    else:  # error, timeout, out_of_credit
        st.error(status_text(m), icon=":material/error:")
    if last and kind != "ok" and question:
        st.button(t("cp_retry"), icon=":material/refresh:", on_click=ask_pending, args=(question,), disabled=locked)


@st.fragment(run_every=1)
def countdown(until):
    left = until - time.time()
    if left <= 0:
        st.rerun()  # hết giờ chờ: chạy lại cả trang để mở khóa (và gửi câu hỏi đang xếp hàng, nếu có)
    st.caption(t("cp_unlock", s=math.ceil(left)) + (" " + t("cp_queued") if ss.get("cp_pending") else ""))


def poll(job):
    """Chờ câu hỏi đang chạy, cập nhật số giây; nút Dừng hủy câu hỏi. Xong (hoặc quá giờ) thì ghi kết quả."""
    with st.chat_message("assistant"):
        status = st.status(t("cp_working", s=0), state="running")
        st.button(t("cp_stop"), icon=":material/stop_circle:", on_click=stop_job, key="cp_stop_btn")
        while not job["future"].done() and time.time() - job["start"] < TIMEOUT_S:
            elapsed = int(time.time() - job["start"])
            status.update(label=t("cp_working_slow" if elapsed >= 15 else "cp_working", s=elapsed))
            time.sleep(0.5)
    finish_job(job)
    st.rerun()


# ---------------------------------------------------------------- đầu trang
ready = readiness()
job = ss.get("cp_job")
PROVIDER = ss.cp_provider
KEY_VAR = PROVIDERS[PROVIDER]["key"]
STATUS = status_of(PROVIDER) if AVAILABLE else "missing"
HAS_KEY = STATUS in ("ok", "unknown")
until = blocked_until()
locked = not HAS_KEY or not ready["db"] or job is not None   # khóa cứng: thiếu khóa API, mất DB, đang trả lời
waiting = time.time() < until                                   # khóa tạm: quá tải / hỏi quá nhanh
examples = EXAMPLES + (MINING_EXAMPLES if ready["mining"] else [])

# Ghim thanh công cụ dưới header (cao 3.75rem, đè lên vùng cuộn stMain): chat dài vẫn đổi model / hỏi mới được.
# Streamlit 1.66 gắn class key vào khối bên trong một stLayoutWrapper cao bằng nó, nên sticky phải đặt lên lớp bọc.
# Nền đặc theo màu nền của theme để tin nhắn cuộn bên dưới không lộ qua.
pal = palette()
st.markdown(f"""<style>
[data-testid="stLayoutWrapper"]:has(> .st-key-cp_toolbar) {{
  position: sticky; top: 3.75rem; z-index: 99; background: {BG[pal.mode]};
  padding: 0.5rem 0; border-bottom: 1px solid {pal.grid}; }}
</style>""", unsafe_allow_html=True)
with st.container(horizontal=True, vertical_alignment="center", key="cp_toolbar"):
    labels = {p: provider_label(p) for p in AVAILABLE or [PROVIDER]}  # tính sẵn theo ngôn ngữ của lần chạy này
    st.selectbox(t("cp_model_label"), list(labels), format_func=labels.get, key="cp_provider",
                 disabled=job is not None or len(AVAILABLE) < 2, label_visibility="collapsed", width=360,
                 help=t("cp_model_help"))
    with st.popover(t("cp_examples"), icon=":material/lightbulb:", disabled=locked):
        for k in examples:
            st.button(t(k), key=f"pop_{k}", type="tertiary", on_click=ask_pending, args=(t(k),))
    st.download_button(t("cp_download"), transcript(), file_name=f"copilot_{datetime.now():%Y%m%d_%H%M}.md",
                       mime="text/markdown", icon=":material/download:", disabled=not ss.cp_msgs,
                       on_click="ignore")
    st.button(t("cp_new"), icon=":material/add_comment:", type="tertiary", on_click=new_chat,
              disabled=not ss.cp_msgs or job is not None)
    st.toggle(t("cp_open_evidence"), key="cp_open")
if STATUS == "missing":
    st.error(t("cp_no_key", provider=PROVIDERS[PROVIDER]["name"], var=KEY_VAR), icon=":material/key_off:")
elif STATUS == "invalid":
    st.error(t("cp_key_invalid", provider=PROVIDERS[PROVIDER]["name"], var=KEY_VAR), icon=":material/key_off:")
elif STATUS == "unavailable":
    st.error(t("cp_unavailable", e=PROVIDERS[PROVIDER]["module"]), icon=":material/extension_off:")
elif not ready["db"]:
    st.warning(t("cp_db_down"), icon=":material/cloud_off:")
elif not ready["mining"]:
    st.info(t("cp_mining_missing"), icon=":material/info:")

# Câu hỏi cuối chưa có câu trả lời mà không còn job = lần chạy trước bị ngắt hẳn (vd. khởi động lại server)
if job is None and ss.cp_msgs and ss.cp_msgs[-1]["role"] == "user":
    ss.cp_msgs.append({"role": "assistant", "content": "", "kind": "stopped", "trace": []})

# ---------------------------------------------------------------- hội thoại
if not ss.cp_msgs:
    with st.chat_message("assistant"):
        st.markdown(t("cp_welcome"))
        st.pills(t("cp_try"), examples, format_func=lambda k: t(f"{k}_short"), key="cp_pill",
                 on_change=pick_example, disabled=locked)
        st.caption(t("cp_limits"))

for i, m in enumerate(ss.cp_msgs):
    with st.chat_message(m["role"]):
        if m["role"] == "user":
            st.markdown(safe_md(m["content"]))
        else:
            q = ss.cp_msgs[i - 1]["content"] if i and ss.cp_msgs[i - 1]["role"] == "user" else None
            render_answer(m, q, last=i == len(ss.cp_msgs) - 1, locked=locked or waiting)

prompt = st.chat_input(t("cp_placeholder"), max_chars=500, submit_mode="disable", disabled=locked or waiting)
if prompt:
    ss.cp_pending = prompt

if job is not None:
    poll(job)
elif waiting and not locked:
    countdown(until)  # câu hỏi gửi lúc đang chờ được giữ lại trong cp_pending và tự gửi khi hết giờ
elif ss.get("cp_pending") and not locked:
    start_job(ss.pop("cp_pending"))
