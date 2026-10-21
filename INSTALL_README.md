# StudentDB Retro OS — Academic Tabs Completion

## Safety and compatibility
This package contains **desktop.py** and the **desktop_app/** folder only. It does not include or modify `.env`, `db.py`, `app.py`, `schema.sql`, Flask templates, or your PostgreSQL data. It was checked for Python syntax but **cannot be live-tested against your private database**. Make a backup of your current `desktop_app` directory before copying.

## Installation (Windows PowerShell in your existing studentdb repository)

1. Close the desktop program.
2. Backup: `Copy-Item .\desktop_app .\desktop_app_backup -Recurse`
3. Extract this ZIP somewhere outside your project. Copy its `desktop_app` folder and `desktop.py` into the root of `studentdb`, replacing the desktop files only.
4. Install PySide6 if needed: `.\.venv\Scripts\python.exe -m pip install PySide6 python-dotenv psycopg[binary]`
5. Run: `.\.venv\Scripts\python.exe desktop.py`

## Connected tabs
Dashboard, Students, Teachers, Subjects, Class Offerings, Enrollments, Grading Periods, Grade Components, Score Encoding, Grades & Transcripts, Overall Grades, Grade Weights.

**Grade Weights** is an additional tab for setting up the weights required by the grade calculator. The form adapts to existing columns in your database.

## Test in order
1. Dashboard and Students: confirm the original records still appear.
2. Subjects and Teachers: use Refresh; confirm existing records show. Test adding a disposable record only if comfortable doing so.
3. Class Offerings, Enrollments, Grading Periods, Grade Components, Grade Weights: configure the data required for grading.
4. Score Encoding: enter a score within its component maximum. Re-entering the same enrollment/component/period updates its score.
5. Calculate Period Grade: requires configured weights totaling 100%, and all required scores. It writes a grade record.
6. Grades & Transcripts and Overall Grades: click Refresh to view saved grades and arithmetic mean across saved grading periods.

## Notes
- Database tables differ across earlier versions of StudentDB. The generic forms discover actual table columns and display PostgreSQL errors if a required field is missing. Send the **exact error text** for targeted adjustments.
- The **Overall Grades** tab computes the unweighted mean of available saved period grades. If your school has a custom period-weighting rule, this must be adjusted.
- This is a **local development prototype**. Before using real student information in production, implement authentication, authorization, auditing, backups and input validation.
- No migrations, DROP TABLE, DELETE ALL or database resets are performed by installation. Individual Delete buttons intentionally delete the selected record after confirmation.
- For reliable text display, the global GUI font is Consolas. Your Minecraftia font file is not included or distributed. It can be tested on specific headings later.
