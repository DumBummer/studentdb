import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from db import get_db
from decimal import Decimal
from uuid import uuid4
from psycopg import IntegrityError
from services.grading_service import calculate_final_grade
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'change-this-development-key')

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

@app.route('/students/new', methods=['GET','POST'])
def student_new():
    if request.method == 'POST':
        data = [request.form.get(k,'').strip() for k in ('student_id','first_name','last_name','email','program','status')]
        if not all(data[:3]):
            flash('Student ID, first name, and last name are required.','error')
            return render_template('student_form.html', student=request.form, editing=False)
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute('INSERT INTO student(student_id,first_name,last_name,email,program,status) VALUES(%s,%s,%s,%s,%s,%s)', (*data[:5], data[5] or 'Active'))
            flash('Student added successfully.','success')
            return redirect(url_for('students'))
        except Exception:
            flash('Could not save student. Check whether the student ID or email already exists.','error')
            return render_template('student_form.html', student=request.form, editing=False)
    return render_template('student_form.html', student={}, editing=False)

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
            cur.execute('''SELECT g.grade_id,g.final_grade,g.remarks,g.date_encoded,s.student_id,s.first_name,s.last_name,sub.subject_code,sub.subject_name,gp.name AS period_name FROM grade g JOIN enrollment e ON e.enrollment_id=g.enrollment_id JOIN student s ON s.student_id=e.student_id JOIN class_offering co ON co.offering_id=e.offering_id JOIN subject sub ON sub.subject_id=co.subject_id JOIN grading_period gp ON gp.period_id=g.period_id ORDER BY g.date_encoded DESC NULLS LAST''')
            rows = cur.fetchall()
    return render_template('grades.html', rows=rows)

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
 'teachers': ('teacher','teacher_id',[('first_name','First name','text'),('last_name','Last name','text'),('email','Email','email'),('department','Department','text'),('status','Status','text')],{}),
 'subjects': ('subject','subject_id',[('subject_code','Subject code','text'),('subject_name','Subject name','text'),('description','Description','text'),('units','Units','number')],{}),
 'offerings': ('class_offering','offering_id',[('class_code','Class code','text'),('schedule','Schedule','text'),('section','Section','text'),('school_year','School year','text'),('semester','Semester','text'),('room','Room','text'),('subject_id','Subject','select'),('teacher_id','Teacher','select')],{'subject_id':('subject','subject_id','subject_name'),'teacher_id':('teacher','teacher_id','last_name')}),
 'enrollments': ('enrollment','enrollment_id',[('student_id','Student','select'),('offering_id','Class offering','select'),('enroll_date','Enrollment date','date'),('status','Status','text')],{'student_id':('student','student_id','last_name'),'offering_id':('class_offering','offering_id','class_code')}),
 'periods': ('grading_period','period_id',[('name','Period name','text'),('start_date','Start date','date'),('end_date','End date','date'),('school_year','School year','text'),('semester','Semester','text')],{}),
 'components': ('grade_component','component_id',[('name','Name','text'),('type','Type','text'),('max_score','Maximum score','number'),('description','Description','text')],{}),
 'weights': ('grade_percentage','percentage_id',[('component_id','Component','select'),('period_id','Period','select'),('percentage','Weight %','number')],{'component_id':('grade_component','component_id','name'),'period_id':('grading_period','period_id','name')})
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

@app.route('/manage/<kind>/new',methods=['GET','POST'])
@app.route('/manage/<kind>/<record_id>/edit',methods=['GET','POST'])
def manage_form(kind,record_id=None):
    table,pk,fields,relations=entity_config(kind)
    with get_db() as conn,conn.cursor() as cur:
        if request.method=='POST':
            values=[request.form.get(field) or None for field,_,_ in fields]
            try:
                if record_id:
                    sets=','.join(f'{field}=%s' for field,_,_ in fields)
                    cur.execute(f'UPDATE {table} SET {sets} WHERE {pk}=%s',values+[record_id])
                else:
                    cols=','.join(field for field,_,_ in fields)
                    placeholders=','.join(['%s']*(len(fields)+1))
                    cur.execute(f'INSERT INTO {table} ({pk},{cols}) VALUES ({placeholders})',[str(uuid4())]+values)
                conn.commit()
                flash('Record saved.','success')
                return redirect(url_for('manage_list',kind=kind))
            except (IntegrityError,ValueError) as exc:
                conn.rollback()
                flash(f'Unable to save: {exc}', 'error')
        if record_id:
            cur.execute(f'SELECT * FROM {table} WHERE {pk}=%s',(record_id,))
            row=cur.fetchone()
            if row is None: abort(404)
        else: row={}
        choices=entity_choices(cur,relations)
    return render_template('manage_form.html',kind=kind,fields=fields,row=row,choices=choices,editing=bool(record_id))

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

