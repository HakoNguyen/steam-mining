"""Bảng màu (đã chạy kiểm định của skill dataviz cho cả nền sáng và nền tối) và kiểu chung cho Plotly.

Quy tắc dùng màu:
- Một chuỗi dữ liệu -> series[0] (xanh dương).
- Nhiều chuỗi -> series theo thứ tự cố định, tối đa 4 cho đường, 3 cho scatter; màu gắn theo đối tượng, không theo thứ hạng.
- Tăng / giảm -> up / down (xanh dương / đỏ).
- Độ lớn (heatmap) -> dải tuần tự một màu xanh.
- Chữ luôn dùng màu chữ (ink), không dùng màu của chuỗi dữ liệu.
"""
from dataclasses import dataclass

import streamlit as st

from lib.fmt import separators
from lib.i18n import lang

FONT = "Be Vietnam Pro, system-ui, -apple-system, Segoe UI, sans-serif"


@dataclass(frozen=True)
class Palette:
    mode: str
    surface: str
    ink: str
    ink2: str
    muted: str
    grid: str
    axis: str
    series: tuple
    up: str
    down: str
    seq: tuple
    hover_bg: str


LIGHT = Palette(
    mode="light", surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
    grid="#e1e0d9", axis="#c3c2b7",
    series=("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"),
    up="#2a78d6", down="#e34948",
    seq=("#eef4fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"),
    hover_bg="#ffffff",
)

DARK = Palette(
    mode="dark", surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781",
    grid="#2c2c2a", axis="#383835",
    series=("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"),
    up="#3987e5", down="#e66767",
    seq=("#1f2733", "#1c3557", "#184f95", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef", "#cde2fb"),
    hover_bg="#262624",
)


def palette():
    """Bảng màu theo giao diện người xem đang chọn (menu ⋮ > Settings > Theme)."""
    theme = getattr(st.context, "theme", None)
    return DARK if getattr(theme, "type", None) == "dark" else LIGHT


def style(fig, p, height=360, legend=False):
    """Kiểu chung: nền trong suốt (ăn theo thẻ), lưới mảnh, chữ dùng màu chữ, số theo ngôn ngữ."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13, color=p.ink2),
        separators=separators(),
        margin=dict(l=4, r=12, t=8 if not legend else 36, b=4),
        hoverlabel=dict(bgcolor=p.hover_bg, bordercolor=p.grid, font=dict(family=FONT, size=12, color=p.ink)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left",
                    font=dict(color=p.ink2, size=12), bgcolor="rgba(0,0,0,0)", title_text=""),
        colorway=list(p.series),
        barcornerradius=4,
        bargap=0.35,
    )
    # automargin: lề tự giãn theo độ dài nhãn trục (tên game, giá...) để nhãn không bị cắt
    axis = dict(gridcolor=p.grid, gridwidth=1, linecolor=p.axis, zeroline=False, ticks="", automargin=True,
                tickfont=dict(color=p.muted, size=12), title_font=dict(color=p.ink2, size=12))
    fig.update_xaxes(showgrid=False, showline=True, **axis)
    fig.update_yaxes(showgrid=True, showline=False, **axis)
    return fig


def show(fig):
    st.plotly_chart(fig, theme=None, config={"displayModeBar": False, "locale": lang()})


CSS = """
<style>
/* Tiêu đề khu vực và thẻ biểu đồ: nhiều khoảng thở, chữ đậm vừa */
h1 { font-weight: 700 !important; letter-spacing: -0.01em; }
h3, h4 { font-weight: 600 !important; letter-spacing: -0.005em; }
[data-testid="stMetricValue"] { font-weight: 600; }
[data-testid="stCaptionContainer"] { line-height: 1.45; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; }
/* Khi đổi ngôn ngữ / sáng tối, Streamlit chạy lại trang và làm mờ nội dung cũ trong lúc chờ:
   tắt hiệu ứng mờ để nội dung mới thay tại chỗ, không có cảm giác tải lại trang */
[data-stale="true"], [data-stale="true"] * { opacity: 1 !important; transition: none !important; }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)
