"""Student CRUD using the existing dictionary-row PostgreSQL connection."""
from db import get_db

FIELDS = ('student_id', 'first_name', 'last_name', 'email', 'program', 'status')


def list_students(search=''):
    term = search.strip()
    pattern = f'%{term}%'
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT student_id, first_name, last_name, email, program, status
            FROM student WHERE %s = '' OR student_id ILIKE %s OR first_name ILIKE %s
            OR last_name ILIKE %s OR COALESCE(email,'') ILIKE %s OR COALESCE(program,'') ILIKE %s
            ORDER BY last_name, first_name, student_id''', (term, pattern, pattern, pattern, pattern, pattern))
        return cur.fetchall()


def add_student(values):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO student (student_id,first_name,last_name,email,program,status)
            VALUES (%s,%s,%s,%s,%s,%s)''', tuple(values[k] or None if k in ('email','program') else values[k] for k in FIELDS))


def update_student(student_id, values):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE student SET first_name=%s,last_name=%s,email=%s,program=%s,status=%s
            WHERE student_id=%s''', tuple(values[k] or None if k in ('email','program') else values[k] for k in FIELDS[1:]) + (student_id,))


def delete_student(student_id):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('DELETE FROM student WHERE student_id=%s', (student_id,))


def student_count():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS total FROM student')
        return cur.fetchone()['total']


def count_students():
    return student_count()
