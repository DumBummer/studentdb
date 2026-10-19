
from db import get_db

FIELDS = (
    'student_id',
    'first_name',
    'last_name',
    'email',
    'program',
    'year_level',
    'status'
)


def list_students(search=''):
    term = search.strip()
    pattern = f'%{term}%'
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''
            SELECT student_id, first_name, last_name,
                   email, program, year_level, status
            FROM student
            WHERE %s = ''
               OR student_id ILIKE %s
               OR first_name ILIKE %s
               OR last_name ILIKE %s
               OR COALESCE(email, '') ILIKE %s
               OR COALESCE(program, '') ILIKE %s
            ORDER BY last_name, first_name, student_id
        ''', (term, pattern, pattern, pattern, pattern, pattern))
        return cur.fetchall()


def add_student(values):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''
            INSERT INTO student
            (student_id, first_name, last_name, email, program, year_level, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            values['student_id'],
            values['first_name'],
            values['last_name'],
            values['email'] or None,
            values['program'] or None,
            values['year_level'],
            values['status']
        ))


def update_student(student_id, values):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''
            UPDATE student
            SET first_name=%s,
                last_name=%s,
                email=%s,
                program=%s,
                year_level=%s,
                status=%s
            WHERE student_id=%s
        ''', (
            values['first_name'],
            values['last_name'],
            values['email'] or None,
            values['program'] or None,
            values['year_level'],
            values['status'],
            student_id
        ))


def delete_student(student_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM student WHERE student_id = %s",
                (student_id,)
            )


def student_count():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM student")
            result = cur.fetchone()
            return result["total"]


def count_students():
    return student_count()
