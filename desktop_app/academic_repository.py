from decimal import Decimal
from uuid import uuid4
from db import get_db
from psycopg import errors
from PySide6.QtWidgets import QMessageBox

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

        if name == 'Teachers':
            cur.execute("""
                SELECT
                    t.teacher_id,
                    t.first_name,
                    t.last_name,
                    t.email,
                    t.department,
                    t.status,
                    t.subject_id,
                    s.description AS subject_description
                FROM teacher t
                LEFT JOIN subject s
                    ON t.subject_id = s.subject_id
                ORDER BY t.teacher_id
                LIMIT 1000
            """)
        else:
            cur.execute(
                f'SELECT * FROM {table} ORDER BY {pk} LIMIT 1000'
            )

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
    if name == 'Teachers' and (not str(data.get('first_name') or '').strip() or not str(data.get('last_name') or '').strip()):
        raise ValueError('Teacher first name and last name are required')
    if name == 'Subjects':
        if not str(data.get('subject_code') or '').strip() or not str(data.get('subject_name') or '').strip():
            raise ValueError('Subject code and name are required')
        try:
            if Decimal(str(data.get('units'))) <= 0:
                raise ValueError('Subject units must be greater than zero')
        except (TypeError, ArithmeticError):
            raise ValueError('Enter valid subject units')
    if name == 'Enrollments':
        status = str(data.get('status') or 'Enrolled').strip().lower()
        if status not in ('enrolled', 'dropped', 'completed'):
            raise ValueError('Enrollment status must be Enrolled, Dropped or Completed')
        data = {**data, 'status': status}
    values = [data.get(f) or None for f in fields]
    with get_db() as conn, conn.cursor() as cur:
        if record_id is not None:
            assignments = ', '.join(f'{f}=%s' for f in fields)
            cur.execute(f'UPDATE {table} SET {assignments} WHERE {pk}=%s', (*values, record_id))
        else:
            if name == 'Teachers':
                manual_id = str(data.get('teacher_id') or '').strip()
                if not manual_id:
                    raise ValueError('Teacher ID is required')
                if schema[pk]['data_type'] == 'uuid':
                    from uuid import UUID
                    try:
                        manual_id = str(UUID(manual_id))
                    except (ValueError, AttributeError) as exc:
                        raise ValueError(
                            'This database stores Teacher IDs as UUIDs. Enter a valid UUID, '
                            'or migrate the teacher_id column to text before using IDs like TCH-001.'
                        ) from exc
                new_id = manual_id
            else:
                new_id = str(uuid4())
            cur.execute(f'INSERT INTO {table} ({pk}, {", ".join(fields)}) VALUES ({", ".join(["%s"] * (len(fields) + 1))})', (new_id, *values))


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
        cur.execute('''SELECT c.max_score, c.offering_id, e.offering_id AS enrolled_offering
                       FROM grade_component c CROSS JOIN enrollment e
                       WHERE c.component_id=%s AND e.enrollment_id=%s''',
                    (data['component_id'], data['enrollment_id']))
        component = cur.fetchone()
        if component is None:
            raise ValueError('Enrollment or grade component does not exist')
        if component['offering_id'] != component['enrolled_offering']:
            raise ValueError('Grade component belongs to a different class offering')
        if score > Decimal(str(component['max_score'])):
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


def college_grade_point(percentage):
    if percentage is None:
        return None
    value = Decimal(str(percentage))
    for cutoff, point in [(97, '1.00'), (94, '1.25'), (91, '1.50'),
                          (88, '1.75'), (85, '2.00'), (82, '2.25'),
                          (79, '2.50'), (76, '2.75'), (75, '3.00')]:
        if value >= cutoff:
            return Decimal(point)
    return Decimal('5.00')


