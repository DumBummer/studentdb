--
-- PostgreSQL database dump
--

\restrict WQ8XlfvLM7Arz8dr8fkYBngha21R0mLoZehRnQ2Ch9qsOcwaP7KVnuw5RaKXDGY

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

-- Started on 2026-10-21 13:11:44

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 232 (class 1255 OID 49993)
-- Name: studentdb_audit_row(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.studentdb_audit_row() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
DECLARE
    id_column TEXT := TG_ARGV[0];
    before_row JSONB;
    after_row JSONB;
    row_identifier TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        before_row := NULL;
        after_row := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        before_row := to_jsonb(OLD);
        after_row := to_jsonb(NEW);
        IF before_row = after_row THEN
            RETURN NEW;
        END IF;
    ELSE
        before_row := to_jsonb(OLD);
        after_row := NULL;
    END IF;

    row_identifier := COALESCE(after_row ->> id_column, before_row ->> id_column);
    IF row_identifier IS NULL THEN
        RAISE EXCEPTION 'Audit key % missing in table %', id_column, TG_TABLE_NAME;
    END IF;

    INSERT INTO public.audit_log
        (table_name, record_id, action, old_data, new_data, changed_by)
    VALUES
        (TG_TABLE_NAME, row_identifier, TG_OP, before_row, after_row, session_user);

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.studentdb_audit_row() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 231 (class 1259 OID 49980)
-- Name: audit_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_log (
    audit_id bigint NOT NULL,
    table_name text NOT NULL,
    record_id text NOT NULL,
    action text NOT NULL,
    old_data jsonb,
    new_data jsonb,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by text
);


ALTER TABLE public.audit_log OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 49979)
-- Name: audit_log_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.audit_log ALTER COLUMN audit_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.audit_log_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 222 (class 1259 OID 16650)
-- Name: class_offering; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.class_offering (
    offering_id text NOT NULL,
    class_code text NOT NULL,
    schedule text,
    section text,
    school_year text NOT NULL,
    semester text NOT NULL,
    room text,
    teacher_id text NOT NULL,
    subject_id text
);


ALTER TABLE public.class_offering OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16683)
-- Name: enrollment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.enrollment (
    enrollment_id text NOT NULL,
    student_id text NOT NULL,
    offering_id text NOT NULL,
    enroll_date date DEFAULT CURRENT_DATE NOT NULL,
    status text DEFAULT 'enrolled'::text NOT NULL,
    CONSTRAINT enrollment_status_check CHECK ((status = ANY (ARRAY['enrolled'::text, 'dropped'::text, 'completed'::text])))
);


ALTER TABLE public.enrollment OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 16783)
-- Name: grade; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.grade (
    grade_id text NOT NULL,
    enrollment_id text NOT NULL,
    final_grade numeric(6,2) NOT NULL,
    remarks text,
    date_encoded date DEFAULT CURRENT_DATE NOT NULL,
    period_id text,
    midterm_grade numeric(7,2),
    finals_grade numeric(7,2),
    overall_grade numeric(7,2),
    midterm_equiv numeric(3,2),
    final_equiv numeric(3,2),
    CONSTRAINT grade_final_grade_check CHECK ((final_grade >= (0)::numeric))
);


ALTER TABLE public.grade OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 49729)
-- Name: grade_backup_before_period_migration; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.grade_backup_before_period_migration (
    grade_id text,
    enrollment_id text,
    final_grade numeric(6,2),
    remarks text,
    date_encoded date
);


ALTER TABLE public.grade_backup_before_period_migration OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 16710)
-- Name: grade_component; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.grade_component (
    component_id text NOT NULL,
    grading_period_id text NOT NULL,
    offering_id text,
    name text NOT NULL,
    type text NOT NULL,
    max_score numeric(6,2) NOT NULL,
    description text,
    CONSTRAINT grade_component_max_score_check CHECK ((max_score > (0)::numeric))
);


ALTER TABLE public.grade_component OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 16755)
-- Name: grade_component_score; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.grade_component_score (
    score_id text NOT NULL,
    enrollment_id text NOT NULL,
    component_id text NOT NULL,
    score numeric(6,2) NOT NULL,
    remarks text,
    date_recorded date DEFAULT CURRENT_DATE NOT NULL,
    CONSTRAINT grade_component_score_score_check CHECK ((score >= (0)::numeric))
);


