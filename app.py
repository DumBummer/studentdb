import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from db import get_db
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from psycopg import IntegrityError
from services.grading_service import calculate_final_grade
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'change-this-development-key')
from decimal import Decimal, ROUND_HALF_UP

@app.get('/')
def dashboard():
    with get_db() as conn:
        with conn.cursor() as cur:
            stats = {}
            for name, table in [('students','student'),('subjects','subject'),('classes','class_offering'),('grades','grade')]:
                cur.execute(f'SELECT COUNT(*) AS n FROM {table}')
                stats[name] = cur.fetchone()['n']
            cur.execute('SELECT * FROM student ORDER BY last_name, first_name LIMIT 8')
            recent = cur.fetchall()
    return render_template('dashboard.html', stats=stats, recent=recent)

@app.get('/students')
def students():
    term = request.args.get('q','').strip()
    pattern = f'%{term}%'
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT * FROM student WHERE %s = '' OR student_id ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s OR COALESCE(email,'') ILIKE %s ORDER BY last_name, first_name''', (term, pattern, pattern, pattern, pattern))
            rows = cur.fetchall()
    return render_template('students.html', rows=rows, term=term)


@app.route('/students/new', methods=['GET', 'POST'])
def student_new():
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        program = request.form.get('program', '').strip()
        status = request.form.get('status', 'active').strip().lower()

        if not all([student_id, first_name, last_name, email]):
            flash('Student ID, first name, last name, and email are required.', 'error')
            return render_template(
                'student_form.html',
                student=request.form,
                editing=False
            )

        if status not in ('active', 'inactive', 'graduated', 'dropped'):
            flash('Invalid student status.', 'error')
            return render_template(
                'student_form.html',
                student=request.form,
                editing=False
            )

        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO student
                        (student_id, first_name, last_name, email, program, status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        student_id,
                        first_name,
                        last_name,
                        email,
                        program or None,
                        status
                    ))

            flash('Student added successfully!', 'success')
            return redirect(url_for('students'))

        except IntegrityError:
            app.logger.exception("Student registration constraint error")
            flash('Student ID or email already exists, or a database constraint was violated.', 'error')

        except Exception:
            app.logger.exception("Unexpected student registration error")
            flash('Could not save student. Check the terminal for details.', 'error')

        return render_template(
            'student_form.html',
            student=request.form,
            editing=False
        )

    return render_template(
        'student_form.html',
        student={},
        editing=False
    )


@app.route('/students/<student_id>/edit', methods=['GET','POST'])
def student_edit(student_id):
    if request.method == 'POST':
        data = [request.form.get(k,'').strip() for k in ('first_name','last_name','email','program','status')]
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute('UPDATE student SET first_name=%s,last_name=%s,email=%s,program=%s,status=%s WHERE student_id=%s', (*data,student_id))
            flash('Student updated.','success')
            return redirect(url_for('students'))
        except Exception:
            flash('Could not update student. Check whether the email is already in use.','error')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM student WHERE student_id=%s',(student_id,))
            student = cur.fetchone()
    if not student:
        flash('Student not found.','error')
        return redirect(url_for('students'))
    return render_template('student_form.html', student=student, editing=True)

@app.post('/students/<student_id>/delete')
def student_delete(student_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM student WHERE student_id=%s',(student_id,))
        flash('Student deleted.','success')
    except Exception:
        flash('This student has academic records. Change their status to Inactive instead.','error')
    return redirect(url_for('students'))



@app.get('/grades')
def grades():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    g.grade_id,
                    g.final_grade,
                    g.remarks,
                    g.date_encoded,

                    s.student_id,
                    s.first_name,
                    s.last_name,

                    sub.subject_code,
                    sub.subject_name,

                    co.class_code,
                    co.section,
                    co.school_year,
                    co.semester,

                    t.first_name AS teacher_first_name,
                    t.last_name AS teacher_last_name,

                    gp.name AS period_name

                FROM grade g

                JOIN enrollment e
                    ON e.enrollment_id = g.enrollment_id

                JOIN student s
                    ON s.student_id = e.student_id

                JOIN class_offering co
                    ON co.offering_id = e.offering_id

                LEFT JOIN teacher t
                    ON t.teacher_id = co.teacher_id

                LEFT JOIN subject sub
                    ON sub.subject_id = t.subject_id

                LEFT JOIN grading_period gp
                    ON gp.period_id = g.period_id

                ORDER BY
                    g.date_encoded DESC NULLS LAST
            """)

            rows = cur.fetchall()

    return render_template(
        'grades.html',
        rows=rows
    )



@app.get('/health')
def health():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT version()')
                return {'status':'ok','database':cur.fetchone()['version']}
    except Exception:
        return {'status':'error','message':'Database connection failed. Check environment settings.'},503


# Metadata-driven academic master data forms. SQL identifiers are fixed, never user supplied.

ENTITIES = {
    'teachers': (
        'teacher',
        'teacher_id',
        [
            ('first_name', 'First name', 'text'),
            ('last_name', 'Last name', 'text'),
            ('email', 'Email', 'email'),
            ('department', 'Department', 'text'),
            ('status', 'Status', 'status_select'),
            ('subject_id', 'Subject', 'select')
        ],
        {
            'subject_id': (
                'subject',
                'subject_id',
                'subject_name'
            )
        }
    ),

    'subjects': (
        'subject',
        'subject_id',
        [
            ('subject_code', 'Subject code', 'text'),
            ('subject_name', 'Subject name', 'text'),
            ('description', 'Description', 'text'),
            ('units', 'Units', 'number')
        ],
        {}
    ),

    'offerings': (
        'class_offering',
        'offering_id',
        [
            ('class_code', 'Class code', 'text'),
            ('schedule', 'Schedule', 'text'),
            ('section', 'Section', 'text'),
            ('school_year', 'School year', 'text'),
            ('semester', 'Semester', 'text'),
            ('room', 'Room', 'text'),
            ('teacher_id', 'Teacher', 'select')
        ],
        {
            'teacher_id': (
                'teacher',
                'teacher_id',
                'last_name'
            )
        }
    ),

    'enrollments': (
        'enrollment',
        'enrollment_id',
        [
            ('student_id', 'Student', 'select'),
            ('offering_id', 'Class offering', 'select'),
            ('enroll_date', 'Enrollment date', 'date'),
            ('status', 'Status', 'enrollment_status')
        ],
        {
            'student_id': (
                'student',
                'student_id',
                'last_name'
            ),
            'offering_id': (
                'class_offering',
                'offering_id',
                'class_code'
            )
        }
    ),
    
    'periods': (
        'grading_period',
        'period_id',
        [
            ('name', 'Period name', 'text'),
            ('start_date', 'Start date', 'date'),
            ('end_date', 'End date', 'date'),
            ('school_year', 'School year', 'text'),
            ('semester', 'Semester', 'text')
        ],
        {}
    ),

    'components': (
        'grade_component',
        'component_id',
        [
            ('grading_period_id', 'Grading period', 'select'),
            ('offering_id', 'Class offering', 'select'),
            ('name', 'Name', 'text'),
            ('type', 'Type', 'text'),
            ('max_score', 'Maximum score', 'number'),
            ('description', 'Description', 'text')
        ],
        {
            'grading_period_id': (
                'grading_period',
                'period_id',
                'name'
            ),
            'offering_id': (
                'class_offering',
                'offering_id',
                'class_code'
            )
        }
    ),

    'weights': (
        'grade_percentage',
        'percentage_id',
        [
            ('offering_id', 'Class offering', 'select'),
            ('component_type', 'Component type', 'text'),
            ('percentage', 'Weight %', 'number')
        ],
        {
            'offering_id': (
                'class_offering',
                'offering_id',
                'class_code'
            )
        }
    )
}


def entity_config(kind):
    if kind not in ENTITIES: abort(404)
    return ENTITIES[kind]

def entity_choices(cur, relations):
    choices={}
    for field,(table,pk,label) in relations.items():
        cur.execute(f'SELECT {pk} AS id,{label} AS label FROM {table} ORDER BY {label}')
        choices[field]=cur.fetchall()
    return choices

@app.get('/manage/<kind>')
def manage_list(kind):
    table,pk,fields,_=entity_config(kind)
    with get_db() as conn,conn.cursor() as cur:
        cur.execute(f'SELECT * FROM {table} ORDER BY {pk}')
        rows=cur.fetchall()
    return render_template('manage_list.html',kind=kind,pk=pk,fields=fields,rows=rows)

@app.route('/manage/<kind>/new', methods=['GET', 'POST'])
@app.route('/manage/<kind>/<record_id>/edit', methods=['GET', 'POST'])
def manage_form(kind, record_id=None):
    table, pk, fields, relations = entity_config(kind)

    with get_db() as conn, conn.cursor() as cur:

        if request.method == 'POST':

            values = []

            for field, label, field_type in fields:
                value = request.form.get(field, '').strip()

                # Normalize teacher status
                if kind == 'teachers' and field == 'status':
                    value = value.lower()

                values.append(value if value else None)

            try:
                if record_id:
                    sets = ', '.join(
                        f'{field}=%s'
                        for field, _, _ in fields
                    )

                    cur.execute(
                        f'UPDATE {table} SET {sets} WHERE {pk}=%s',
                        values + [record_id]
                    )

                else:
                    cols = ', '.join(
                        field for field, _, _ in fields
                    )

                    placeholders = ', '.join(
                        ['%s'] * (len(fields) + 1)
                    )

                    cur.execute(
                        f'INSERT INTO {table} ({pk}, {cols}) '
                        f'VALUES ({placeholders})',
                        [str(uuid4())] + values
                    )

                conn.commit()

                flash('Record saved successfully!', 'success')

                return redirect(
                    url_for('manage_list', kind=kind)
                )

            except (IntegrityError, ValueError):
                conn.rollback()
                app.logger.exception(
                    "Failed to save %s record", kind
                )
                flash(
                    'Unable to save record. Check the '
                    'required fields and database constraints.',
                    'error'
                )

        if record_id:
            cur.execute(
                f'SELECT * FROM {table} WHERE {pk}=%s',
                (record_id,)
            )

            row = cur.fetchone()

            if row is None:
                abort(404)

        else:
            row = {}

        choices = entity_choices(cur, relations)

    return render_template(
        'manage_form.html',
        kind=kind,
        fields=fields,
        row=row,
        choices=choices,
        editing=bool(record_id)
    )


@app.post('/manage/<kind>/<record_id>/delete')
def manage_delete(kind,record_id):
    table,pk,_,_=entity_config(kind)
    try:
        with get_db() as conn,conn.cursor() as cur:
            cur.execute(f'DELETE FROM {table} WHERE {pk}=%s',(record_id,))
        flash('Record deleted.','success')
    except IntegrityError:
        flash('Record is referenced by other academic data and cannot be deleted.','error')
    return redirect(url_for('manage_list',kind=kind))


@app.route('/scores', methods=['GET', 'POST'])
def scores():
    with get_db() as conn, conn.cursor() as cur:

        if request.method == 'POST':
            enrollment_id = request.form.get('enrollment_id')
            component_id = request.form.get('component_id')
            remarks = request.form.get('remarks', '').strip()

            try:
                score = Decimal(request.form.get('score', ''))

                # Find the selected grading component
                # and verify it belongs to the student's class.
                cur.execute("""
                    SELECT
                        gc.max_score,
                        gc.offering_id
                    FROM grade_component gc
                    JOIN enrollment e
                        ON e.offering_id = gc.offering_id
                    WHERE gc.component_id = %s
                      AND e.enrollment_id = %s
                """, (component_id, enrollment_id))

                component = cur.fetchone()

                if not component:
                    raise ValueError(
                        "The grading component does not belong "
                        "to the selected student's class."
                    )

                if not (
                    Decimal('0') <= score <=
                    Decimal(str(component['max_score']))
                ):
                    raise ValueError(
                        "Score must be between zero "
                        "and the component maximum."
                    )

                # Check whether a score already exists.
                cur.execute("""
                    SELECT score_id
                    FROM grade_component_score
                    WHERE enrollment_id = %s
                      AND component_id = %s
                    ORDER BY date_recorded DESC NULLS LAST
                    LIMIT 1
                """, (enrollment_id, component_id))

                existing_score = cur.fetchone()

                if existing_score:
                    cur.execute("""
                        UPDATE grade_component_score
                        SET score = %s,
                            remarks = %s,
                            date_recorded = CURRENT_TIMESTAMP
                        WHERE score_id = %s
                    """, (
                        score,
                        remarks,
                        existing_score['score_id']
                    ))
                else:
                    cur.execute("""
                        INSERT INTO grade_component_score (
                            score_id,
                            enrollment_id,
                            component_id,
                            score,
                            remarks,
                            date_recorded
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            CURRENT_TIMESTAMP
                        )
                    """, (
                        str(uuid4()),
                        enrollment_id,
                        component_id,
                        score,
                        remarks
                    ))

                conn.commit()
                flash('Score saved successfully!', 'success')

            except (ValueError, InvalidOperation, IntegrityError) as exc:
                conn.rollback()
                flash(f'Unable to save score: {exc}', 'error')

            return redirect(url_for('scores'))

        # Load student enrollments.
        cur.execute("""
            SELECT
                e.enrollment_id,
                s.first_name || ' ' || s.last_name ||
                ' - ' || co.class_code AS label
            FROM enrollment e
            JOIN student s
                ON e.student_id = s.student_id
            JOIN class_offering co
                ON e.offering_id = co.offering_id
            ORDER BY label
        """)
        enrollments = cur.fetchall()

        # Load grading components.
        cur.execute("""
            SELECT
                component_id,
                name,
                max_score,
                offering_id
            FROM grade_component
            ORDER BY name
        """)
        components = cur.fetchall()

        # Load grading periods.
        cur.execute("""
            SELECT period_id, name
            FROM grading_period
            ORDER BY name
        """)
        periods = cur.fetchall()

        # Load previously recorded scores.
        cur.execute("""
            SELECT
                sc.*,
                s.first_name,
                s.last_name,
                gc.name AS component_name,
                gp.name AS period_name
            FROM grade_component_score sc
            JOIN enrollment e
                ON sc.enrollment_id = e.enrollment_id
            JOIN student s
                ON e.student_id = s.student_id
            JOIN grade_component gc
                ON sc.component_id = gc.component_id
            JOIN grading_period gp
                ON gc.grading_period_id = gp.period_id
            ORDER BY sc.date_recorded DESC NULLS LAST
            LIMIT 100
        """)
        rows = cur.fetchall()

    return render_template(
        'scores.html',
        enrollments=enrollments,
        components=components,
        periods=periods,
        rows=rows
    )




@app.post('/grades/calculate')
def calculate_grades():
    enrollment_id = request.form.get('enrollment_id')
    period_id = request.form.get('period_id')

    if not enrollment_id or not period_id:
        flash('Select an enrollment and grading period.', 'error')
        return redirect(url_for('scores'))

    try:
        with get_db() as conn:
            with conn.cursor() as cur:

                # 1. Find the selected enrollment.
                cur.execute("""
                    SELECT offering_id
                    FROM enrollment
                    WHERE enrollment_id = %s
                """, (enrollment_id,))

                enrollment = cur.fetchone()

                if not enrollment:
                    raise ValueError('Enrollment not found.')

                offering_id = enrollment['offering_id']

                # 2. Validate the grading period.
                cur.execute("""
                    SELECT period_id
                    FROM grading_period
                    WHERE period_id = %s
                """, (period_id,))

                if not cur.fetchone():
                    raise ValueError('Grading period not found.')

                # 3. Load grading weights.
                cur.execute("""
                    SELECT component_type, percentage
                    FROM grade_percentage
                    WHERE offering_id = %s
                """, (offering_id,))

                weight_rows = cur.fetchall()

                if not weight_rows:
                    raise ValueError(
                        'No grading percentages configured.'
                    )

                weights = {}

                for row in weight_rows:
                    category = row['component_type'].strip().lower()

                    if category in weights:
                        raise ValueError(
                            f'Duplicate grading category: {category}'
                        )

                    weights[category] = Decimal(
                        str(row['percentage'])
                    )

                if sum(weights.values(), Decimal('0')) != Decimal('100'):
                    raise ValueError(
                        'Grading percentages must total 100%.'
                    )

                if any(weight <= 0 for weight in weights.values()):
                    raise ValueError(
                        'All grading percentages must be positive.'
                    )

                # 4. Load activities for the selected period.
                cur.execute("""
                    SELECT
                        c.component_id,
                        c.name,
                        c.type,
                        c.max_score,
                        sc.score
                    FROM grade_component c
                    LEFT JOIN LATERAL (
                        SELECT score
                        FROM grade_component_score
                        WHERE component_id = c.component_id
                          AND enrollment_id = %s
                        ORDER BY date_recorded DESC NULLS LAST,
                                 score_id DESC
                        LIMIT 1
                    ) sc ON TRUE
                    WHERE c.offering_id = %s
                      AND c.grading_period_id = %s
                    ORDER BY c.type, c.name
                """, (
                    enrollment_id,
                    offering_id,
                    period_id
                ))

                components = cur.fetchall()

                if not components:
                    raise ValueError(
                        'No grading activities found for this period.'
                    )

                # 5. Group scores by category.
                categories = {}

                for component in components:
                    category = component['type'].strip().lower()

                    if category not in weights:
                        raise ValueError(
                            f'No grading weight for: {category}'
                        )

                    if component['score'] is None:
                        raise ValueError(
                            f'Missing score for: {component["name"]}'
                        )

                    maximum = Decimal(
                        str(component['max_score'])
                    )

                    score = Decimal(
                        str(component['score'])
                    )

                    if maximum <= 0:
                        raise ValueError(
                            f'Invalid maximum score for: '
                            f'{component["name"]}'
                        )

                    if not Decimal('0') <= score <= maximum:
                        raise ValueError(
                            f'Invalid score for: {component["name"]}'
                        )

                    if category not in categories:
                        categories[category] = {
                            'earned': Decimal('0'),
                            'maximum': Decimal('0')
                        }

                    categories[category]['earned'] += score
                    categories[category]['maximum'] += maximum

                missing = set(weights) - set(categories)

                if missing:
                    raise ValueError(
                        'Missing activities for: '
                        + ', '.join(sorted(missing))
                    )

                # 6. Calculate weighted period grade.
                final_grade = Decimal('0')

                for category, totals in categories.items():
                    final_grade += (
                        totals['earned'] / totals['maximum']
                    ) * weights[category]

                final_grade = final_grade.quantize(
                    Decimal('0.01'),
                    rounding=ROUND_HALF_UP
                )

                # 7. Save INSIDE the active connection.
                # The unique index prevents duplicate
                # grades for the same enrollment and period.
                cur.execute("""
                    INSERT INTO grade (
                        grade_id,
                        enrollment_id,
                        period_id,
                        final_grade,
                        remarks,
                        date_encoded
                    )
                    VALUES (
                        %s, %s, %s, %s,
                        'Calculated', CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (enrollment_id, period_id)
                    WHERE period_id IS NOT NULL
                    DO UPDATE SET
                        final_grade = EXCLUDED.final_grade,
                        remarks = EXCLUDED.remarks,
                        date_encoded = CURRENT_TIMESTAMP
                """, (
                    str(uuid4()),
                    enrollment_id,
                    period_id,
                    final_grade
                ))

            # Commit after all database operations succeed.
            conn.commit()

        flash(
            f'Grade calculated and saved: {final_grade}%',
            'success'
        )
        return redirect(url_for('grades'))

    except (ValueError, InvalidOperation, IntegrityError) as exc:
        app.logger.exception('Grade calculation failed')
        flash(f'Cannot calculate grade: {exc}', 'error')
        return redirect(url_for('scores'))

    except Exception:
        app.logger.exception('Unexpected grade calculation error')
        flash(
            'Could not calculate grade. Check the VS Code terminal.',
            'error'
        )
        return redirect(url_for('scores'))


# ==========================================
# OVERALL SUBJECT GRADE CALCULATOR
# ==========================================

@app.route("/grades/overall")
def overall_grades():
    with get_db() as conn, conn.cursor() as cur:

        # Retrieve every enrollment, including
        # those without calculated period grades.
        cur.execute("""
            SELECT
                e.enrollment_id,
                s.student_id,
                s.first_name,
                s.last_name,
                co.class_code,
                sub.subject_code,
                sub.subject_name
            FROM enrollment e
            JOIN student s
                ON s.student_id = e.student_id
            JOIN class_offering co
                ON co.offering_id = e.offering_id
            JOIN teacher t
                ON t.teacher_id = co.teacher_id
            JOIN subject sub
                ON sub.subject_id = t.subject_id
            ORDER BY s.last_name, s.first_name,
                     sub.subject_name
        """)

        enrollments = cur.fetchall()

        # Fetch saved period grades.
        cur.execute("""
            SELECT
                g.enrollment_id,
                g.period_id,
                gp.name AS period_name,
                g.final_grade
            FROM grade g
            JOIN grading_period gp
                ON gp.period_id = g.period_id
            ORDER BY gp.start_date, gp.name
        """)

        saved_grades = cur.fetchall()

        # Fetch available grading periods.
        cur.execute("""
            SELECT
                period_id,
                name,
                school_year,
                semester
            FROM grading_period
            ORDER BY start_date, name
        """)

        periods = cur.fetchall()

    # Group grades by enrollment.
    grades_by_enrollment = {}

    for grade in saved_grades:
        enrollment_id = grade["enrollment_id"]

        grades_by_enrollment.setdefault(
            enrollment_id, []
        ).append(grade)

    results = []

    for enrollment in enrollments:
        enrollment_id = enrollment["enrollment_id"]

        student_grades = grades_by_enrollment.get(
            enrollment_id, []
        )

        values = [
            Decimal(str(g["final_grade"]))
            for g in student_grades
        ]

        overall = None

        if values:
            overall = (
                sum(values) / Decimal(len(values))
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

        # Count only grading periods with
        # an actual saved grade.
        results.append({
            "student_id": enrollment["student_id"],
            "student_name": (
                f'{enrollment["first_name"]} '
                f'{enrollment["last_name"]}'
            ),
            "subject_code": enrollment["subject_code"],
            "subject_name": enrollment["subject_name"],
            "class_code": enrollment["class_code"],
            "period_grades": student_grades,
            "period_count": len(student_grades),
            "overall_grade": overall
        })

    return render_template(
        "overall_grades.html",
        results=results,
        periods=periods
    )


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG','false').lower() == 'true')
