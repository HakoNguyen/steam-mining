import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
_ENV = dotenv_values(ROOT / ".env")


def setting(key, default=None):
    """Ưu tiên biến môi trường (Docker), rồi tới .env ở thư mục gốc dự án."""
    return os.environ.get(key) or _ENV.get(key) or default


# Streamlit server gọi API Metabase (trong Docker: http://metabase-bi:3000)
METABASE_URL = setting("METABASE_URL", "http://localhost:3000")
# Trình duyệt của người xem tải iframe nhúng (luôn là địa chỉ mở được từ máy người xem)
METABASE_PUBLIC_URL = setting("METABASE_PUBLIC_URL", "http://localhost:3000")
METABASE_API_KEY = setting("METABASE_API_KEY")
METABASE_EMBED_SECRET = setting("METABASE_EMBED_SECRET")

STREAMLIT_COLLECTION = "Streamlit"
DASHBOARD_NAME = "Steam Market — Smart Dashboard"