ALTER TABLE public.grade_component_score OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16735)
-- Name: grade_percentage; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.grade_percentage (
    percentage_id text NOT NULL,
    offering_id text NOT NULL,
    component_type text NOT NULL,
    percentage numeric(5,2) NOT NULL,
    CONSTRAINT grade_percentage_percentage_check CHECK (((percentage >= (0)::numeric) AND (percentage <= (100)::numeric)))
);


ALTER TABLE public.grade_percentage OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 16669)
-- Name: grading_period; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.grading_period (
    period_id text NOT NULL,
    name text NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    school_year text NOT NULL,
    semester text NOT NULL,
    period_order integer,
    CONSTRAINT grading_period_check CHECK ((end_date >= start_date))
);


ALTER TABLE public.grading_period OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16598)
-- Name: student; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.student (
    student_id text NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    email text NOT NULL,
    program text,
    status text DEFAULT 'active'::text NOT NULL,
    year_level character varying(20) DEFAULT '1st Year'::character varying,
    CONSTRAINT student_status_check CHECK ((status = ANY (ARRAY['Active'::text, 'Inactive'::text, 'Enrolled'::text, 'Graduated'::text])))
);


ALTER TABLE public.student OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16630)
-- Name: subject; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.subject (
    subject_id text NOT NULL,
    subject_code text NOT NULL,
    subject_name text NOT NULL,
    description text,
    units integer NOT NULL,
    CONSTRAINT subject_units_check CHECK ((units > 0))
);


ALTER TABLE public.subject OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 16614)
-- Name: teacher; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.teacher (
    teacher_id text NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    email text NOT NULL,
    department text,
    status text DEFAULT 'active'::text NOT NULL,
    subject_id text NOT NULL,
    CONSTRAINT teacher_status_check CHECK ((status = ANY (ARRAY['Active'::text, 'Inactive'::text])))
);


ALTER TABLE public.teacher OWNER TO postgres;

--
-- TOC entry 5140 (class 0 OID 49980)
-- Dependencies: 231
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.audit_log (audit_id, table_name, record_id, action, old_data, new_data, changed_at, changed_by) FROM stdin;
4	student	2026-0002	UPDATE	{"email": "pr@gmail.com", "status": "Active", "program": "BSCS", "last_name": "Reyes", "first_name": "Pedro", "student_id": "2026-0002", "year_level": "2nd Year"}	{"email": "dpr@gmail.com", "status": "Active", "program": "BSCS", "last_name": "Reyes", "first_name": "Pedro", "student_id": "2026-0002", "year_level": "2nd Year"}	2026-10-21 12:45:00.903602+08	postgres
\.


--
-- TOC entry 5131 (class 0 OID 16650)
-- Dependencies: 222
-- Data for Name: class_offering; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.class_offering (offering_id, class_code, schedule, section, school_year, semester, room, teacher_id, subject_id) FROM stdin;
729af011-47ad-4fbe-813f-05ffec68166e	CSPC103	MWF 9:00-10:00	A	2026-2027	1STS SEM	CS-201	T-1001	09416200-52e2-4c7e-bf0e-cd0d9f5fc395
\.


--
-- TOC entry 5133 (class 0 OID 16683)
-- Dependencies: 224
-- Data for Name: enrollment; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.enrollment (enrollment_id, student_id, offering_id, enroll_date, status) FROM stdin;
1d8daeb6-d79c-4db4-92f8-5386af0ee260	2026-0001	729af011-47ad-4fbe-813f-05ffec68166e	2026-08-01	enrolled
72d13d0e-f6b7-4148-8d1b-822c27a53ffa	2026-0003	729af011-47ad-4fbe-813f-05ffec68166e	2026-08-01	enrolled
b28b8eb6-ec78-4390-a86b-e878693535c9	2026-0004	729af011-47ad-4fbe-813f-05ffec68166e	2026-08-02	enrolled
7f50ec77-1cdc-4c0f-9a4c-4998e2ca272a	2026-0099	729af011-47ad-4fbe-813f-05ffec68166e	2026-08-02	enrolled
650a6675-e85b-4112-98e9-99132f519148	2026-0002	729af011-47ad-4fbe-813f-05ffec68166e	2026-08-04	enrolled
\.


