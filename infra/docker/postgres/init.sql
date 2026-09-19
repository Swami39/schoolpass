-- Local/CI bootstrap. Production roles are created by Terraform (later).
-- Runtime role MUST remain NOBYPASSRLS.

CREATE ROLE schoolpass_migrator LOGIN PASSWORD 'migrator_dev_only' BYPASSRLS;
CREATE ROLE schoolpass_app LOGIN PASSWORD 'app_dev_only' NOBYPASSRLS;
CREATE ROLE schoolpass_breakglass LOGIN PASSWORD 'breakglass_dev_only' BYPASSRLS;

CREATE DATABASE schoolpass OWNER schoolpass_migrator;

GRANT CONNECT ON DATABASE schoolpass TO schoolpass_app;
GRANT CONNECT ON DATABASE schoolpass TO schoolpass_breakglass;