@app.route('/scores',methods=['GET','POST'])
def scores():
    with get_db() as conn,conn.cursor() as cur:
        if request.method=='POST':
            enrollment_id=request.form.get('enrollment_id')
            component_id=request.form.get('component_id')
            period_id=request.form.get('period_id')
            try:
                score=Decimal(request.form.get('score',''))
                cur.execute('SELECT max_score FROM grade_component WHERE component_id=%s',(component_id,))
                component=cur.fetchone()
                if not component or not (Decimal('0')<=score<=component['max_score']):
                    raise ValueError('Score must be between zero and component maximum.')
                cur.execute('''INSERT INTO grade_component_score(score_id,enrollment_id,component_id,period_id,score,remarks)
                    VALUES(%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(enrollment_id,component_id,period_id) DO UPDATE SET score=EXCLUDED.score,remarks=EXCLUDED.remarks,date_recorded=CURRENT_TIMESTAMP''',
                    (str(uuid4()),enrollment_id,component_id,period_id,score,request.form.get('remarks','')))
                conn.commit(); flash('Score saved.','success')
            except (ValueError,IntegrityError) as exc:
                conn.rollback();flash(f'Invalid score: {exc}','error')
            return redirect(url_for('scores'))
        cur.execute('''SELECT e.enrollment_id,s.first_name||' '||s.last_name||' · '||co.class_code label FROM enrollment e JOIN student s USING(student_id) JOIN class_offering co USING(offering_id) ORDER BY label''')
        enrollments=cur.fetchall()
        cur.execute('SELECT component_id,name,max_score FROM grade_component ORDER BY name');components=cur.fetchall()
        cur.execute('SELECT period_id,name FROM grading_period ORDER BY name');periods=cur.fetchall()
        cur.execute('''SELECT sc.*,s.first_name,s.last_name,c.name component_name,p.name period_name FROM grade_component_score sc JOIN enrollment e USING(enrollment_id) JOIN student s USING(student_id) JOIN grade_component c USING(component_id) JOIN grading_period p USING(period_id) ORDER BY sc.date_recorded DESC LIMIT 100''')
        rows=cur.fetchall()
    return render_template('scores.html',enrollments=enrollments,components=components,periods=periods,rows=rows)

@app.post('/grades/calculate')
def calculate_grades():
    enrollment_id=request.form.get('enrollment_id');period_id=request.form.get('period_id')
    with get_db() as conn,conn.cursor() as cur:
        cur.execute('''SELECT sc.score,c.max_score,gp.percentage FROM grade_component_score sc
            JOIN grade_component c USING(component_id)
            JOIN grade_percentage gp ON gp.component_id=sc.component_id AND gp.period_id=sc.period_id
            WHERE sc.enrollment_id=%s AND sc.period_id=%s''',(enrollment_id,period_id))
        rows=cur.fetchall()
        cur.execute('SELECT COALESCE(SUM(percentage),0) total FROM grade_percentage WHERE period_id=%s',(period_id,))
        configured=cur.fetchone()['total']
        actual=sum((r['percentage'] for r in rows),Decimal('0'))
        if not rows or configured!=100 or actual!=100:
            flash('Cannot calculate: period weights must total 100% and every weighted component must have a score.','error')
            return redirect(url_for('scores'))
        grade=calculate_final_grade(rows)
        cur.execute('''INSERT INTO grade(grade_id,enrollment_id,period_id,final_grade,remarks) VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT(enrollment_id,period_id) DO UPDATE SET final_grade=EXCLUDED.final_grade,remarks=EXCLUDED.remarks,date_encoded=CURRENT_TIMESTAMP''',
            (str(uuid4()),enrollment_id,period_id,grade,'Calculated'))
    flash(f'Final grade calculated: {grade}','success')
    return redirect(url_for('grades'))

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG','false').lower() == 'true')
