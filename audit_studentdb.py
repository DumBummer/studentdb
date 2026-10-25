"""Read-only PostgreSQL schema audit for CSPC 103 StudentDB.
Run from the inner studentdb project root: python audit_studentdb.py
No records are inserted, changed or deleted.
"""
from db import get_db

EXPECTED = {
    'student': ['student_id','first_name','last_name','email','program','year_level','status'],
    'teacher': ['teacher_id','first_name','last_name','email','department','status'],
    'subject': ['subject_id','subject_code','subject_name','description','units'],
    'class_offering': ['offering_id','class_code','subject_id','teacher_id','section','school_year','semester','schedule','room'],
    'enrollment': ['enrollment_id','student_id','offering_id','enroll_date','status'],
    'grading_period': ['period_id','name','period_order','start_date','end_date','school_year','semester'],
    'grade_component': ['component_id','grading_period_id','name','type','max_score','description'],
    'grade_percentage': ['percentage_id','offering_id','component_id','percentage'],
    'grade_component_score': ['score_id','enrollment_id','component_id','score','remarks','date_recorded'],
    'grade': ['grade_id','enrollment_id','midterm_grade','finals_grade','overall_grade','midterm_equiv','final_equiv','remarks','date_encoded'],
    'audit_log': ['log_id','table_name','record_id','action','old_value','new_value','changed_by','changed_at'],
}
FINAL_COUNTS = {'student':5,'teacher':2,'subject':2,'class_offering':2,'enrollment':4,
                'grading_period':2,'grade_component':6,'grade_percentage':12,
                'grade_component_score':24,'grade':4}


def main():
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT current_database() AS db, inet_server_port() AS port')
        info = cur.fetchone()
        print(f"StudentDB READ-ONLY AUDIT | Database: {info['db']} | Port: {info['port']}")
        cur.execute('''SELECT table_name, column_name, data_type FROM information_schema.columns
                       WHERE table_schema=current_schema() ORDER BY table_name, ordinal_position''')
        schemas = {}
        for row in cur.fetchall():
            schemas.setdefault(row['table_name'], {})[row['column_name']] = row['data_type']
        print('\nSCHEMA COMPARISON (guide -> your database)')
        for table, required in EXPECTED.items():
            actual = schemas.get(table)
            if actual is None:
                print(f'  MISSING TABLE: {table}')
                continue
            missing = [x for x in required if x not in actual]
            print(f"  {table}: {'MATCHING COLUMNS' if not missing else 'MISSING: ' + ', '.join(missing)}")
            if table == 'teacher':
                print('    teacher_id type:', actual.get('teacher_id'))
        print('\nCURRENT ROW COUNTS (guide targets apply ONLY after all 52 tests, in order)')
        for table, expected in FINAL_COUNTS.items():
            if table not in schemas:
                continue
            cur.execute(f'SELECT COUNT(*) AS total FROM "{table}"')
            actual = cur.fetchone()['total']
            print(f'  {table}: current={actual}; end-of-guide target={expected}')
        if 'audit_log' in schemas:
            cur.execute('SELECT COUNT(*) AS total FROM audit_log')
            print('  audit_log: current=', cur.fetchone()['total'], '; end-of-guide target >=7')
        print('\nCHECK CONSTRAINTS')
        cur.execute('''SELECT c.relname AS table_name, pg_get_constraintdef(k.oid) AS rule
                       FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
                       JOIN pg_namespace n ON n.oid=c.relnamespace
                       WHERE n.nspname=current_schema() AND k.contype='c'
                       ORDER BY c.relname''')
        for row in cur.fetchall():
            print(f"  {row['table_name']}: {row['rule']}")
        print('\nNo data was changed. Differences indicate items to inspect, not automatic migration instructions.')


if __name__ == '__main__':
    main()