--
-- TOC entry 5137 (class 0 OID 16783)
-- Dependencies: 228
-- Data for Name: grade; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.grade (grade_id, enrollment_id, final_grade, remarks, date_encoded, period_id, midterm_grade, finals_grade, overall_grade, midterm_equiv, final_equiv) FROM stdin;
59159e61-9c75-43d4-a768-217197a69bc1	1d8daeb6-d79c-4db4-92f8-5386af0ee260	80.50	Calculated	2026-10-21	2819b622-15a2-492e-80d3-e8bd323c15b2	80.50	83.50	82.30	2.50	2.25
15e3dfa3-f1a1-4545-91fb-a97d403c2634	1d8daeb6-d79c-4db4-92f8-5386af0ee260	83.50	Calculated	2026-10-21	86e95666-0bdf-4901-aa2e-61449b7b6a2f	80.50	83.50	82.30	2.50	2.25
\.


--
-- TOC entry 5138 (class 0 OID 49729)
-- Dependencies: 229
-- Data for Name: grade_backup_before_period_migration; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.grade_backup_before_period_migration (grade_id, enrollment_id, final_grade, remarks, date_encoded) FROM stdin;
605505dc-c0c7-4e91-beee-b0ffeb0a16bd	67be3ced-db71-4a2e-91c3-7f55c4464e58	85.70	Calculated	2026-10-19
\.


--
-- TOC entry 5134 (class 0 OID 16710)
-- Dependencies: 225
-- Data for Name: grade_component; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.grade_component (component_id, grading_period_id, offering_id, name, type, max_score, description) FROM stdin;
2c82d52a-a871-46b8-ae80-3ffc9e7e0d42	86e95666-0bdf-4901-aa2e-61449b7b6a2f	729af011-47ad-4fbe-813f-05ffec68166e	Final Examination	Examination	100.00	Finals
0308544e-5a8d-4114-88ca-103abc145b19	86e95666-0bdf-4901-aa2e-61449b7b6a2f	729af011-47ad-4fbe-813f-05ffec68166e	Final Lab/Project	Project	100.00	Finals
1c6346fe-f13e-46af-beb2-63c5803efbfa	2819b622-15a2-492e-80d3-e8bd323c15b2	729af011-47ad-4fbe-813f-05ffec68166e	Midterm Lab/Project	Project	100.00	Midterm
26ec10fe-6257-4779-9cac-c89df3121bfc	2819b622-15a2-492e-80d3-e8bd323c15b2	729af011-47ad-4fbe-813f-05ffec68166e	Midterm Examination	Exam	100.00	Midterm
6ff7e42d-7633-4a85-8ad4-41d6075db695	86e95666-0bdf-4901-aa2e-61449b7b6a2f	729af011-47ad-4fbe-813f-05ffec68166e	Final Quiz	Quiz	50.00	Finals
7e7e75f4-10b2-4c11-a10b-a01dc10d5e64	2819b622-15a2-492e-80d3-e8bd323c15b2	729af011-47ad-4fbe-813f-05ffec68166e	Midterm Quiz	Quiz	50.00	Midterm
\.


--
-- TOC entry 5136 (class 0 OID 16755)
-- Dependencies: 227
-- Data for Name: grade_component_score; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.grade_component_score (score_id, enrollment_id, component_id, score, remarks, date_recorded) FROM stdin;
c57b46b6-4798-47db-bd8a-03436515f1fd	1d8daeb6-d79c-4db4-92f8-5386af0ee260	7e7e75f4-10b2-4c11-a10b-a01dc10d5e64	40.00	A	2026-10-20
5a16cc2b-9785-4a1b-a3a5-81b6d484958a	1d8daeb6-d79c-4db4-92f8-5386af0ee260	1c6346fe-f13e-46af-beb2-63c5803efbfa	90.00	A	2026-10-20
468274ab-008c-4399-8951-642e96f2381f	1d8daeb6-d79c-4db4-92f8-5386af0ee260	26ec10fe-6257-4779-9cac-c89df3121bfc	75.00	B-	2026-10-20
f6191bbd-74b7-44a3-bd7f-75aadd8b84f2	1d8daeb6-d79c-4db4-92f8-5386af0ee260	6ff7e42d-7633-4a85-8ad4-41d6075db695	45.00	A	2026-10-20
2566d2f8-8360-4d5d-9e1f-5fed9305b165	1d8daeb6-d79c-4db4-92f8-5386af0ee260	0308544e-5a8d-4114-88ca-103abc145b19	85.00	A-	2026-10-20
c8612aee-209c-4f67-9a1a-17afeb32f1e9	1d8daeb6-d79c-4db4-92f8-5386af0ee260	2c82d52a-a871-46b8-ae80-3ffc9e7e0d42	80.00	A-	2026-10-20
\.


