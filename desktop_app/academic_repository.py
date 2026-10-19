"""Academic database operations for the existing StudentDB PostgreSQL database.

No DDL or destructive migration is performed. All SQL identifiers come from fixed
application metadata; user values are always parameterized.
"""
from decimal import Decimal
from uuid import uuid4
from db import get_db

# (table, primary key, editable fields): schema may vary between installations.
ENTITIES = {
    'Teachers': ('teacher', 'teacher_id', ['first_name', 'last_name', 'email', 'department', 'status', 'subject_id']),
    'Subjects': ('subject', 'subject_id', ['subject_code', 'subject_name', 'description', 'units']),
    'Class Offerings': ('class_offering', 'offering_id', ['class_code', 'subject_id', 'teacher_id', 'schedule', 'section', 'school_year', 'semester', 'room']),
    'Enrollments': ('enrollment', 'enrollment_id', ['student_id', 'offering_id', 'enroll_date', 'status']),
    'Grading Periods': ('grading_period', 'period_id', ['name', 'start_date', 'end_date', 'school_year', 'semester']),
    'Grade Components': ('grade_component', 'component_id', ['grading_period_id', 'offering_id', 'name', 'type', 'max_score', 'description']),
    'Grade Weights': ('grade_percentage', 'percentage_id', ['offering_id', 'component_id', 'period_id', 'component_type', 'percentage']),
}
FOREIGN_KEYS = {
    'subject_id': ('subject', 'subject_id', 'subject_name'),
    'teacher_id': ('teacher', 'teacher_id', 'last_name'),
    'student_id': ('student', 'student_id', 'last_name'),
    'offering_id': ('class_offering', 'offering_id', 'class_code'),
    'grading_period_id': ('grading_period', 'period_id', 'name'),
    'period_id': ('grading_period', 'period_id', 'name'),
    'component_id': ('grade_component', 'component_id', 'name'),
    'enrollment_id': ('enrollment', 'enrollment_id', 'enrollment_id'),
}