def overall_rows():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""SELECT s.student_id, s.first_name, s.last_name,
            co.class_code, e.enrollment_id, gp.name AS period_name, g.final_grade
            FROM enrollment e
            JOIN student s ON s.student_id=e.student_id
            JOIN class_offering co ON co.offering_id=e.offering_id
            LEFT JOIN grade g ON g.enrollment_id=e.enrollment_id
            LEFT JOIN grading_period gp ON gp.period_id=g.period_id
            ORDER BY s.last_name, s.first_name, co.class_code""")
        records = {}
        for row in cur.fetchall():
            key = str(row['enrollment_id'])
            result = records.setdefault(key, {
                'student_id': row['student_id'], 'first_name': row['first_name'],
                'last_name': row['last_name'], 'class_code': row['class_code'],
                'midterm_percentage': None, 'finals_percentage': None,
                'overall_percentage': None, 'final_equiv': None, 'remarks': 'Pending'
            })
            period = str(row.get('period_name') or '').strip().lower()
            if period == 'midterm':
                result['midterm_percentage'] = row['final_grade']
            elif period in ('final', 'finals'):
                result['finals_percentage'] = row['final_grade']
        for result in records.values():
            midterm = result['midterm_percentage']
            finals = result['finals_percentage']
            if midterm is not None and finals is not None:
                overall = Decimal(str(midterm)) * Decimal('0.40') + Decimal(str(finals)) * Decimal('0.60')
                result['overall_percentage'] = overall.quantize(Decimal('0.01'))
                result['final_equiv'] = college_grade_point(overall)
                result['remarks'] = 'Passed' if overall >= 75 else 'Failed'
        return list(records.values())


def enrollment_choices():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT e.enrollment_id AS id,
            s.first_name || ' ' || s.last_name || ' / ' || co.class_code || ' / Prof. ' || COALESCE(t.last_name, 'Unassigned') AS label
            FROM enrollment e JOIN student s ON s.student_id=e.student_id
            JOIN class_offering co ON co.offering_id=e.offering_id
            LEFT JOIN teacher t ON t.teacher_id=co.teacher_id
            ORDER BY label''')
        return [(str(r['id']), str(r['label'])) for r in cur.fetchall()]
    
def show_error(parent, error):
    if isinstance(error, errors.CheckViolation):
        constraint = getattr(error.diag, "constraint_name", None)
        message = (
            "A value does not match the database rules.\n\n"
            f"Failed constraint: {constraint or 'Unknown'}\n\n"
            f"Details: {error}"
        )

    elif isinstance(error, errors.ForeignKeyViolation):
        message = (
            "This record is referenced by another record, "
            "or the selected related record does not exist.\n\n"
            f"Details: {error}"
        )

    elif isinstance(error, errors.UniqueViolation):
        message = "This ID or another unique value already exists."

    elif isinstance(error, ValueError):
        message = str(error)

    else:
        message = str(error)

    QMessageBox.critical(parent, "StudentDB — Database Error", message)


def normalize_component_type(value):
    value = str(value).strip().lower()

    for prefix in ("midterm ", "finals ", "final "):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break

    if value in ("exam", "examination"):
        return "exam"

    if value in (
        "project",
        "laboratory",
        "lab",
        "laboratory/project",
        "lab/project",
    ):
        return "project"

    if value == "quiz":
        return "quiz"

    return value


def calculate_period_grade(enrollment_id, period_id):
    """Compute a complete period with period-scoped weights, then persist it."""
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''SELECT e.offering_id, gp.name AS period_name
                       FROM enrollment e CROSS JOIN grading_period gp
                       WHERE e.enrollment_id=%s AND gp.period_id=%s''',
                    (enrollment_id, period_id))
        context = cur.fetchone()
        if context is None:
            raise ValueError('Unknown enrollment or grading period')
        period_name = str(context['period_name']).strip().lower()
        if period_name not in ('midterm', 'final', 'finals'):
            raise ValueError('Expected Midterm or Finals grading period')
        cur.execute('''
            SELECT component_type, percentage
            FROM grade_percentage
            WHERE offering_id = %s
            AND LOWER(TRIM(component_type)) LIKE %s
        ''', (
            context['offering_id'],
            (
                'midterm %'
                if str(context['period_name']).strip().lower() == 'midterm'
                else 'final %'
            )
        ))
        weights = {}
        for item in cur.fetchall():
            kind = normalize_component_type(item['component_type'])
            if kind in weights:
                raise ValueError(f'Duplicate weight for {kind} in {period_name}')
            weights[kind] = Decimal(str(item['percentage']))
        if set(weights) != {'quiz', 'project', 'exam'}:
            raise ValueError('Each period needs Quiz, Lab/Project and Exam weights')
        if sum(weights.values()) != Decimal('100'):
            raise ValueError(f'{period_name} weights must total 100%, not {sum(weights.values())}%')
        cur.execute('''SELECT c.component_id, c.type, c.max_score, sc.score
                       FROM grade_component c
                       LEFT JOIN grade_component_score sc
                         ON sc.component_id=c.component_id AND sc.enrollment_id=%s
                       WHERE c.offering_id=%s AND c.grading_period_id=%s''',
                    (enrollment_id, context['offering_id'], period_id))
        grouped = {'quiz': [], 'project': [], 'exam': []}
        for item in cur.fetchall():
            kind = normalize_component_type(item['type'])
            if kind not in grouped:
                raise ValueError(f'Unsupported component type: {item["type"]}')
            if item['score'] is None:
                raise ValueError(f'Missing score for component {item["component_id"]}')
            maximum = Decimal(str(item['max_score']))
            score = Decimal(str(item['score']))
            if maximum <= 0 or not (0 <= score <= maximum):
                raise ValueError('Score must be between zero and component maximum')
            grouped[kind].append(score / maximum * 100)
        if any(not group for group in grouped.values()):
            raise ValueError('Each period needs scores for Quiz, Lab/Project and Exam')
        percentage = sum((sum(group) / len(group)) * weights[kind] / 100
                         for kind, group in grouped.items()).quantize(Decimal('0.01'))
        cur.execute('SELECT grade_id FROM grade WHERE enrollment_id=%s AND period_id=%s',
                    (enrollment_id, period_id))
        existing = cur.fetchall()
        if len(existing) > 1:
            raise ValueError('Duplicate grade records found; resolve before recalculating')
        if existing:
            cur.execute('''UPDATE grade SET final_grade=%s, remarks=%s, date_encoded=CURRENT_DATE
                           WHERE grade_id=%s''', (percentage, 'Calculated', existing[0]['grade_id']))
        else:
            cur.execute('''INSERT INTO grade (grade_id, enrollment_id, period_id, final_grade, remarks)
                           VALUES (%s,%s,%s,%s,%s)''',
                        (str(uuid4()), enrollment_id, period_id, percentage, 'Calculated'))
        cur.execute('''SELECT gp.name, g.final_grade FROM grade g
                       JOIN grading_period gp ON gp.period_id=g.period_id
                       WHERE g.enrollment_id=%s''', (enrollment_id,))
        periods = {}
        for item in cur.fetchall():
            label = str(item['name']).strip().lower()
            label = 'finals' if label in ('final', 'finals') else label
            if label in periods:
                raise ValueError('Duplicate period grades; cannot consolidate')
            periods[label] = item['final_grade']
        midterm = periods.get('midterm')
        finals = periods.get('finals')
        overall = ((Decimal(str(midterm)) * Decimal('0.40') +
                    Decimal(str(finals)) * Decimal('0.60')).quantize(Decimal('0.01'))
                   if midterm is not None and finals is not None else None)
        cur.execute('''UPDATE grade SET midterm_grade=%s, finals_grade=%s,
                       overall_grade=%s, midterm_equiv=%s, final_equiv=%s
                       WHERE enrollment_id=%s''',
                    (midterm, finals, overall,
                     college_grade_point(midterm) if midterm is not None else None,
                     college_grade_point(overall) if overall is not None else None,
                     enrollment_id))
        return percentage