--
-- TOC entry 5135 (class 0 OID 16735)
-- Dependencies: 226
-- Data for Name: grade_percentage; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.grade_percentage (percentage_id, offering_id, component_type, percentage) FROM stdin;
9890afd3-015c-48d1-a41c-90e7d9624416	729af011-47ad-4fbe-813f-05ffec68166e	Midterm Quiz	20.00
b72375fd-1e99-4b21-bdd4-9184575c77fc	729af011-47ad-4fbe-813f-05ffec68166e	Midterm Laboratory/Project	30.00
74484050-b4c0-4dc3-a585-112aa01d26c6	729af011-47ad-4fbe-813f-05ffec68166e	Midterm Examination	50.00
a5410155-cc38-4c84-b77d-956656cd80e5	729af011-47ad-4fbe-813f-05ffec68166e	Final Quiz	20.00
88e825df-0b8d-48e2-ad8d-10bf3c256018	729af011-47ad-4fbe-813f-05ffec68166e	Final Laboratory/Project	30.00
f7f00eea-3658-4a97-b39f-e7b6adbf1b92	729af011-47ad-4fbe-813f-05ffec68166e	Final Examination	50.00
\.


--
-- TOC entry 5132 (class 0 OID 16669)
-- Dependencies: 223
-- Data for Name: grading_period; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.grading_period (period_id, name, start_date, end_date, school_year, semester, period_order) FROM stdin;
2819b622-15a2-492e-80d3-e8bd323c15b2	Midterm	2026-07-01	2026-10-19	2026-2027	1st sem	1
86e95666-0bdf-4901-aa2e-61449b7b6a2f	Finals	2026-09-28	2026-10-24	2026-2027	1st sem	2
\.


--
-- TOC entry 5128 (class 0 OID 16598)
-- Dependencies: 219
-- Data for Name: student; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.student (student_id, first_name, last_name, email, program, status, year_level) FROM stdin;
2026-0003	Ana	Garcia	aG@gmail.com	BSIT	Active	2nd Year
2026-0004	Kevin	O'Brien	kob@gmail.com	BSIT	Enrolled	1st Year
2026-0001	Juan	Dela Cruz	JDC@GMAIL.COM	BSCS	Active	2nd Year
2026-0099	Lea	Ramos	Ramming@gmail.com	BSIT	Inactive	1st Year
2026-0002	Pedro	Reyes	dpr@gmail.com	BSCS	Active	2nd Year
\.


--
-- TOC entry 5130 (class 0 OID 16630)
-- Dependencies: 221
-- Data for Name: subject; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.subject (subject_id, subject_code, subject_name, description, units) FROM stdin;
09416200-52e2-4c7e-bf0e-cd0d9f5fc395	CSPC103	CSPC103	OOP	3
\.


--
-- TOC entry 5129 (class 0 OID 16614)
-- Dependencies: 220
-- Data for Name: teacher; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.teacher (teacher_id, first_name, last_name, email, department, status, subject_id) FROM stdin;
T-1001	Maria	Santos	pok@gmail.com	CSD	Active	09416200-52e2-4c7e-bf0e-cd0d9f5fc395
\.


--
-- TOC entry 5146 (class 0 OID 0)
-- Dependencies: 230
-- Name: audit_log_audit_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.audit_log_audit_id_seq', 4, true);


--
-- TOC entry 4959 (class 2606 OID 49992)
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (audit_id);


--
-- TOC entry 4931 (class 2606 OID 16663)
-- Name: class_offering class_offering_class_code_section_school_year_semester_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.class_offering
    ADD CONSTRAINT class_offering_class_code_section_school_year_semester_key UNIQUE (class_code, section, school_year, semester);


--
-- TOC entry 4933 (class 2606 OID 16661)
-- Name: class_offering class_offering_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.class_offering
    ADD CONSTRAINT class_offering_pkey PRIMARY KEY (offering_id);


--
-- TOC entry 4937 (class 2606 OID 16697)
-- Name: enrollment enrollment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.enrollment
    ADD CONSTRAINT enrollment_pkey PRIMARY KEY (enrollment_id);


