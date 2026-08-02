from pathlib import Path
import os, psycopg

url=os.getenv('DATABASE_URL','').strip().replace('postgresql+psycopg://','postgresql://').replace('postgresql+asyncpg://','postgresql://')
if not url: raise SystemExit('DATABASE_URL is required')
files=sorted(Path(__file__).parent.joinpath('migrations').glob('*.sql'))
with psycopg.connect(url) as conn:
    for path in files:
        version=path.stem
        with conn.cursor() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version varchar(64) PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now())')
            cur.execute('SELECT 1 FROM schema_migrations WHERE version=%s',(version,))
            if cur.fetchone(): print('skip',version); continue
            # psycopg3 does not allow multiple SQL statements in one execute.
            statements=[part.strip() for part in path.read_text(encoding='utf-8').split(';') if part.strip()]
            for statement in statements:
                cur.execute(statement)
            print('apply',version)
print('done')
