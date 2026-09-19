\c schoolpass

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO schoolpass_migrator;
GRANT USAGE ON SCHEMA public TO schoolpass_app;

ALTER DEFAULT PRIVILEGES FOR ROLE schoolpass_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO schoolpass_app;
ALTER DEFAULT PRIVILEGES FOR ROLE schoolpass_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO schoolpass_app;