--
-- TOC entry 4939 (class 2606 OID 16699)
-- Name: enrollment enrollment_student_id_offering_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.enrollment
    ADD CONSTRAINT enrollment_student_id_offering_id_key UNIQUE (student_id, offering_id);


--
-- TOC entry 4941 (class 2606 OID 16722)
-- Name: grade_component grade_component_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_component
    ADD CONSTRAINT grade_component_pkey PRIMARY KEY (component_id);


--
-- TOC entry 4950 (class 2606 OID 16770)
-- Name: grade_component_score grade_component_score_enrollment_id_component_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_component_score
    ADD CONSTRAINT grade_component_score_enrollment_id_component_id_key UNIQUE (enrollment_id, component_id);


--
-- TOC entry 4952 (class 2606 OID 16768)
-- Name: grade_component_score grade_component_score_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_component_score
    ADD CONSTRAINT grade_component_score_pkey PRIMARY KEY (score_id);


--
-- TOC entry 4945 (class 2606 OID 16748)
-- Name: grade_percentage grade_percentage_offering_id_component_type_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_percentage
    ADD CONSTRAINT grade_percentage_offering_id_component_type_key UNIQUE (offering_id, component_type);


--
-- TOC entry 4947 (class 2606 OID 16746)
-- Name: grade_percentage grade_percentage_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_percentage
    ADD CONSTRAINT grade_percentage_pkey PRIMARY KEY (percentage_id);


--
-- TOC entry 4957 (class 2606 OID 16795)
-- Name: grade grade_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade
    ADD CONSTRAINT grade_pkey PRIMARY KEY (grade_id);


--
-- TOC entry 4935 (class 2606 OID 16682)
-- Name: grading_period grading_period_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grading_period
    ADD CONSTRAINT grading_period_pkey PRIMARY KEY (period_id);


--
-- TOC entry 4919 (class 2606 OID 16613)
-- Name: student student_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.student
    ADD CONSTRAINT student_email_key UNIQUE (email);


--
-- TOC entry 4921 (class 2606 OID 16611)
-- Name: student student_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.student
    ADD CONSTRAINT student_pkey PRIMARY KEY (student_id);


--
-- TOC entry 4927 (class 2606 OID 16641)
-- Name: subject subject_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subject
    ADD CONSTRAINT subject_pkey PRIMARY KEY (subject_id);


--
-- TOC entry 4929 (class 2606 OID 16643)
-- Name: subject subject_subject_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.subject
    ADD CONSTRAINT subject_subject_code_key UNIQUE (subject_code);


--
-- TOC entry 4923 (class 2606 OID 16629)
-- Name: teacher teacher_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teacher
    ADD CONSTRAINT teacher_email_key UNIQUE (email);


--
-- TOC entry 4925 (class 2606 OID 16627)
-- Name: teacher teacher_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teacher
    ADD CONSTRAINT teacher_pkey PRIMARY KEY (teacher_id);


--
-- TOC entry 4955 (class 1259 OID 49739)
-- Name: grade_enrollment_period_unique; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX grade_enrollment_period_unique ON public.grade USING btree (enrollment_id, period_id) WHERE (period_id IS NOT NULL);


--
-- TOC entry 4953 (class 1259 OID 16782)
-- Name: idx_gcs_component; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_gcs_component ON public.grade_component_score USING btree (component_id);


--
-- TOC entry 4954 (class 1259 OID 16781)
-- Name: idx_gcs_enrollment; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_gcs_enrollment ON public.grade_component_score USING btree (enrollment_id);


--
-- TOC entry 4942 (class 1259 OID 16733)
-- Name: idx_grade_component_offering; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_grade_component_offering ON public.grade_component USING btree (offering_id);


--
-- TOC entry 4943 (class 1259 OID 16734)
-- Name: idx_grade_component_period; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_grade_component_period ON public.grade_component USING btree (grading_period_id);


--
-- TOC entry 4948 (class 1259 OID 16754)
-- Name: idx_grade_percentage_offering; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_grade_percentage_offering ON public.grade_percentage USING btree (offering_id);


--
-- TOC entry 4974 (class 2620 OID 49997)
-- Name: class_offering studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.class_offering FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('offering_id');


--
-- TOC entry 4976 (class 2620 OID 49998)
-- Name: enrollment studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.enrollment FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('enrollment_id');


--
-- TOC entry 4980 (class 2620 OID 50003)
-- Name: grade studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.grade FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('grade_id');


