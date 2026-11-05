import hmac
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, current_app, g, jsonify, request, send_file, send_from_directory, session
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
MAX_CV_SIZE = 5 * 1024 * 1024
MAX_REQUEST_SIZE = 6 * 1024 * 1024
ALLOWED_CV_EXTENSIONS = {".pdf", ".doc", ".docx"}
PHONE_PATTERN = re.compile(r"^[0-9٠-٩+() -]{8,20}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EGYPT_CITIES = {
    "القاهرة", "الجيزة", "الإسكندرية", "الدقهلية", "البحر الأحمر", "البحيرة",
    "الفيوم", "الغربية", "الإسماعيلية", "المنوفية", "المنيا", "القليوبية",
    "الوادي الجديد", "السويس", "أسوان", "أسيوط", "بني سويف", "بورسعيد",
    "دمياط", "الشرقية", "جنوب سيناء", "كفر الشيخ", "المحلة", "مطروح",
    "الأقصر", "قنا", "شمال سيناء", "سوهاج",
}
JOB_CATEGORIES = {"إدارة", "محاسبة", "تسويق", "موارد بشرية", "تقنية", "برمجة"}
JOB_TYPES = {
    "full-time": "دوام كامل",
    "internship": "تدريب",
    "remote": "عن بُعد",
}

SEED_COMPANIES = [
    ("شركة النور للاستشارات", "ن", "logo-blue"),
    ("مدار للتجارة الإلكترونية", "م", "logo-orange"),
    ("جسور للموارد البشرية", "ج", "logo-purple"),
    ("آفاق للصناعات", "آ", "logo-green"),
    ("نقطة تك للحلول الرقمية", "ن", "logo-teal"),
    ("النخبة للتوزيع", "ن", "logo-red"),
    ("بكسل للحلول البرمجية", "ب", "logo-teal"),
    ("كود كلاود", "ك", "logo-blue"),
    ("دوت لاب للتقنية", "د", "logo-purple"),
]