def columns(table):
    if table not in {v[0] for v in ENTITIES.values()} | {'grade_component_score', 'grade', 'student'}:
        raise ValueError('Unknown table')
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = %s
            ORDER BY ordinal_position''', (table,))
        return {r['column_name']: r for r in cur.fetchall()}


def entity_fields(name):
    table, pk, fields = ENTITIES[name]
    schema = columns(table)
    return table, pk, [f for f in fields if f in schema], schema


def rows(name):
    table, pk, _, _ = entity_fields(name)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(f'SELECT * FROM {table} ORDER BY {pk} LIMIT 1000')
        return cur.fetchall()


def choices(field):
    table, pk, label = FOREIGN_KEYS[field]
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(f'SELECT {pk} AS id, {label} AS label FROM {table} ORDER BY {label} LIMIT 2000')
        return [(str(r['id']), str(r['label'])) for r in cur.fetchall()]


def save_entity(name, data, record_id=None):
    table, pk, fields, schema = entity_fields(name)
    required = [f for f in fields if schema[f]['is_nullable'] == 'NO' and schema[f]['column_default'] is None]
    for field in required:
        if not str(data.get(field, '') or '').strip():
            raise ValueError(f'{field.replace("_", " ").title()} is required')
    values = [data.get(f) or None for f in fields]
    with get_db() as conn, conn.cursor() as cur:
        if record_id is not None:
            assignments = ', '.join(f'{f}=%s' for f in fields)
            cur.execute(f'UPDATE {table} SET {assignments} WHERE {pk}=%s', (*values, record_id))
        else:
            # Existing StudentDB academic IDs are text-based UUIDs.
            cur.execute(f'INSERT INTO {table} ({pk}, {", ".join(fields)}) VALUES ({", ".join(["%s"] * (len(fields) + 1))})', (str(uuid4()), *values))


def delete_entity(name, record_id):
    table, pk, _, _ = entity_fields(name)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(f'DELETE FROM {table} WHERE {pk}=%s', (record_id,))


def score_rows():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM grade_component_score ORDER BY date_recorded DESC LIMIT 1000')
        return cur.fetchall()


def score_schema():
    return columns('grade_component_score')


def save_score(data):
    schema = score_schema()
    fields = [f for f in ['enrollment_id', 'component_id', 'period_id', 'score', 'remarks'] if f in schema]
    if not data.get('enrollment_id') or not data.get('component_id'):
        raise ValueError('Enrollment and component are required')
    score = Decimal(str(data.get('score', '')))
    if score < 0:
        raise ValueError('Score cannot be negative')
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT max_score FROM grade_component WHERE component_id=%s', (data['component_id'],))
        component = cur.fetchone()
        if not component or score > Decimal(str(component['max_score'])):
            raise ValueError('Score exceeds the component maximum')
        cur.execute('SELECT score_id FROM grade_component_score WHERE enrollment_id=%s AND component_id=%s' + (' AND period_id=%s' if 'period_id' in schema else ''),
                    (data['enrollment_id'], data['component_id'], data.get('period_id')) if 'period_id' in schema else (data['enrollment_id'], data['component_id']))
        existing = cur.fetchone()
        if existing:
            cur.execute('UPDATE grade_component_score SET score=%s, remarks=%s, date_recorded=CURRENT_TIMESTAMP WHERE score_id=%s',
                        (score, data.get('remarks') or None, existing['score_id']))
        else:
            cur.execute(f'INSERT INTO grade_component_score (score_id, {", ".join(fields)}) VALUES ({", ".join(["%s"] * (len(fields) + 1))})',
                        (str(uuid4()), *(score if f == 'score' else data.get(f) or None for f in fields)))


def grade_rows():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT g.*, s.student_id, s.first_name, s.last_name,
            co.class_code, gp.name AS period_name
            FROM grade g JOIN enrollment e ON e.enrollment_id=g.enrollment_id
            JOIN student s ON s.student_id=e.student_id
            JOIN class_offering co ON co.offering_id=e.offering_id
            LEFT JOIN grading_period gp ON gp.period_id=g.period_id
            ORDER BY s.last_name, s.first_name, co.class_code, gp.name LIMIT 2000''')
        return cur.fetchall()


def overall_rows():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT s.student_id, s.first_name, s.last_name,
            co.class_code, COUNT(g.final_grade) AS periods,
            ROUND(AVG(g.final_grade), 2) AS overall_grade
            FROM grade g JOIN enrollment e ON e.enrollment_id=g.enrollment_id
            JOIN student s ON s.student_id=e.student_id
            JOIN class_offering co ON co.offering_id=e.offering_id
            WHERE g.final_grade IS NOT NULL
            GROUP BY s.student_id, s.first_name, s.last_name, co.class_code
            ORDER BY s.last_name, s.first_name, co.class_code LIMIT 2000''')
        return cur.fetchall()


def enrollment_choices():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT e.enrollment_id AS id,
            s.first_name || ' ' || s.last_name || ' / ' || co.class_code AS label
            FROM enrollment e JOIN student s ON s.student_id=e.student_id
            JOIN class_offering co ON co.offering_id=e.offering_id
            ORDER BY label''')
        return [(str(r['id']), str(r['label'])) for r in cur.fetchall()]