--
-- TOC entry 4977 (class 2620 OID 50000)
-- Name: grade_component studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.grade_component FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('component_id');


--
-- TOC entry 4979 (class 2620 OID 50002)
-- Name: grade_component_score studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.grade_component_score FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('score_id');


--
-- TOC entry 4978 (class 2620 OID 50001)
-- Name: grade_percentage studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.grade_percentage FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('percentage_id');


--
-- TOC entry 4975 (class 2620 OID 49999)
-- Name: grading_period studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.grading_period FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('period_id');


--
-- TOC entry 4971 (class 2620 OID 49994)
-- Name: student studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.student FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('student_id');


--
-- TOC entry 4973 (class 2620 OID 49996)
-- Name: subject studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.subject FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('subject_id');


--
-- TOC entry 4972 (class 2620 OID 49995)
-- Name: teacher studentdb_audit_changes; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER studentdb_audit_changes AFTER INSERT OR DELETE OR UPDATE ON public.teacher FOR EACH ROW EXECUTE FUNCTION public.studentdb_audit_row('teacher_id');


--
-- TOC entry 4961 (class 2606 OID 16664)
-- Name: class_offering class_offering_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.class_offering
    ADD CONSTRAINT class_offering_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.teacher(teacher_id) ON DELETE RESTRICT;


--
-- TOC entry 4962 (class 2606 OID 16705)
-- Name: enrollment enrollment_offering_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.enrollment
    ADD CONSTRAINT enrollment_offering_id_fkey FOREIGN KEY (offering_id) REFERENCES public.class_offering(offering_id) ON DELETE CASCADE;


--
-- TOC entry 4963 (class 2606 OID 16700)
-- Name: enrollment enrollment_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.enrollment
    ADD CONSTRAINT enrollment_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.student(student_id) ON DELETE CASCADE;


--
-- TOC entry 4964 (class 2606 OID 16723)
-- Name: grade_component grade_component_grading_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_component
    ADD CONSTRAINT grade_component_grading_period_id_fkey FOREIGN KEY (grading_period_id) REFERENCES public.grading_period(period_id) ON DELETE CASCADE;


--
-- TOC entry 4965 (class 2606 OID 16728)
-- Name: grade_component grade_component_offering_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_component
    ADD CONSTRAINT grade_component_offering_id_fkey FOREIGN KEY (offering_id) REFERENCES public.class_offering(offering_id) ON DELETE CASCADE;


--
-- TOC entry 4967 (class 2606 OID 16776)
-- Name: grade_component_score grade_component_score_component_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_component_score
    ADD CONSTRAINT grade_component_score_component_id_fkey FOREIGN KEY (component_id) REFERENCES public.grade_component(component_id) ON DELETE CASCADE;


--
-- TOC entry 4968 (class 2606 OID 16771)
-- Name: grade_component_score grade_component_score_enrollment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_component_score
    ADD CONSTRAINT grade_component_score_enrollment_id_fkey FOREIGN KEY (enrollment_id) REFERENCES public.enrollment(enrollment_id) ON DELETE CASCADE;


--
-- TOC entry 4969 (class 2606 OID 16798)
-- Name: grade grade_enrollment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade
    ADD CONSTRAINT grade_enrollment_id_fkey FOREIGN KEY (enrollment_id) REFERENCES public.enrollment(enrollment_id) ON DELETE CASCADE;


--
-- TOC entry 4966 (class 2606 OID 16749)
-- Name: grade_percentage grade_percentage_offering_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade_percentage
    ADD CONSTRAINT grade_percentage_offering_id_fkey FOREIGN KEY (offering_id) REFERENCES public.class_offering(offering_id) ON DELETE CASCADE;


--
-- TOC entry 4970 (class 2606 OID 49734)
-- Name: grade grade_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.grade
    ADD CONSTRAINT grade_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.grading_period(period_id);


--
-- TOC entry 4960 (class 2606 OID 16645)
-- Name: teacher teacher_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.teacher
    ADD CONSTRAINT teacher_subject_id_fkey FOREIGN KEY (subject_id) REFERENCES public.subject(subject_id) ON DELETE RESTRICT;


-- Completed on 2026-10-21 13:11:44

--
-- PostgreSQL database dump complete
--

\unrestrict WQ8XlfvLM7Arz8dr8fkYBngha21R0mLoZehRnQ2Ch9qsOcwaP7KVnuw5RaKXDGY

