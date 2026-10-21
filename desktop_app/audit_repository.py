"""Read-only access to StudentDB's PostgreSQL audit history."""
from db import get_db


def audit_tables():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT table_name FROM public.audit_log ORDER BY table_name")
        return [row['table_name'] for row in cur.fetchall()]


def audit_rows(search='', table_name='', action='', limit=500):
    """Fetch newest audit entries; parameters are bound to prevent SQL injection."""
    search = (search or '').strip()
    table_name = (table_name or '').strip()
    action = (action or '').strip().upper()
    limit = max(1, min(int(limit), 2000))
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''
            SELECT audit_id, table_name, record_id, action, changed_at,
                   old_data, new_data
            FROM public.audit_log
            WHERE (%s = '' OR table_name = %s)
              AND (%s = '' OR action = %s)
              AND (%s = '' OR table_name ILIKE %s OR record_id ILIKE %s
                   OR action ILIKE %s OR CAST(audit_id AS TEXT) ILIKE %s)
            ORDER BY audit_id DESC
            LIMIT %s
        ''', (table_name, table_name, action, action,
              search, *([f'%{search}%'] * 4), limit))
        return cur.fetchall()