def calculate_period_grade(enrollment_id, period_id):
    """Calculate and persist a weighted grade using whichever weight schema exists.

    Refuses incomplete configurations and does not overwrite unrelated grades.
    """
    score_cols = columns('grade_component_score')
    weight_cols = columns('grade_percentage')
    comp_cols = columns('grade_component')
    with get_db() as conn, conn.cursor() as cur:
        if {'component_id', 'period_id'} <= set(weight_cols):
            cur.execute('''SELECT c.component_id, c.max_score, w.percentage,
                sc.score FROM grade_percentage w
                JOIN grade_component c ON c.component_id=w.component_id
                LEFT JOIN grade_component_score sc ON sc.component_id=c.component_id
                    AND sc.enrollment_id=%s''' + (' AND sc.period_id=w.period_id' if 'period_id' in score_cols else '') + '''
                WHERE w.period_id=%s''', (enrollment_id, period_id))
        elif {'component_type', 'offering_id'} <= set(weight_cols) and 'type' in comp_cols:
            cur.execute('''SELECT c.component_id, c.max_score, w.percentage, sc.score
                FROM enrollment e JOIN grade_component c ON c.offering_id=e.offering_id
                JOIN grade_percentage w ON w.offering_id=e.offering_id AND w.component_type=c.type
                LEFT JOIN grade_component_score sc ON sc.component_id=c.component_id
                    AND sc.enrollment_id=e.enrollment_id
                WHERE e.enrollment_id=%s''' + (' AND c.grading_period_id=%s' if 'grading_period_id' in comp_cols else ''),
                (enrollment_id, period_id) if 'grading_period_id' in comp_cols else (enrollment_id,))
        else:
            raise ValueError('Grade weight table structure is not supported by the calculator')
        records = cur.fetchall()
        if not records or any(r['score'] is None for r in records):
            raise ValueError('Encode all required component scores first')
        # Multiple components may share a type; count each type weight once in that schema.
        if 'component_type' in weight_cols and 'offering_id' in weight_cols:
            cur.execute('''SELECT COALESCE(SUM(percentage),0) AS total FROM grade_percentage
                WHERE offering_id=(SELECT offering_id FROM enrollment WHERE enrollment_id=%s)''', (enrollment_id,))
            configured = Decimal(str(cur.fetchone()['total']))
            if configured != 100:
                raise ValueError(f'Configured weight total is {configured}%, expected 100%')
            # Average percentages within each type rather than double-counting type weight.
            cur.execute('''SELECT c.type, AVG(sc.score / NULLIF(c.max_score,0) * 100) AS pct,
                w.percentage FROM enrollment e
                JOIN grade_component c ON c.offering_id=e.offering_id
                JOIN grade_percentage w ON w.offering_id=e.offering_id AND w.component_type=c.type
                JOIN grade_component_score sc ON sc.component_id=c.component_id AND sc.enrollment_id=e.enrollment_id
                WHERE e.enrollment_id=%s''' + (' AND c.grading_period_id=%s' if 'grading_period_id' in comp_cols else '') + '''
                GROUP BY c.type, w.percentage''',
                (enrollment_id, period_id) if 'grading_period_id' in comp_cols else (enrollment_id,))
            groups = cur.fetchall()
            final = sum(Decimal(str(r['pct'])) * Decimal(str(r['percentage'])) / 100 for r in groups)
        else:
            total = sum(Decimal(str(r['percentage'])) for r in records)
            if total != 100:
                raise ValueError(f'Configured weight total is {total}%, expected 100%')
            final = sum(Decimal(str(r['score'])) / Decimal(str(r['max_score'])) * Decimal(str(r['percentage'])) for r in records)
        final = final.quantize(Decimal('0.01'))
        cur.execute('SELECT grade_id FROM grade WHERE enrollment_id=%s AND period_id=%s', (enrollment_id, period_id))
        existing = cur.fetchone()
        if existing:
            cur.execute('''UPDATE grade SET final_grade=%s, remarks=%s,
                date_encoded=CURRENT_TIMESTAMP WHERE grade_id=%s''', (final, 'Calculated', existing['grade_id']))
        else:
            cur.execute('''INSERT INTO grade (grade_id, enrollment_id, period_id, final_grade, remarks)
                VALUES (%s,%s,%s,%s,%s)''', (str(uuid4()), enrollment_id, period_id, final, 'Calculated'))
        return final
