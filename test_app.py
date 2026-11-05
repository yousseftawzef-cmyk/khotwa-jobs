import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from io import BytesIO
from pathlib import Path
from uuid import uuid4


TEST_DIRECTORY = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = str(Path(TEST_DIRECTORY.name) / "test.db")
os.environ["UPLOAD_DIR"] = str(Path(TEST_DIRECTORY.name) / "uploads")

from app import create_app


class ApplicationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "DATABASE": os.environ["DATABASE_PATH"],
                "UPLOAD_FOLDER": os.environ["UPLOAD_DIR"],
            }
        )
        cls.client = cls.app.test_client()

    def setUp(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute("DELETE FROM applications")
            database.execute("DELETE FROM jobs WHERE posted_by_user_id IS NOT NULL")
            database.execute("DELETE FROM companies WHERE owner_user_id IS NOT NULL")
            database.execute("DELETE FROM seeker_profiles")
            database.execute("DELETE FROM users")
            database.commit()
        self.client = self.app.test_client()
        session_response = self.client.get("/api/auth/session")
        self.csrf_token = session_response.json["csrf_token"]
        self.email = f"seeker-{uuid4().hex}@example.com"
        registration = self.client.post(
            "/api/auth/register",
            data={
                "role": "seeker",
                "name": "أحمد محمد",
                "email": self.email,
                "password": "secure-password-123",
                "phone": "01012345678",
                "city": "القاهرة",
                "specialization": "إدارة أعمال",
                "account_consent": "yes",
            },
            headers={"X-CSRF-Token": self.csrf_token},
        )
        self.assertEqual(registration.status_code, 201)
        self.csrf_token = registration.json["csrf_token"]

    def csrf_headers(self):
        return {"X-CSRF-Token": self.csrf_token}

    def test_seeded_jobs_are_read_from_database(self):
        response = self.client.get("/api/jobs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["jobs"]), 9)
        self.assertTrue(any(job["category"] == "برمجة" for job in response.json["jobs"]))

    def test_stats_reflect_database_records(self):
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"jobs": 9, "companies": 9, "applications": 0})

    def test_application_without_resume_is_saved(self):
        job_id = self.client.get("/api/jobs").json["jobs"][0]["id"]
        response = self.client.post(
            "/api/applications",
            data={
                "job_id": str(job_id),
                "name": "أحمد محمد",
                "email": "ahmed@example.com",
                "phone": "01012345678",
                "consent": "yes",
            },
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["message"], "تم استلام طلبك بنجاح!")

        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            application = database.execute(
                "SELECT applicant_name, email, cv_storage_name FROM applications"
            ).fetchone()
        self.assertEqual(application, ("أحمد محمد", self.email, None))

    def test_application_saves_a_valid_optional_resume(self):
        job_id = self.client.get("/api/jobs").json["jobs"][0]["id"]
        response = self.client.post(
            "/api/applications",
            data={
                "job_id": str(job_id),
                "name": "سارة علي",
                "email": "sara@example.com",
                "phone": "01012345678",
                "consent": "yes",
                "cv": (BytesIO(b"%PDF-1.4\nresume"), "resume.pdf"),
            },
            headers=self.csrf_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)

        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            stored_name = database.execute(
                "SELECT cv_storage_name FROM applications"
            ).fetchone()[0]
        self.assertTrue((Path(self.app.config["UPLOAD_FOLDER"]) / stored_name).is_file())

    def test_application_rejects_an_invalid_resume_signature(self):
        job_id = self.client.get("/api/jobs").json["jobs"][0]["id"]
        response = self.client.post(
            "/api/applications",
            data={
                "job_id": str(job_id),
                "name": "سارة علي",
                "email": "sara@example.com",
                "phone": "01012345678",
                "consent": "yes",
                "cv": (BytesIO(b"not a PDF"), "resume.pdf"),
            },
            headers=self.csrf_headers(),
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)

    def test_application_rejects_an_unknown_job(self):
        response = self.client.post(
            "/api/applications",
            data={
                "job_id": "999999",
                "name": "أحمد محمد",
                "email": "ahmed@example.com",
                "phone": "01012345678",
                "consent": "yes",
            },
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_application_requires_data_storage_consent(self):
        job_id = self.client.get("/api/jobs").json["jobs"][0]["id"]
        response = self.client.post(
            "/api/applications",
            data={
                "job_id": str(job_id),
                "name": "أحمد محمد",
                "email": "ahmed@example.com",
                "phone": "01012345678",
            },
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 400)

    def test_application_requires_a_seeker_account(self):
        client = self.app.test_client()
        csrf = client.get("/api/auth/session").json["csrf_token"]
        response = client.post(
            "/api/applications",
            data={"job_id": "1", "consent": "yes"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 401)

    def test_seeker_can_register_and_password_is_hashed(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            row = database.execute(
                "SELECT role, password_hash FROM users WHERE email = ?",
                (self.email,),
            ).fetchone()
        self.assertEqual(row[0], "seeker")
        self.assertNotEqual(row[1], "secure-password-123")

    def test_account_login_and_logout_issue_fresh_csrf_tokens(self):
        client = self.app.test_client()
        csrf = client.get("/api/auth/session").json["csrf_token"]
        login = client.post(
            "/api/auth/login",
            data={"email": self.email, "password": "secure-password-123"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json["account"]["role"], "seeker")
        self.assertNotEqual(login.json["csrf_token"], csrf)

        logout = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": login.json["csrf_token"]},
        )
        self.assertEqual(logout.status_code, 200)
        self.assertNotEqual(logout.json["csrf_token"], login.json["csrf_token"])
        self.assertIsNone(client.get("/api/auth/session").json["account"])

    def test_login_rejects_an_incorrect_password(self):
        client = self.app.test_client()
        csrf = client.get("/api/auth/session").json["csrf_token"]
        response = client.post(
            "/api/auth/login",
            data={"email": self.email, "password": "incorrect-password"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 401)

    def test_employer_can_publish_a_job_and_view_its_applications(self):
        employer_client = self.app.test_client()
        csrf = employer_client.get("/api/auth/session").json["csrf_token"]
        suffix = uuid4().hex[:8]
        registration = employer_client.post(
            "/api/auth/register",
            data={
                "role": "employer",
                "name": "مسؤول الشركة",
                "company_name": f"شركة اختبار {suffix}",
                "email": f"employer-{suffix}@example.com",
                "password": "secure-password-123",
                "phone": "01012345678",
                "account_consent": "yes",
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(registration.status_code, 201)
        csrf = registration.json["csrf_token"]
        publish = employer_client.post(
            "/api/employer/jobs",
            data={
                "title": "مطور بايثون",
                "category": "برمجة",
                "city": "القاهرة",
                "job_type": "full-time",
                "location_detail": "مدينة نصر",
                "salary": "١٥٬٠٠٠",
                "salary_note": "شهريًا",
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(publish.status_code, 201)

        application = self.client.post(
            "/api/applications",
            data={"job_id": str(publish.json["job_id"]), "consent": "yes"},
            headers=self.csrf_headers(),
        )
        self.assertEqual(application.status_code, 201)
        employer_applications = employer_client.get("/api/employer/applications")
        self.assertEqual(len(employer_applications.json["applications"]), 1)
        self.assertEqual(
            employer_applications.json["applications"][0]["applicant_name"],
            "أحمد محمد",
        )

        other_employer = self.app.test_client()
        other_csrf = other_employer.get("/api/auth/session").json["csrf_token"]
        other_suffix = uuid4().hex[:8]
        other_registration = other_employer.post(
            "/api/auth/register",
            data={
                "role": "employer",
                "name": "مسؤول شركة أخرى",
                "company_name": f"شركة أخرى {other_suffix}",
                "email": f"another-employer-{other_suffix}@example.com",
                "password": "secure-password-123",
                "phone": "01012345678",
                "account_consent": "yes",
            },
            headers={"X-CSRF-Token": other_csrf},
        )
        self.assertEqual(other_registration.status_code, 201)
        other_applications = other_employer.get("/api/employer/applications")
        self.assertEqual(other_applications.json["applications"], [])

    def test_seeker_cannot_publish_jobs(self):
        response = self.client.post(
            "/api/employer/jobs",
            data={"title": "غير مسموح"},
            headers=self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
