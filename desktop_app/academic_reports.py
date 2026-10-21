"""Read-only academic reports for StudentDB's PostgreSQL database."""
from decimal import Decimal, ROUND_HALF_UP
from db import get_db
from .academic_repository import college_grade_point


def class_choices():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT offering_id AS id, class_code AS label
            FROM class_offering ORDER BY class_code
        """)
        return cur.fetchall()


def student_choices():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT student_id AS id,
                   student_id || ' - ' || first_name || ' ' || last_name AS label
            FROM student ORDER BY last_name, first_name, student_id
        """)
        return cur.fetchall()


def class_list(offering_id):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT s.student_id, s.last_name, s.first_name,
                   e.status AS enrollment_status, co.class_code
            FROM enrollment e
            JOIN student s ON s.student_id=e.student_id
            JOIN class_offering co ON co.offering_id=e.offering_id
            WHERE e.offering_id=%s
            ORDER BY s.last_name, s.first_name, s.student_id
        """, (offering_id,))
        return cur.fetchall()


def _completed_grades():
    """Return one result per enrollment; no double counting of period rows."""
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT e.enrollment_id, e.student_id, e.offering_id,
                   co.class_code, s.first_name, s.last_name,
                   subj.subject_code, subj.subject_name, subj.units,
                   t.first_name AS teacher_first_name,
                   t.last_name AS teacher_last_name,
                   gp.name AS period_name, g.final_grade
            FROM enrollment e
            JOIN student s ON s.student_id=e.student_id
            JOIN class_offering co ON co.offering_id=e.offering_id
            LEFT JOIN teacher t ON t.teacher_id=co.teacher_id
            LEFT JOIN subject subj ON subj.subject_id=COALESCE(co.subject_id, t.subject_id)
            LEFT JOIN grade g ON g.enrollment_id=e.enrollment_id
            LEFT JOIN grading_period gp ON gp.period_id=g.period_id
            ORDER BY s.last_name, s.first_name, co.class_code
        """)
        rows = cur.fetchall()

    grouped = {}
    for row in rows:
        key = str(row['enrollment_id'])
        entry = grouped.setdefault(key, {
            'enrollment_id': row['enrollment_id'],
            'student_id': row['student_id'],
            'offering_id': row['offering_id'],
            'class_code': row['class_code'],
            'first_name': row['first_name'],
            'last_name': row['last_name'],
            'subject_code': row['subject_code'],
            'subject_name': row['subject_name'],
            'units': row['units'],
            'teacher': ' '.join(str(part) for part in
                (row['teacher_first_name'], row['teacher_last_name']) if part) or 'Unassigned',
            'midterm': None, 'finals': None,
        })
        period = str(row['period_name'] or '').strip().lower()
        if period == 'midterm':
            entry['midterm'] = row['final_grade']
        elif period in ('final', 'finals'):
            entry['finals'] = row['final_grade']

    for entry in grouped.values():
        midterm, finals = entry['midterm'], entry['finals']
        entry['midterm_equiv'] = college_grade_point(midterm)
        entry['finals_equiv'] = college_grade_point(finals)
        entry['overall'] = None
        entry['final_equiv'] = None
        entry['remarks'] = 'Pending'
        if midterm is not None and finals is not None:
            overall = (Decimal(str(midterm)) * Decimal('0.40') +
                       Decimal(str(finals)) * Decimal('0.60'))
            overall = overall.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            entry['overall'] = overall
            entry['final_equiv'] = college_grade_point(overall)
            entry['remarks'] = 'Passed' if overall >= 75 else 'Failed'
    return list(grouped.values())


def class_grade_sheet(offering_id):
    return [row for row in _completed_grades()
            if str(row['offering_id']) == str(offering_id)]


def student_grade_report(student_id):
    rows = [row for row in _completed_grades()
            if str(row['student_id']) == str(student_id)]
    weighted = Decimal('0')
    total_units = Decimal('0')
    for row in rows:
        if row['final_equiv'] is not None and row['units'] is not None:
            units = Decimal(str(row['units']))
            if units > 0:
                weighted += Decimal(str(row['final_equiv'])) * units
                total_units += units
    gwa = (weighted / total_units).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if total_units else None
    return rows, gwa, total_units
