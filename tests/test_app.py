import os
import base64
import tempfile
import unittest

from fastapi.testclient import TestClient

TEMP_DATA = tempfile.TemporaryDirectory()
os.environ["FACULTYHELP_DATA_DIR"] = TEMP_DATA.name

from main import app


class FacultyHelpTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def sign_in(self, user_id, password):
        return self.client.post("/login", data={"user_id": user_id, "password": password}, follow_redirects=False)

    def test_invalid_login_is_rejected(self):
        response = self.sign_in("FAC001", "incorrect")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid user ID or password", response.text)

    def test_faculty_ticket_creation_with_evidence_and_shared_join(self):
        self.assertEqual(self.sign_in("FAC001", "faculty123").status_code, 303)
        response = self.client.post(
            "/tickets/new",
            data={"category": "IT Support", "subcategory": "Projector", "subject": "Test classroom projector", "description": "No image appears on screen", "location": "CSE Block", "people_affected": "2", "priority": "High", "urgency": "Urgent"},
            files={"attachment": ("evidence.txt", b"not allowed", "text/plain")},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/tickets/new",
            data={"category": "IT Support", "subcategory": "Projector", "subject": "Test classroom projector", "description": "No image appears on screen", "location": "CSE Block", "people_affected": "2", "priority": "High", "urgency": "Urgent"},
            files={"attachment": ("evidence.pdf", b"sample evidence", "application/pdf")},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        token = response.headers["location"].rsplit("/", 1)[-1]
        detail = self.client.get(f"/tickets/{token}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Test classroom projector", detail.text)
        self.assertIn("Open attachment · evidence.pdf", detail.text)
        second = TestClient(app)
        with second:
            self.assertEqual(second.post("/login", data={"user_id": "FAC002", "password": "faculty123"}, follow_redirects=False).status_code, 303)
            self.assertEqual(second.post(f"/tickets/{token}/join", follow_redirects=False).status_code, 303)
            self.assertIn("2</dd>", second.get(f"/tickets/{token}").text)

    def test_admin_export_and_routing_duplicate_guard(self):
        self.assertEqual(self.sign_in("ADM001", "admin123").status_code, 303)
        self.assertEqual(self.client.get("/admin").status_code, 200)
        report = self.client.get("/reports.csv")
        self.assertEqual(report.status_code, 200)
        self.assertIn("FT-00001", report.text)
        duplicate = self.client.post("/admin/resources", data={"kind": "routing", "category": "IT Support", "subcategory": "Projector", "team_name": "IT Support"})
        self.assertEqual(duplicate.status_code, 409)

    def test_json_login_and_bootstrap(self):
        login = self.client.post("/api/auth/login", json={"userId": "IT001", "password": "team123"})
        self.assertEqual(login.status_code, 200)
        bootstrap = self.client.post("/api/bootstrap", json={"sessionToken": login.json()["sessionToken"]})
        self.assertEqual(bootstrap.status_code, 200)
        self.assertEqual(bootstrap.json()["user"]["role"], "Team Member")

    def test_faculty_signup_request_can_be_approved(self):
        request = self.client.post("/api/auth/signup-request", json={"facultyId": "FAC099", "name": "New Faculty", "department": "CSE", "password": "newuser123"})
        self.assertEqual(request.status_code, 201)
        admin = self.client.post("/api/auth/login", json={"userId": "ADM001", "password": "admin123"}).json()
        data = self.client.post("/api/admin/data", json={"sessionToken": admin["sessionToken"]}).json()
        access = next(item for item in data["access_requests"] if item["facultyId"] == "FAC099")
        self.assertNotIn("passwordHash", access)
        approved = self.client.post("/api/admin/mutate", json={"sessionToken": admin["sessionToken"], "kind": "access_requests", "action": "approve", "id": access["id"]})
        self.assertEqual(approved.status_code, 200)
        login = self.client.post("/api/auth/login", json={"userId": "FAC099", "password": "newuser123"})
        self.assertEqual(login.status_code, 200)

    def test_admin_sla_setting_controls_new_ticket_deadline(self):
        admin = self.client.post("/api/auth/login", json={"userId": "ADM001", "password": "admin123"}).json()
        response = self.client.post("/api/admin/mutate", json={"sessionToken": admin["sessionToken"], "kind": "sla_settings", "action": "update", "id": "Critical", "record": {"priority": "Critical", "responseMinutes": 2, "resolutionMinutes": 3, "active": True}})
        self.assertEqual(response.status_code, 200)
        faculty = self.client.post("/api/auth/login", json={"userId": "FAC001", "password": "faculty123"}).json()
        created = self.client.post("/api/tickets", json={"sessionToken": faculty["sessionToken"], "category": "IT Support", "subcategory": "Projector", "subject": "SLA setting check", "description": "Verify configured deadlines", "location": "CSE Block", "priority": "Critical"})
        self.assertEqual(created.status_code, 201)
        detail = self.client.post("/api/tickets/detail", json={"sessionToken": faculty["sessionToken"], "token": created.json()["ticket"]["token"]}).json()["ticket"]
        from datetime import datetime
        duration = datetime.fromisoformat(detail["resolution_deadline"]) - datetime.fromisoformat(detail["created_at"])
        self.assertEqual(duration.total_seconds(), 180)

    def test_json_ticket_create_and_evidence_upload(self):
        faculty = self.client.post("/api/auth/login", json={"userId": "FAC001", "password": "faculty123"}).json()
        session_token = faculty["sessionToken"]
        created = self.client.post("/api/tickets", json={"sessionToken": session_token, "category": "IT Support", "subcategory": "Projector", "subject": "JSON upload check", "description": "Check frontend upload API", "location": "CSE Block", "priority": "High", "urgency": "Urgent", "peopleAffected": 2})
        self.assertEqual(created.status_code, 201)
        token = created.json()["ticket"]["token"]
        uploaded = self.client.post("/api/upload", json={"sessionToken": session_token, "token": token, "fileName": "evidence.pdf", "contentType": "application/pdf", "base64": base64.b64encode(b"sample PDF evidence").decode()})
        self.assertEqual(uploaded.status_code, 200)
        detail = self.client.post("/api/tickets/detail", json={"sessionToken": session_token, "token": token}).json()["ticket"]
        self.assertEqual(detail["attachment"]["fileName"], "evidence.pdf")
        self.assertEqual(detail["teamName"], "IT Support")


if __name__ == "__main__":
    unittest.main()