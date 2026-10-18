-- User chỉ-đọc cho AI Copilot: chỉ SELECT trên dw, marts, mining; không sửa được dữ liệu.
-- Chạy (mật khẩu lấy từ COPILOT_DB_PASSWORD trong .env):
--   docker exec -i steam_postgres_dwh psql -U admin -d steam_dwh -v copilot_password=<mật khẩu> < scripts/create_copilot_role.sql
-- Chạy lại nhiều lần vẫn an toàn.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'copilot_ro') THEN
    CREATE ROLE copilot_ro LOGIN;
  END IF;
END $$;

ALTER ROLE copilot_ro WITH LOGIN PASSWORD :'copilot_password';
ALTER ROLE copilot_ro SET statement_timeout = '5s';               -- câu truy vấn chạy quá 5 giây bị hủy
ALTER ROLE copilot_ro SET default_transaction_read_only = on;     -- chặn ghi ở mức phiên làm việc

GRANT CONNECT ON DATABASE steam_dwh TO copilot_ro;

-- Schema cho kết quả Data Mining (HUYNH ghi bảng vào đây)
CREATE SCHEMA IF NOT EXISTS mining;

GRANT USAGE ON SCHEMA dw, marts, mining TO copilot_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA dw, marts, mining TO copilot_ro;

-- SQLMesh tạo lại view ở dw/marts mỗi lần plan; HUYNH tạo bảng mới ở mining.
-- Default privileges để quyền SELECT tự áp dụng cho các bảng/view tạo sau này (do user admin tạo).
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA dw, marts, mining GRANT SELECT ON TABLES TO copilot_ro;