SEED_JOBS = [
    ("junior-accountant", "محاسب مبتدئ", "شركة النور للاستشارات", "محاسبة", "القاهرة", "القاهرة، مدينة نصر", "full-time", "دوام كامل", "٨٬٠٠٠ – ١٠٬٠٠٠", "ج.م / شهريًا", "منذ يومين"),
    ("digital-marketing-coordinator", "منسق تسويق رقمي", "مدار للتجارة الإلكترونية", "تسويق", "الجيزة", "الجيزة، الشيخ زايد", "full-time", "دوام كامل", "٧٬٥٠٠ – ٩٬٠٠٠", "ج.م / شهريًا", "منذ ٣ أيام"),
    ("hr-intern", "متدرب موارد بشرية", "جسور للموارد البشرية", "موارد بشرية", "القاهرة", "القاهرة، المعادي", "internship", "تدريب", "تدريب مدفوع", "لمدة ٣ أشهر", "منذ ٤ أيام"),
    ("administrative-assistant", "مساعد إداري", "آفاق للصناعات", "إدارة", "القاهرة", "القاهرة، التجمع الخامس", "full-time", "دوام كامل", "٩٬٠٠٠ – ١١٬٠٠٠", "ج.م / شهريًا", "منذ أسبوع"),
    ("junior-data-analyst", "محلل بيانات مبتدئ", "نقطة تك للحلول الرقمية", "تقنية", "remote", "عن بُعد، من مصر", "remote", "عن بُعد", "١٠٬٠٠٠ – ١٣٬٠٠٠", "ج.م / شهريًا", "منذ أسبوع"),
    ("sales-intern", "متدرب مبيعات", "النخبة للتوزيع", "تسويق", "الإسكندرية", "الإسكندرية، سموحة", "internship", "تدريب", "تدريب مدفوع", "مع فرصة للتعيين", "منذ أسبوع"),
    ("junior-frontend-developer", "مطور واجهات أمامية مبتدئ", "بكسل للحلول البرمجية", "برمجة", "القاهرة", "القاهرة، التجمع الخامس", "full-time", "دوام كامل", "١٠٬٠٠٠ – ١٤٬٠٠٠", "ج.م / شهريًا", "منذ يومين"),
    ("junior-web-developer", "مطور مواقع مبتدئ", "كود كلاود", "برمجة", "remote", "عن بُعد، من مصر", "remote", "عن بُعد", "٩٬٠٠٠ – ١٢٬٠٠٠", "ج.م / شهريًا", "منذ ٣ أيام"),
    ("software-development-intern", "متدرب تطوير برمجيات", "دوت لاب للتقنية", "برمجة", "الجيزة", "الجيزة، الدقي", "internship", "تدريب", "تدريب مدفوع", "لمدة ٣ أشهر", "منذ ٥ أيام"),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


def initialize_database(app):
    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path = Path(app.config["UPLOAD_FOLDER"])
    upload_path.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as database:
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys = ON")
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                initial TEXT NOT NULL,
                logo_color TEXT NOT NULL,
                owner_user_id INTEGER,
                contact_name TEXT,
                phone TEXT,
                website TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                role TEXT NOT NULL CHECK (role IN ('seeker', 'employer')),
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS seeker_profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                city TEXT NOT NULL,
                specialization TEXT NOT NULL,
                cv_storage_name TEXT
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                company_id INTEGER NOT NULL REFERENCES companies(id),
                category TEXT NOT NULL,
                city TEXT NOT NULL,
                location TEXT NOT NULL,
                job_type TEXT NOT NULL CHECK (job_type IN ('full-time', 'internship', 'remote')),
                job_type_label TEXT NOT NULL,
                salary TEXT NOT NULL,
                salary_note TEXT NOT NULL,
                posted_label TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                posted_by_user_id INTEGER REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id),
                applicant_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                cv_storage_name TEXT,
                user_id INTEGER REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'reviewing', 'accepted', 'rejected')),
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active, id);
            CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
            CREATE INDEX IF NOT EXISTS idx_applications_created_at ON applications(created_at);
            """
        )

        company_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(companies)")
        }
        for column, definition in (
            ("owner_user_id", "INTEGER"),
            ("contact_name", "TEXT"),
            ("phone", "TEXT"),
            ("website", "TEXT"),
        ):
            if column not in company_columns:
                database.execute(f"ALTER TABLE companies ADD COLUMN {column} {definition}")

        job_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(jobs)")
        }
        if "posted_by_user_id" not in job_columns:
            database.execute(
                "ALTER TABLE jobs ADD COLUMN posted_by_user_id INTEGER REFERENCES users(id)"
            )

        application_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(applications)")
        }
        if "user_id" not in application_columns:
            database.execute(
                "ALTER TABLE applications ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )

        database.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_poster ON jobs(posted_by_user_id, is_active)"
        )
        database.execute(
            "CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id)"
        )
        database.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_unique_seeker_job
                ON applications(job_id, user_id) WHERE user_id IS NOT NULL
            """
        )

        for company in SEED_COMPANIES:
            database.execute(
                "INSERT OR IGNORE INTO companies (name, initial, logo_color) VALUES (?, ?, ?)",
                company,
            )

        timestamp = datetime.now(timezone.utc).isoformat()
        for job in SEED_JOBS:
            slug, title, company_name, category, city, location, job_type, type_label, salary, salary_note, posted_label = job
            database.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    slug, title, company_id, category, city, location, job_type,
                    job_type_label, salary, salary_note, posted_label, created_at
                )
                SELECT ?, ?, id, ?, ?, ?, ?, ?, ?, ?, ?, ?
                FROM companies WHERE name = ?
                """,
                (
                    slug,
                    title,
                    category,
                    city,
                    location,
                    job_type,
                    type_label,
                    salary,
                    salary_note,
                    posted_label,
                    timestamp,
                    company_name,
                ),
            )

        database.commit()


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "step.db")),
        UPLOAD_FOLDER=os.environ.get("UPLOAD_DIR", str(BASE_DIR / "instance" / "uploads")),
        MAX_CONTENT_LENGTH=MAX_REQUEST_SIZE,
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes"},
    )
    if test_config:
        app.config.update(test_config)

    initialize_database(app)
    app.teardown_appcontext(close_db)

    def csrf_token():
        token = session.get("csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    def csrf_is_valid():
        expected = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token", "")
        return bool(expected and supplied and hmac.compare_digest(expected, supplied))

    def current_account(required_role=None):
        account_id = session.get("account_id")
        if not account_id:
            return None

        account = get_db().execute(
            """
            SELECT users.id, users.role, users.name, users.email, users.phone,
                   seeker_profiles.city, seeker_profiles.specialization,
                   seeker_profiles.cv_storage_name,
                   companies.id AS company_id, companies.name AS company_name,
                   companies.contact_name, companies.website
            FROM users
            LEFT JOIN seeker_profiles ON seeker_profiles.user_id = users.id
            LEFT JOIN companies ON companies.owner_user_id = users.id
            WHERE users.id = ?
            """,
            (account_id,),
        ).fetchone()
        if account is None or (required_role and account["role"] != required_role):
            return None
        return account

    def public_account(account):
        response = {
            "id": account["id"],
            "role": account["role"],
            "name": account["name"],
            "email": account["email"],
            "phone": account["phone"],
        }
        if account["role"] == "seeker":
            response.update(
                city=account["city"],
                specialization=account["specialization"],
                has_cv=account["cv_storage_name"] is not None,
            )
        else:
            response.update(
                company_id=account["company_id"],
                company_name=account["company_name"],
                website=account["website"] or "",
            )
        return response

    def read_cv(upload):
        if not upload or not upload.filename:
            return None, None, None

        extension = Path(secure_filename(upload.filename)).suffix.lower()
        if extension not in ALLOWED_CV_EXTENSIONS:
            return None, None, "ارفع السيرة الذاتية بصيغة PDF أو Word."

        file_bytes = upload.stream.read(MAX_CV_SIZE + 1)
        if not file_bytes:
            return None, None, "ملف السيرة الذاتية فارغ."
        if len(file_bytes) > MAX_CV_SIZE:
            return None, None, "حجم السيرة الذاتية يجب ألا يتجاوز ٥ ميجابايت."

        valid_signatures = {
            ".pdf": file_bytes.startswith(b"%PDF-"),
            ".doc": file_bytes.startswith(bytes.fromhex("D0CF11E0A1B11AE1")),
            ".docx": file_bytes.startswith(b"PK\x03\x04"),
        }
        if not valid_signatures[extension]:
            return None, None, "محتوى الملف لا يطابق صيغته."
        return file_bytes, extension, None

    def store_private_file(file_bytes, extension):
        storage_name = f"{uuid.uuid4().hex}{extension}"
        path = Path(app.config["UPLOAD_FOLDER"]) / storage_name
        path.write_bytes(file_bytes)
        return storage_name, path

    @app.get("/")
    def index():
        return send_from_directory(BASE_DIR, "index.html")

    @app.get("/<path:filename>")
    def public_asset(filename):
        if filename not in {"s.css", "scr.js"}:
            return jsonify(error="الصفحة المطلوبة غير موجودة."), 404
        return send_from_directory(BASE_DIR, filename)

    @app.get("/api/auth/session")
    def auth_session():
        account = current_account()
        return jsonify(
            csrf_token=csrf_token(),
            account=public_account(account) if account else None,
        )

    @app.post("/api/auth/register")
    def register_account():
        if not csrf_is_valid():
            return jsonify(error="انتهت صلاحية النموذج. حدّث الصفحة وحاول مرة أخرى."), 400

        role = request.form.get("role", "")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        consent = request.form.get("account_consent")
        if role not in {"seeker", "employer"}:
            return jsonify(error="اختار نوع الحساب."), 400
        if not name or len(name) > 120:
            return jsonify(error="اكتب الاسم، على ألا يزيد عن ١٢٠ حرفًا."), 400
        if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            return jsonify(error="اكتب بريدًا إلكترونيًا صحيحًا."), 400
        if len(password) < 10 or len(password) > 128:
            return jsonify(error="كلمة المرور يجب ألا تقل عن ١٠ أحرف."), 400
        if not PHONE_PATTERN.fullmatch(phone) or not re.search(r"[0-9٠-٩]", phone):
            return jsonify(error="اكتب رقم تلفون صحيحًا."), 400
        if consent != "yes":
            return jsonify(error="الموافقة على حفظ البيانات مطلوبة لإنشاء الحساب."), 400

        city = ""
        specialization = ""
        company_name = ""
        contact_name = ""
        website = ""
        if role == "seeker":
            city = request.form.get("city", "").strip()
            specialization = request.form.get("specialization", "").strip()
            if city not in EGYPT_CITIES and city != "remote":
                return jsonify(error="اختار المدينة من القائمة."), 400
            if not specialization or len(specialization) > 120:
                return jsonify(error="اكتب تخصصك الدراسي."), 400
            cv_bytes, cv_extension, cv_error = read_cv(request.files.get("cv"))
            if cv_error:
                return jsonify(error=cv_error), 400 if "حجم" not in cv_error else 413
        else:
            company_name = request.form.get("company_name", "").strip()
            contact_name = request.form.get("contact_name", name).strip()
            website = request.form.get("website", "").strip()
            if not company_name or len(company_name) > 160:
                return jsonify(error="اكتب اسم الشركة، على ألا يزيد عن ١٦٠ حرفًا."), 400
            if not contact_name or len(contact_name) > 120:
                return jsonify(error="اكتب اسم مسؤول التواصل."), 400
            if website:
                parsed_website = urlparse(website)
                if parsed_website.scheme not in {"http", "https"} or not parsed_website.netloc:
                    return jsonify(error="أدخل رابط موقع صحيحًا يبدأ بـ https://."), 400

        database = get_db()
        stored_cv_name = None
        saved_path = None
        try:
            if role == "seeker" and cv_bytes:
                stored_cv_name, saved_path = store_private_file(cv_bytes, cv_extension)

            cursor = database.execute(
                """
                INSERT INTO users (role, name, email, password_hash, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    role,
                    name,
                    email,
                    generate_password_hash(password),
                    phone,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            account_id = cursor.lastrowid

            if role == "seeker":
                cursor = database.execute(
                    """
                    INSERT INTO seeker_profiles (user_id, city, specialization, cv_storage_name)
                    VALUES (?, ?, ?, ?)
                    """,
                    (account_id, city, specialization, stored_cv_name),
                )
            else:
                database.execute(
                    """
                    INSERT INTO companies (
                        name, initial, logo_color, owner_user_id, contact_name, phone, website
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_name,
                        company_name[0],
                        "logo-green",
                        account_id,
                        contact_name,
                        phone,
                        website or None,
                    ),
                )
            database.commit()
        except sqlite3.IntegrityError:
            database.rollback()
            if saved_path and saved_path.exists():
                saved_path.unlink()
            return jsonify(error="البريد الإلكتروني مستخدم بالفعل."), 409
        except (OSError, sqlite3.Error):
            database.rollback()
            if saved_path and saved_path.exists():
                saved_path.unlink()
            current_app.logger.exception("Unable to create an account.")
            return jsonify(error="تعذر إنشاء الحساب الآن. حاول مرة أخرى لاحقًا."), 500

        session.clear()
        session["account_id"] = account_id
        csrf_token()
        account = current_account()
        return jsonify(account=public_account(account), csrf_token=session["csrf_token"]), 201

    @app.post("/api/auth/login")
    def login_account():
        if not csrf_is_valid():
            return jsonify(error="انتهت صلاحية النموذج. حدّث الصفحة وحاول مرة أخرى."), 400

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        account = get_db().execute(
            "SELECT id, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if account is None or not check_password_hash(account["password_hash"], password):
            return jsonify(error="البريد الإلكتروني أو كلمة المرور غير صحيحة."), 401

        session.clear()
        session["account_id"] = account["id"]
        csrf_token()
        signed_in_account = current_account()
        return jsonify(
            account=public_account(signed_in_account),
            csrf_token=session["csrf_token"],
        )

    @app.post("/api/auth/logout")
    def logout_account():
        if not csrf_is_valid():
            return jsonify(error="انتهت صلاحية النموذج. حدّث الصفحة وحاول مرة أخرى."), 400
        session.clear()
        return jsonify(message="تم تسجيل الخروج.", csrf_token=csrf_token())

    @app.get("/api/profile/cv")
    def download_profile_cv():
        account = current_account("seeker")
        if account is None:
            return jsonify(error="سجّل الدخول بحساب باحث عن عمل أولًا."), 401
        storage_name = account["cv_storage_name"]
        if not storage_name:
            return jsonify(error="لم ترفع سيرة ذاتية إلى حسابك."), 404
        path = Path(app.config["UPLOAD_FOLDER"]) / storage_name
        if not path.is_file():
            current_app.logger.error("A profile resume is missing from private storage.")
            return jsonify(error="تعذر العثور على السيرة الذاتية."), 404
        response = send_file(
            path,
            as_attachment=True,
            download_name=f"resume{Path(storage_name).suffix}",
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.get("/api/employer/jobs")
    def employer_jobs():
        account = current_account("employer")
        if account is None:
            return jsonify(error="سجّل الدخول بحساب شركة أولًا."), 401
        rows = get_db().execute(
            """
            SELECT jobs.id, jobs.title, jobs.category, jobs.city, jobs.location,
                   jobs.job_type_label, jobs.salary, jobs.salary_note, jobs.is_active,
                   jobs.created_at,
                   COUNT(applications.id) AS applications_count
            FROM jobs
            LEFT JOIN applications ON applications.job_id = jobs.id
            WHERE jobs.posted_by_user_id = ?
            GROUP BY jobs.id
            ORDER BY jobs.id DESC
            """,
            (account["id"],),
        ).fetchall()
        return jsonify(jobs=[dict(row) for row in rows])

    @app.post("/api/employer/jobs")
    def create_job():
        if not csrf_is_valid():
            return jsonify(error="انتهت صلاحية النموذج. حدّث الصفحة وحاول مرة أخرى."), 400
        account = current_account("employer")
        if account is None:
            return jsonify(error="نشر الوظائف متاح لحسابات الشركات فقط."), 403

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        city = request.form.get("city", "").strip()
        job_type = request.form.get("job_type", "").strip()
        location_detail = request.form.get("location_detail", "").strip()
        salary = request.form.get("salary", "").strip()
        salary_note = request.form.get("salary_note", "").strip()
        if not title or len(title) > 160:
            return jsonify(error="اكتب المسمى الوظيفي، على ألا يزيد عن ١٦٠ حرفًا."), 400
        if category not in JOB_CATEGORIES:
            return jsonify(error="اختار مجالًا صحيحًا للوظيفة."), 400
        if job_type not in JOB_TYPES:
            return jsonify(error="اختار نوع وظيفة صحيحًا."), 400
        if city not in EGYPT_CITIES:
            return jsonify(error="اختار محافظة صحيحة من القائمة."), 400
        if len(location_detail) > 120 or len(salary) > 80 or len(salary_note) > 80:
            return jsonify(error="تحقق من طول الموقع أو تفاصيل الراتب."), 400

        location = "عن بُعد، من مصر" if job_type == "remote" else city
        if location_detail and job_type != "remote":
            location = f"{city}، {location_detail}"
        if not salary:
            salary = "يحدد بعد المقابلة"
        if not salary_note:
            salary_note = "حسب الخبرة"

        database = get_db()
        company = database.execute(
            "SELECT id FROM companies WHERE owner_user_id = ?",
            (account["id"],),
        ).fetchone()
        if company is None:
            return jsonify(error="لم يتم إعداد ملف الشركة. تواصل مع الدعم."), 409

        cursor = database.execute(
            """
            INSERT INTO jobs (
                slug, title, company_id, category, city, location, job_type,
                job_type_label, salary, salary_note, posted_label, is_active,
                created_at, posted_by_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                title,
                company["id"],
                category,
                "remote" if job_type == "remote" else city,
                location,
                job_type,
                JOB_TYPES[job_type],
                salary,
                salary_note,
                "حديثًا",
                datetime.now(timezone.utc).isoformat(),
                account["id"],
            ),
        )
        database.commit()
        return jsonify(message="تم نشر الوظيفة بنجاح.", job_id=cursor.lastrowid), 201

    @app.get("/api/employer/applications")
    def employer_applications():
        account = current_account("employer")
        if account is None:
            return jsonify(error="سجّل الدخول بحساب شركة أولًا."), 401
        rows = get_db().execute(
            """
            SELECT applications.id, applications.applicant_name, applications.email,
                   applications.phone, applications.cv_storage_name IS NOT NULL AS has_cv,
                   applications.created_at, applications.status,
                   jobs.id AS job_id, jobs.title AS job_title
            FROM applications
            JOIN jobs ON jobs.id = applications.job_id
            WHERE jobs.posted_by_user_id = ?
            ORDER BY applications.id DESC
            """,
            (account["id"],),
        ).fetchall()
        return jsonify(applications=[dict(row) for row in rows])

    @app.get("/api/employer/applications/<int:application_id>/cv")
    def download_applicant_cv(application_id):
        account = current_account("employer")
        if account is None:
            return jsonify(error="سجّل الدخول بحساب شركة أولًا."), 401
        application = get_db().execute(
            """
            SELECT applications.cv_storage_name
            FROM applications
            JOIN jobs ON jobs.id = applications.job_id
            WHERE applications.id = ? AND jobs.posted_by_user_id = ?
            """,
            (application_id, account["id"]),
        ).fetchone()
        if application is None or not application["cv_storage_name"]:
            return jsonify(error="السيرة الذاتية غير متاحة لهذا الطلب."), 404
        storage_name = application["cv_storage_name"]
        path = Path(app.config["UPLOAD_FOLDER"]) / storage_name
        if not path.is_file():
            current_app.logger.error("An application resume is missing from private storage.")
            return jsonify(error="تعذر العثور على السيرة الذاتية."), 404
        response = send_file(
            path,
            as_attachment=True,
            download_name=f"resume{Path(storage_name).suffix}",
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.get("/api/jobs")
    def list_jobs():
        rows = get_db().execute(
            """
            SELECT jobs.id, jobs.title, companies.name AS company,
                   companies.initial AS company_initial, companies.logo_color,
                   jobs.category, jobs.city, jobs.location, jobs.job_type,
                   jobs.job_type_label, jobs.salary, jobs.salary_note,
                   jobs.posted_label
            FROM jobs
            JOIN companies ON companies.id = jobs.company_id
            WHERE jobs.is_active = 1
            ORDER BY jobs.id
            """
        ).fetchall()
        return jsonify(jobs=[dict(row) for row in rows])

    @app.get("/api/stats")
    def public_stats():
        database = get_db()
        return jsonify(
            jobs=database.execute(
                "SELECT COUNT(*) FROM jobs WHERE is_active = 1"
            ).fetchone()[0],
            companies=database.execute(
                """
                SELECT COUNT(DISTINCT company_id)
                FROM jobs WHERE is_active = 1
                """
            ).fetchone()[0],
            applications=database.execute(
                "SELECT COUNT(*) FROM applications"
            ).fetchone()[0],
        )

    @app.post("/api/applications")
    def submit_application():
        if not csrf_is_valid():
            return jsonify(error="انتهت صلاحية النموذج. حدّث الصفحة وحاول مرة أخرى."), 400
        account = current_account("seeker")
        if account is None:
            return jsonify(error="سجّل الدخول بحساب باحث عن عمل للتقديم."), 401

        job_id = request.form.get("job_id", "").strip()
        consent = request.form.get("consent")
        cv = request.files.get("cv")

        if consent != "yes":
            return jsonify(error="يجب الموافقة على حفظ البيانات لمراجعة الطلب."), 400
        if not job_id.isdigit():
            return jsonify(error="الوظيفة المطلوبة غير صحيحة."), 400

        database = get_db()
        job = database.execute(
            "SELECT id FROM jobs WHERE id = ? AND is_active = 1",
            (int(job_id),),
        ).fetchone()
        if job is None:
            return jsonify(error="الوظيفة غير متاحة حاليًا."), 404

        duplicate = database.execute(
            "SELECT 1 FROM applications WHERE job_id = ? AND user_id = ?",
            (int(job_id), account["id"]),
        ).fetchone()
        if duplicate:
            return jsonify(error="سبق وقدمت على هذه الوظيفة."), 409

        cv_bytes, cv_extension, cv_error = read_cv(cv)
        if cv_error:
            return jsonify(error=cv_error), 413 if "حجم" in cv_error else 400
        stored_cv_name = account["cv_storage_name"]

        saved_path = None
        try:
            if cv_bytes is not None:
                stored_cv_name, saved_path = store_private_file(cv_bytes, cv_extension)

            cursor = database.execute(
                """
                INSERT INTO applications (
                    job_id, applicant_name, email, phone, cv_storage_name, user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(job_id),
                    account["name"],
                    account["email"],
                    account["phone"],
                    stored_cv_name,
                    account["id"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            database.commit()
        except OSError:
            database.rollback()
            if saved_path and saved_path.exists():
                saved_path.unlink()
            current_app.logger.exception("Unable to store an application attachment.")
            return jsonify(error="تعذر حفظ الطلب الآن. حاول مرة أخرى لاحقًا."), 500
        except sqlite3.Error:
            database.rollback()
            if saved_path and saved_path.exists():
                saved_path.unlink()
            current_app.logger.exception("Unable to store an application.")
            return jsonify(error="تعذر حفظ الطلب الآن. حاول مرة أخرى لاحقًا."), 500

        return jsonify(message="تم استلام طلبك بنجاح!", application_id=cursor.lastrowid), 201

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify(error="حجم الطلب أكبر من المسموح. الحد الأقصى للسيرة الذاتية ٥ ميجابايت."), 413

    @app.errorhandler(500)
    def internal_server_error(_error):
        if request.path.startswith("/api/"):
            return jsonify(error="حدث خطأ أثناء تنفيذ الطلب. حاول مرة أخرى لاحقًا."), 500
        return "حدث خطأ أثناء تحميل الصفحة.", 500

    @app.get("/api/health")
    def health():
        get_db().execute("SELECT 1")
        return jsonify(status="ok")

    return app


app = create_app()


if __name__ == "__main__":
    from waitress import serve

    serve(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )
