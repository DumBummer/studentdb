# StudentDB — Student Grade Management System

Flask + PostgreSQL web application using Python, HTML templates, and CSS, based on the supplied UML class diagram.

## Included
- Dashboard counts for students, subjects, class offerings, and grade records
- Student directory: create, search, edit, delete
- Grade/transcript listing joined to student, enrollment, class offering, subject, and grading period
- PostgreSQL schema for all UML academic entities
- `/health` endpoint for database connectivity
- Weighted grade calculation helper in `services/grading_service.py`

## Setup (Windows PowerShell)
1. Install PostgreSQL and create the database: `CREATE DATABASE studentdb;`
2. Create/activate a Python environment: `py -m venv .venv` then `\.venv\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`, set your database password, then load environment variables in PowerShell or use a dotenv loader. For example, set `$env:DB_PASSWORD='your_password'` before starting.
5. Run schema: `psql -U postgres -d studentdb -f schema.sql`
6. Start the application: `python app.py`
7. Open `http://127.0.0.1:5000`; test database at `/health`.

## Important
The current phase has full student CRUD and grade viewing. Teacher/subject/class-offering/enrollment/grading-period/component CRUD, score entry, grade encoding, authentication and role permissions remain follow-up work. Do not commit real student information or credentials. The app is a development starter, not production-hardened.

## Expanded academic modules
Teacher, Subject, Class Offering, Enrollment, Grading Period, Grade Component, and Weight setup now support add/edit/delete. Score encoding supports updates and final grade calculation when all configured weights sum to 100%. Configure weights per period before encoding grades.

**Important:** This is a local development prototype, not production-ready for real student records. Authentication, authorization, CSRF protection, auditing, and stronger validation are required before deployment. Grade weights currently apply per grading period globally (as the supplied UML models them), not per subject.
