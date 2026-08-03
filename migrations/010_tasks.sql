-- Этап C: задачи и напоминания.
-- Выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

CREATE TABLE IF NOT EXISTS cd_tasks (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  title varchar(255) NOT NULL,
  description text NOT NULL DEFAULT '',
  status varchar(24) NOT NULL DEFAULT 'todo'
    CHECK (status IN ('todo','in_progress','done','cancelled')),
  priority varchar(12) NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low','normal','high','urgent')),
  assignee_id integer REFERENCES cd_users(id) ON DELETE SET NULL,
  due_at timestamptz,
  remind_at timestamptz,
  reminded boolean NOT NULL DEFAULT false,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_tasks_workspace ON cd_tasks(workspace_id, due_at);
CREATE INDEX IF NOT EXISTS idx_cd_tasks_remind ON cd_tasks(remind_at, reminded) WHERE remind_at IS NOT NULL;

INSERT INTO schema_migrations(version) VALUES('010_tasks') ON CONFLICT(version) DO NOTHING;
