from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("FACULTYHELP_DATA_DIR", "/tmp/facultyhelp" if os.getenv("VERCEL") else BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DATABASE = DATA_DIR / "facultyhelp.sqlite3"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

STATUSES = ("New", "Assigned", "In Progress", "Pending", "Resolved", "Closed", "Escalated")
PRIORITIES = ("Low", "Medium", "High", "Critical")
SLA_MINUTES = {"Critical": (15, 120), "High": (30, 360), "Medium": (120, 1440), "Low": (480, 4320)}
DEPARTMENTS = ("CSE", "CSE-AI", "ECE", "EEE", "Mechanical", "Civil", "Science", "Mathematics", "Physics", "Chemistry", "English", "Management")
LOCATIONS = ("Academic Block", "Science Block", "CSE Block", "ECE Block", "Mechanical Block", "Civil Block", "Library", "Laboratory", "Auditorium", "Seminar Hall", "Administrative Block", "Hostel", "Parking Area")
CATEGORIES: dict[str, tuple[str, ...]] = {
    "IT Support": ("Computer", "Projector", "Printer", "Software", "Login/Access", "Other IT Issue"),
    "Network Support": ("Wi-Fi", "Internet", "LAN", "Network Access", "Network Outage"),
    "Electrical & Maintenance": ("Fan", "Light", "AC", "Power", "Electrical Equipment"),
    "Infrastructure": ("Furniture", "Plumbing", "Classroom", "Building Maintenance"),
    "Housekeeping": ("Cleaning", "Washroom", "Waste", "General Housekeeping"),
    "Laboratory Support": ("Lab Computer", "Lab Equipment", "Lab Network", "Lab Maintenance"),
    "Transport & Logistics": ("Transport", "Vehicle", "Logistics"),
    "Library Support": ("Library Access", "Library Equipment", "Library Resources"),
    "Procurement & Stores": ("Equipment Request", "Stationery", "Stores", "Procurement"),
    "Academic Support": ("Academic Resources", "Classroom Support", "Academic System"),
    "Administration": ("Administrative Request", "Documentation", "General Administration"),
    "Security": ("Security Issue", "Access Control", "Safety Concern"),
}
SAMPLE_TICKETS = (
    ("Projector not working in CSE classroom", "IT Support", "Projector", "CSE", "New", "High", "Urgent", "CSE Block", "Ananya Rao"),
    ("Wi-Fi unavailable in Science Block", "Network Support", "Wi-Fi", "Science", "In Progress", "High", "Urgent", "Science Block", "Rahul Kumar"),
    ("Printer not responding in Faculty Room", "IT Support", "Printer", "CSE-AI", "Assigned", "Medium", "Normal", "CSE Block", "Priya Sharma"),
    ("AC not cooling in Seminar Hall", "Electrical & Maintenance", "AC", "ECE", "Pending", "High", "Urgent", "Seminar Hall", "Kiran Reddy"),
    ("Ceiling fan not working in Room 204", "Electrical & Maintenance", "Fan", "EEE", "Resolved", "Medium", "Normal", "Academic Block", "Sneha Patel"),
    ("Lab computer not starting", "Laboratory Support", "Lab Computer", "Mechanical", "Closed", "Critical", "Urgent", "Laboratory", "Arjun Kumar"),
    ("Classroom light flickering", "Electrical & Maintenance", "Light", "Civil", "Escalated", "High", "Urgent", "Civil Block", "Meena Rao"),
    ("Furniture repair required", "Infrastructure", "Furniture", "Science", "In Progress", "Low", "Normal", "Science Block", "Sanjay Reddy"),
    ("Library computer issue", "Library Support", "Library Equipment", "Mathematics", "New", "Medium", "Normal", "Library", "Ananya Rao"),
    ("Laboratory equipment issue", "Laboratory Support", "Lab Equipment", "CSE-AI", "Assigned", "Critical", "Urgent", "Laboratory", "Rahul Kumar"),
    ("Transport request", "Transport & Logistics", "Transport", "ECE", "Pending", "Low", "Normal", "Parking Area", "Priya Sharma"),
    ("Stationery/equipment procurement request", "Procurement & Stores", "Stationery", "CSE", "Resolved", "Low", "Normal", "Administrative Block", "Kiran Reddy"),
)
SEED_USERS = (
    ("FAC001", "Ananya Rao", "CSE", "Faculty", "faculty123", None),
    ("FAC002", "Rahul Kumar", "CSE-AI", "Faculty", "faculty123", None),
    ("FAC003", "Priya Sharma", "ECE", "Faculty", "faculty123", None),
    ("FAC004", "Kiran Reddy", "EEE", "Faculty", "faculty123", None),
    ("FAC005", "Sneha Patel", "Mechanical", "Faculty", "faculty123", None),
    ("FAC006", "Arjun Kumar", "Civil", "Faculty", "faculty123", None),
    ("FAC007", "Meena Rao", "Science", "Faculty", "faculty123", None),
    ("FAC008", "Sanjay Reddy", "Mathematics", "Faculty", "faculty123", None),
    ("IT001", "Rahul Support", "IT Support", "Team Member", "team123", "IT Support"),
    ("NET001", "Network Support", "Network Support", "Team Member", "team123", "Network Support"),
    ("ELE001", "Electrical Support", "Electrical & Maintenance", "Team Member", "team123", "Electrical & Maintenance"),
    ("LAB001", "Laboratory Support", "Laboratory Support", "Team Member", "team123", "Laboratory Support"),
    ("ADM001", "System Administrator", "Administration", "Administrator", "admin123", "Administration"),
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def sla_minutes(priority: str, db: sqlite3.Connection | None = None) -> tuple[int, int]:
    defaults = SLA_MINUTES.get(priority, SLA_MINUTES["Medium"])
    if db is not None:
        row = db.execute("SELECT response_minutes,resolution_minutes,active FROM sla_settings WHERE priority=?", (priority,)).fetchone()
    else:
        with connect() as connection:
            row = connection.execute("SELECT response_minutes,resolution_minutes,active FROM sla_settings WHERE priority=?", (priority,)).fetchone()
    if not row or not row["active"]:
        return defaults
    return int(row["response_minutes"]), int(row["resolution_minutes"])


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 240_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def initialize_database() -> None:
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL, role TEXT NOT NULL, team_name TEXT, designation TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id), expires_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS teams (name TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS subcategories (category TEXT NOT NULL, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(category, name));
            CREATE TABLE IF NOT EXISTS routing_rules (category TEXT NOT NULL, subcategory TEXT NOT NULL, team_name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(category, subcategory));
            CREATE TABLE IF NOT EXISTS locations (name TEXT PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS sla_settings (priority TEXT PRIMARY KEY, response_minutes INTEGER NOT NULL, resolution_minutes INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE NOT NULL, subject TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL, subcategory TEXT NOT NULL, faculty_id TEXT NOT NULL REFERENCES users(user_id), faculty_name TEXT NOT NULL, department TEXT NOT NULL, location TEXT NOT NULL, people_affected INTEGER NOT NULL DEFAULT 1, urgency TEXT NOT NULL, priority TEXT NOT NULL, team_name TEXT NOT NULL, assigned_to TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, response_deadline TEXT NOT NULL, resolution_deadline TEXT NOT NULL, attachment TEXT, shared INTEGER NOT NULL DEFAULT 1, sla_alerted INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS participants (ticket_id INTEGER NOT NULL REFERENCES tickets(id), faculty_id TEXT NOT NULL REFERENCES users(user_id), joined_at TEXT NOT NULL, PRIMARY KEY(ticket_id, faculty_id));
            CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL REFERENCES tickets(id), author_id TEXT NOT NULL, author_name TEXT NOT NULL, comment TEXT NOT NULL, created_at TEXT NOT NULL, internal INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ticket_history (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL REFERENCES tickets(id), action TEXT NOT NULL, detail TEXT NOT NULL, actor_id TEXT NOT NULL, actor_name TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(user_id), title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, read INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS access_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, faculty_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, department TEXT NOT NULL, designation TEXT NOT NULL, phone TEXT NOT NULL, password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending', created_at TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        for priority, (response, resolution) in SLA_MINUTES.items():
            db.execute("INSERT OR IGNORE INTO sla_settings(priority,response_minutes,resolution_minutes) VALUES(?,?,?)", (priority, response, resolution))
        seeded = db.execute("SELECT value FROM settings WHERE key='seeded'").fetchone()
        if seeded:
            return
        for user_id, name, department, role, password, team_name in SEED_USERS:
            db.execute("INSERT INTO users(user_id,name,department,role,team_name,designation,password_hash) VALUES(?,?,?,?,?,?,?)", (user_id, name, department, role, team_name, role if role == "Faculty" else "Support Staff", password_hash(password)))
        team_names = set(CATEGORIES) | {"Administration"}
        for name in team_names:
            db.execute("INSERT OR IGNORE INTO teams(name) VALUES(?)", (name,))
        for name in CATEGORIES:
            db.execute("INSERT INTO categories(name) VALUES(?)", (name,))
            for subcategory in CATEGORIES[name]:
                db.execute("INSERT INTO subcategories(category,name) VALUES(?,?)", (name, subcategory))
                team_name = "IT Support" if name == "IT Support" else name
                db.execute("INSERT INTO routing_rules(category,subcategory,team_name) VALUES(?,?,?)", (name, subcategory, team_name))
        for name in LOCATIONS:
            db.execute("INSERT INTO locations(name) VALUES(?)", (name,))
        for priority, (response, resolution) in SLA_MINUTES.items():
            db.execute("INSERT INTO settings(key,value) VALUES(?,?)", (f"sla:{priority}", json.dumps({"response": response, "resolution": resolution})))
        for index, sample in enumerate(SAMPLE_TICKETS, start=1):
            subject, team, subcategory, department, status, priority, urgency, location, faculty_name = sample
            faculty = db.execute("SELECT user_id FROM users WHERE name=?", (faculty_name,)).fetchone()
            created = datetime.now(timezone.utc) - timedelta(hours=index)
            response, resolution = SLA_MINUTES[priority]
            token = f"FT-{index:05d}"
            cursor = db.execute("""INSERT INTO tickets(token,subject,description,category,subcategory,faculty_id,faculty_name,department,location,people_affected,urgency,priority,team_name,assigned_to,status,created_at,updated_at,response_deadline,resolution_deadline)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (token, subject, f"Faculty service request: {subject}.", team, subcategory, faculty["user_id"], faculty_name, department, location, 1, urgency, priority, team, "IT001" if status in ("Assigned", "In Progress") and team == "IT Support" else None, status, created.isoformat(timespec="seconds"), created.isoformat(timespec="seconds"), (created + timedelta(minutes=response)).isoformat(timespec="seconds"), (created + timedelta(minutes=resolution)).isoformat(timespec="seconds")))
            event(db, cursor.lastrowid, "Ticket created", f"Ticket {token} created", faculty["user_id"], faculty_name)
        db.execute("INSERT INTO settings(key,value) VALUES('seeded','true')")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="FacultyHelp Campus Support Portal", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["json"] = json


def user_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {"userId": row["user_id"], "name": row["name"], "department": row["department"], "role": row["role"], "teamName": row["team_name"]}


def find_user(user_id: str) -> sqlite3.Row | None:
    with connect() as db:
        return db.execute("SELECT * FROM users WHERE user_id=? AND active=1", (user_id.upper(),)).fetchone()


def session_user(request: Request) -> sqlite3.Row | None:
    token = request.cookies.get("facultyhelp_session", "")
    if not token:
        return None
    with connect() as db:
        return db.execute("SELECT u.* FROM sessions s JOIN users u ON u.user_id=s.user_id WHERE s.token=? AND s.expires_at>? AND u.active=1", (token, now_iso())).fetchone()


def require_user(request: Request) -> sqlite3.Row:
    user = session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return user


def require_admin(user: sqlite3.Row) -> None:
    if user["role"] != "Administrator":
        raise HTTPException(status_code=403, detail="Administrator access required")


def can_view(ticket: sqlite3.Row | dict[str, Any], user: sqlite3.Row | dict[str, Any]) -> bool:
    if user["role"] == "Administrator":
        return True
    if user["role"] == "Team Member":
        return ticket["team_name"] == user["team_name"]
    return ticket["shared"] == 1 or ticket["faculty_id"] == user["user_id"]


def sla_status(ticket: sqlite3.Row | dict[str, Any]) -> str:
    if ticket["status"] == "Closed":
        return "On Track"
    try:
        remaining = (datetime.fromisoformat(ticket["resolution_deadline"]) - datetime.now(timezone.utc)).total_seconds()
        created = datetime.fromisoformat(ticket["created_at"])
        total = (datetime.fromisoformat(ticket["resolution_deadline"]) - created).total_seconds()
    except (TypeError, ValueError):
        return "On Track"
    if remaining < 0:
        return "Breached"
    return "At Risk" if remaining < max(1800, total * 0.2) else "On Track"


def event(db: sqlite3.Connection, ticket_id: int, action: str, detail: str, actor_id: str, actor_name: str) -> None:
    db.execute("INSERT INTO ticket_history(ticket_id,action,detail,actor_id,actor_name,created_at) VALUES(?,?,?,?,?,?)", (ticket_id, action, detail, actor_id, actor_name, now_iso()))


def notify(db: sqlite3.Connection, user_id: str, title: str, body: str) -> None:
    db.execute("INSERT INTO notifications(user_id,title,body,created_at) VALUES(?,?,?,?)", (user_id, title, body, now_iso()))


def ticket_rows(user: sqlite3.Row, *, own_only: bool = False, status: str = "", priority: str = "", search: str = "") -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM tickets ORDER BY updated_at DESC").fetchall()
        result = []
        for row in rows:
            if not can_view(row, user) or (own_only and row["faculty_id"] != user["user_id"]):
                continue
            if status and row["status"] != status:
                continue
            if priority and row["priority"] != priority:
                continue
            if search and search.casefold() not in " ".join(str(row[key] or "") for key in ("token", "subject", "faculty_name", "category", "subcategory", "team_name", "status")).casefold():
                continue
            ticket = dict(row)
            ticket["affected_count"] = 1 + db.execute("SELECT COUNT(*) FROM participants WHERE ticket_id=?", (row["id"],)).fetchone()[0]
            ticket["sla_status"] = sla_status(ticket)
            result.append(ticket)
        return result


def page_context(request: Request, user: sqlite3.Row | None, page: str, **values: Any) -> dict[str, Any]:
    unread = 0
    if user:
        with connect() as db:
            unread = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (user["user_id"],)).fetchone()[0]
    return {"request": request, "user": dict(user) if user else None, "page": page, "unread": unread, "statuses": STATUSES, "priorities": PRIORITIES, **values}


def render(request: Request, user: sqlite3.Row | None, page: str, *, status_code: int = 200, **values: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", page_context(request, user, page, **values), status_code=status_code)


def ticket_for_user(token: str, user: sqlite3.Row) -> sqlite3.Row:
    with connect() as db:
        ticket = db.execute("SELECT * FROM tickets WHERE token=?", (token,)).fetchone()
    if not ticket or not can_view(ticket, user):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def api_ticket(ticket: dict[str, Any] | sqlite3.Row) -> dict[str, Any]:
    item = dict(ticket)
    if item.get("attachment"):
        item["attachment"] = json.loads(item["attachment"])
    item.update({
        "facultyId": item.get("faculty_id"),
        "facultyName": item.get("faculty_name"),
        "teamName": item.get("team_name"),
        "assignedTo": item.get("assigned_to"),
        "createdAt": item.get("created_at"),
        "updatedAt": item.get("updated_at"),
        "responseDeadline": item.get("response_deadline"),
        "resolutionDeadline": item.get("resolution_deadline"),
        "peopleAffected": item.get("people_affected", 1),
        "shared": bool(item.get("shared", 1)),
        "slaStatus": item.get("sla_status") or sla_status(item),
        "slaAlerted": bool(item.get("sla_alerted", 0)),
    })
    if "affected_count" in item:
        item["affectedCount"] = item["affected_count"]
    return item


def api_resource(kind: str, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    if kind == "users":
        return {"id": item["user_id"], "userId": item["user_id"], "name": item["name"], "department": item["department"], "role": item["role"], "designation": item["designation"], "phone": item["phone"], "teamName": item["team_name"], "active": bool(item["active"])}
    elif kind in ("teams", "categories", "locations"):
        return {"id": item["name"], "name": item["name"], "active": bool(item["active"])}
    elif kind == "routing_rules":
        return {"id": f"{item['category']}:{item['subcategory']}", "category": item["category"], "subcategory": item["subcategory"], "teamName": item["team_name"], "active": bool(item["active"])}
    elif kind == "subcategories":
        return {"id": f"{item['category']}:{item['name']}", "category": item["category"], "name": item["name"], "active": bool(item["active"])}
    elif kind == "access_requests":
        return {"id": item["id"], "facultyId": item["faculty_id"], "name": item["name"], "department": item["department"], "designation": item["designation"], "phone": item["phone"], "status": item["status"], "createdAt": item["created_at"], "reviewedBy": item["reviewed_by"], "reviewedAt": item["reviewed_at"]}
    elif kind == "sla_settings":
        return {"id": item["priority"], "priority": item["priority"], "responseMinutes": item["response_minutes"], "resolutionMinutes": item["resolution_minutes"], "active": bool(item["active"])}
    return item


@app.get("/api/_healthcheck")
def healthcheck() -> dict[str, Any]:
    return {"ok": True, "app": "FacultyHelp"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if os.getenv("VERCEL"):
        return FileResponse(BASE_DIR / "dist" / "index.html")
    user = session_user(request)
    if not user:
        with connect() as db:
            accounts = db.execute("SELECT user_id,name,role,team_name FROM users WHERE active=1 ORDER BY role,name").fetchall()
        return render(request, None, "login", accounts=accounts, error="")
    tickets = ticket_rows(user)
    counts = {status: sum(ticket["status"] == status for ticket in tickets) for status in STATUSES}
    counts["total"] = len(tickets)
    return render(request, user, "dashboard", tickets=tickets[:8], counts=counts)


@app.post("/login")
def login(request: Request, user_id: str = Form(...), password: str = Form(...)):
    account = find_user(user_id.strip())
    if not account or not verify_password(password, account["password_hash"]):
        with connect() as db:
            accounts = db.execute("SELECT user_id,name,role,team_name FROM users WHERE active=1 ORDER BY role,name").fetchall()
        return render(request, None, "login", accounts=accounts, error="Invalid user ID or password.", status_code=401)
    token = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token, account["user_id"], (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(timespec="seconds")))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("facultyhelp_session", token, httponly=True, samesite="lax", max_age=8 * 60 * 60)
    return response


@app.post("/logout")
def logout(request: Request):
    token = request.cookies.get("facultyhelp_session", "")
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE token=?", (token,))
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("facultyhelp_session")
    return response


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return render(request, None, "signup", departments=DEPARTMENTS, message="")


@app.post("/signup")
def signup(request: Request, faculty_id: str = Form(...), name: str = Form(...), department: str = Form(...), password: str = Form(...), designation: str = Form("Faculty"), phone: str = Form("")):
    faculty_id = faculty_id.strip().upper()
    if len(password) < 6 or not name.strip() or department not in DEPARTMENTS:
        return render(request, None, "signup", departments=DEPARTMENTS, message="Enter a name, valid department, and password of at least 6 characters.", status_code=400)
    with connect() as db:
        exists = db.execute("SELECT 1 FROM users WHERE user_id=? UNION SELECT 1 FROM access_requests WHERE faculty_id=? AND status='Pending'", (faculty_id, faculty_id)).fetchone()
        if exists:
            return render(request, None, "signup", departments=DEPARTMENTS, message="This ID already exists or has a pending request.", status_code=409)
        db.execute("INSERT INTO access_requests(faculty_id,name,department,designation,phone,password_hash,created_at) VALUES(?,?,?,?,?,?,?)", (faculty_id, name.strip(), department, designation.strip(), phone.strip(), password_hash(password), now_iso()))
        for admin in db.execute("SELECT user_id FROM users WHERE role='Administrator' AND active=1"):
            notify(db, admin["user_id"], "Faculty access request", f"{faculty_id} · {name.strip()}")
    return render(request, None, "signup", departments=DEPARTMENTS, message="Your access request was sent to the administrator.")


@app.get("/tickets", response_class=HTMLResponse)
def tickets_page(request: Request, user: sqlite3.Row = Depends(require_user), status: str = "", priority: str = "", q: str = ""):
    return render(request, user, "tickets", tickets=ticket_rows(user, own_only=user["role"] == "Faculty", status=status, priority=priority, search=q), filters={"status": status, "priority": priority, "q": q})


@app.get("/issues", response_class=HTMLResponse)
def shared_issues(request: Request, user: sqlite3.Row = Depends(require_user)):
    rows = [ticket for ticket in ticket_rows(user) if ticket["faculty_id"] != user["user_id"] and ticket["shared"]]
    return render(request, user, "issues", tickets=rows)


@app.get("/tickets/new", response_class=HTMLResponse)
def new_ticket_page(request: Request, user: sqlite3.Row = Depends(require_user)):
    if user["role"] != "Faculty":
        raise HTTPException(status_code=403, detail="Only faculty can create tickets")
    with connect() as db:
        categories = db.execute("SELECT name FROM categories WHERE active=1 ORDER BY name").fetchall()
        locations = db.execute("SELECT name FROM locations WHERE active=1 ORDER BY name").fetchall()
        routes = [dict(row) for row in db.execute("SELECT category,subcategory,team_name FROM routing_rules WHERE active=1 ORDER BY category,subcategory")]
    return render(request, user, "new-ticket", categories=categories, locations=locations, routes=routes, message="")


@app.post("/tickets/new")
async def create_ticket(request: Request, user: sqlite3.Row = Depends(require_user), category: str = Form(...), subcategory: str = Form(...), subject: str = Form(...), description: str = Form(...), location: str = Form(...), people_affected: int = Form(1), priority: str = Form("Medium"), urgency: str = Form("Normal"), attachment: UploadFile | None = File(None)):
    if user["role"] != "Faculty":
        raise HTTPException(status_code=403, detail="Only faculty can create tickets")
    if priority not in PRIORITIES or urgency not in ("Low", "Normal", "Urgent") or people_affected < 1:
        raise HTTPException(status_code=400, detail="Invalid priority, urgency, or affected count")
    with connect() as db:
        route = db.execute("SELECT team_name FROM routing_rules WHERE category=? AND subcategory=? AND active=1", (category, subcategory)).fetchone()
        valid_location = db.execute("SELECT 1 FROM locations WHERE name=? AND active=1", (location,)).fetchone()
        if not route or not valid_location:
            raise HTTPException(status_code=400, detail="Choose an active category, subcategory, and location")
        attached_url = None
        if attachment and attachment.filename:
            allowed = {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "video/quicktime", "application/pdf"}
            if attachment.content_type not in allowed:
                raise HTTPException(status_code=400, detail="Unsupported file type")
            contents = await attachment.read(5_000_001)
            if len(contents) > 5_000_000:
                raise HTTPException(status_code=413, detail="File exceeds the 5 MB upload limit")
            safe_name = Path(attachment.filename).name
            stored_name = f"{secrets.token_hex(8)}-{safe_name}"
            (UPLOAD_DIR / stored_name).write_bytes(contents)
            attached_url = json.dumps({"fileName": safe_name, "url": f"/uploads/{stored_name}", "contentType": attachment.content_type})
        last = db.execute("SELECT MAX(CAST(SUBSTR(token,4) AS INTEGER)) FROM tickets").fetchone()[0] or 0
        token = f"FT-{last + 1:05d}"
        created = datetime.now(timezone.utc)
        response_minutes, resolution_minutes = sla_minutes(priority, db)
        cursor = db.execute("""INSERT INTO tickets(token,subject,description,category,subcategory,faculty_id,faculty_name,department,location,people_affected,urgency,priority,team_name,status,created_at,updated_at,response_deadline,resolution_deadline,attachment)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'New',?,?,?,?,?)""", (token, subject.strip(), description.strip(), category, subcategory, user["user_id"], user["name"], user["department"], location, people_affected, urgency, priority, route["team_name"], created.isoformat(timespec="seconds"), created.isoformat(timespec="seconds"), (created + timedelta(minutes=response_minutes)).isoformat(timespec="seconds"), (created + timedelta(minutes=resolution_minutes)).isoformat(timespec="seconds"), attached_url))
        event(db, cursor.lastrowid, "Ticket created", f"Ticket {token} created", user["user_id"], user["name"])
        event(db, cursor.lastrowid, "Ticket routed", f"Automatically routed to {route['team_name']}", "SYSTEM", "System")
        for member in db.execute("SELECT user_id FROM users WHERE role='Team Member' AND team_name=? AND active=1", (route["team_name"],)):
            notify(db, member["user_id"], "New ticket routed", f"{token} · {subject.strip()}")
        notify(db, user["user_id"], "Ticket created", f"{token} routed to {route['team_name']}")
    return RedirectResponse(f"/tickets/{token}", status_code=303)


@app.get("/tickets/{token}", response_class=HTMLResponse)
def ticket_detail(request: Request, token: str, user: sqlite3.Row = Depends(require_user)):
    ticket = ticket_for_user(token, user)
    item = dict(ticket)
    item["sla_status"] = sla_status(item)
    with connect() as db:
        item["affected_count"] = 1 + db.execute("SELECT COUNT(*) FROM participants WHERE ticket_id=?", (item["id"],)).fetchone()[0]
        comments = db.execute("SELECT * FROM comments WHERE ticket_id=? AND (internal=0 OR ?!='Faculty') ORDER BY created_at", (item["id"], user["role"])).fetchall()
        history = db.execute("SELECT * FROM ticket_history WHERE ticket_id=? ORDER BY created_at", (item["id"],)).fetchall()
    return render(request, user, "ticket-detail", ticket=item, comments=comments, history=history, message="")


@app.post("/tickets/{token}/action")
def ticket_action(token: str, request: Request, user: sqlite3.Row = Depends(require_user), action: str = Form(...), status: str = Form("")):
    ticket = ticket_for_user(token, user)
    if user["role"] == "Faculty" and action != "close":
        raise HTTPException(status_code=403, detail="Faculty cannot perform this action")
    if user["role"] == "Team Member" and ticket["team_name"] != user["team_name"]:
        raise HTTPException(status_code=403, detail="Ticket is outside your team queue")
    if action == "accept":
        new_status, assignee = "Assigned", user["user_id"]
        detail = f"Assigned to {user['name']}"
    elif action == "status" and status in STATUSES:
        new_status, assignee, detail = status, ticket["assigned_to"], f"Status changed to {status}"
    elif action == "resolve":
        new_status, assignee, detail = "Resolved", ticket["assigned_to"], "Ticket resolved"
    elif action == "close":
        new_status, assignee, detail = "Closed", ticket["assigned_to"], "Ticket closed"
    elif action == "escalate":
        new_status, assignee, detail = "Escalated", ticket["assigned_to"], "Ticket escalated"
    else:
        raise HTTPException(status_code=400, detail="Unsupported action or status")
    with connect() as db:
        db.execute("UPDATE tickets SET status=?,assigned_to=?,updated_at=? WHERE id=?", (new_status, assignee, now_iso(), ticket["id"]))
        event(db, ticket["id"], detail, detail, user["user_id"], user["name"])
        notify(db, ticket["faculty_id"], f"Ticket {token} updated", detail)
    return RedirectResponse(f"/tickets/{token}", status_code=303)


@app.post("/tickets/{token}/join")
def join_issue(token: str, user: sqlite3.Row = Depends(require_user)):
    if user["role"] != "Faculty":
        raise HTTPException(status_code=403, detail="Faculty access required")
    with connect() as db:
        ticket = db.execute("SELECT * FROM tickets WHERE token=? AND shared=1", (token,)).fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Shared ticket not found")
        added = db.execute("INSERT OR IGNORE INTO participants(ticket_id,faculty_id,joined_at) VALUES(?,?,?)", (ticket["id"], user["user_id"], now_iso())).rowcount
        if added:
            event(db, ticket["id"], "Faculty joined issue", f"{user['name']} is also affected by this issue", user["user_id"], user["name"])
            notify(db, ticket["faculty_id"], "Faculty joined your ticket", f"{user['name']} reported the same issue")
    return RedirectResponse(f"/tickets/{token}", status_code=303)


@app.post("/tickets/{token}/comments")
def add_comment(token: str, user: sqlite3.Row = Depends(require_user), comment: str = Form(...)):
    ticket = ticket_for_user(token, user)
    text = comment.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comment is required")
    with connect() as db:
        db.execute("INSERT INTO comments(ticket_id,author_id,author_name,comment,created_at) VALUES(?,?,?,?,?)", (ticket["id"], user["user_id"], user["name"], text, now_iso()))
        event(db, ticket["id"], "Comment added", "Comment added", user["user_id"], user["name"])
    return RedirectResponse(f"/tickets/{token}", status_code=303)


@app.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request, user: sqlite3.Row = Depends(require_user)):
    with connect() as db:
        items = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC", (user["user_id"],)).fetchall()
    return render(request, user, "notifications", notifications=items)


@app.post("/notifications/{notification_id}/read")
def mark_notification(notification_id: int, user: sqlite3.Row = Depends(require_user)):
    with connect() as db:
        db.execute("UPDATE notifications SET read=1 WHERE id=? AND user_id=?", (notification_id, user["user_id"]))
    return RedirectResponse("/notifications", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: sqlite3.Row = Depends(require_user)):
    require_admin(user)
    with connect() as db:
        resources = {"users": db.execute("SELECT user_id,name,department,role,team_name,active FROM users ORDER BY role,name").fetchall(), "teams": db.execute("SELECT * FROM teams ORDER BY name").fetchall(), "categories": db.execute("SELECT * FROM categories ORDER BY name").fetchall(), "routing_rules": db.execute("SELECT * FROM routing_rules ORDER BY category,subcategory").fetchall(), "locations": db.execute("SELECT * FROM locations ORDER BY name").fetchall(), "access_requests": db.execute("SELECT * FROM access_requests ORDER BY created_at DESC").fetchall()}
    return render(request, user, "admin", resources=resources, message="")


@app.post("/admin/access/{request_id}/{decision}")
def review_access(request_id: int, decision: str, user: sqlite3.Row = Depends(require_user)):
    require_admin(user)
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    with connect() as db:
        access = db.execute("SELECT * FROM access_requests WHERE id=? AND status='Pending'", (request_id,)).fetchone()
        if not access:
            raise HTTPException(status_code=404, detail="Pending request not found")
        state = "Approved" if decision == "approve" else "Rejected"
        if decision == "approve":
            db.execute("INSERT INTO users(user_id,name,department,role,designation,phone,password_hash) VALUES(?,?,?,'Faculty',?,?,?)", (access["faculty_id"], access["name"], access["department"], access["designation"], access["phone"], access["password_hash"]))
        db.execute("UPDATE access_requests SET status=?,reviewed_by=?,reviewed_at=? WHERE id=?", (state, user["user_id"], now_iso(), request_id))
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/resources")
def add_admin_resource(user: sqlite3.Row = Depends(require_user), kind: str = Form(...), name: str = Form(""), category: str = Form(""), subcategory: str = Form(""), team_name: str = Form("")):
    require_admin(user)
    with connect() as db:
        if kind == "team":
            if not name.strip():
                raise HTTPException(status_code=400, detail="Team name is required")
            db.execute("INSERT OR IGNORE INTO teams(name) VALUES(?)", (name.strip(),))
        elif kind == "category":
            if not name.strip():
                raise HTTPException(status_code=400, detail="Category name is required")
            db.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (name.strip(),))
        elif kind == "location":
            if not name.strip():
                raise HTTPException(status_code=400, detail="Location name is required")
            db.execute("INSERT OR IGNORE INTO locations(name) VALUES(?)", (name.strip(),))
        elif kind == "routing":
            if not category.strip() or not subcategory.strip() or not team_name.strip():
                raise HTTPException(status_code=400, detail="Category, subcategory, and team are required")
            if not db.execute("SELECT 1 FROM teams WHERE name=? AND active=1", (team_name,)).fetchone():
                raise HTTPException(status_code=400, detail="Choose an active support team")
            try:
                db.execute("INSERT INTO routing_rules(category,subcategory,team_name) VALUES(?,?,?)", (category, subcategory, team_name))
                db.execute("INSERT OR IGNORE INTO subcategories(category,name) VALUES(?,?)", (category, subcategory))
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="An active routing rule already exists for that category and subcategory") from exc
        else:
            raise HTTPException(status_code=400, detail="Unsupported resource")
    return RedirectResponse("/admin", status_code=303)


@app.get("/reports.csv")
def download_report(user: sqlite3.Row = Depends(require_user)):
    if user["role"] not in ("Administrator", "Team Member"):
        raise HTTPException(status_code=403, detail="Reports access required")
    tickets = ticket_rows(user)
    output = io.StringIO()
    columns = ("token", "subject", "category", "subcategory", "faculty_name", "department", "team_name", "status", "priority", "location", "created_at", "resolution_deadline", "sla_status")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows({**ticket, "sla_status": ticket["sla_status"]} for ticket in tickets)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=facultyhelp-report.csv"})


def api_body_user(data: dict[str, Any]) -> sqlite3.Row:
    token = str(data.get("sessionToken", ""))
    with connect() as db:
        session = db.execute("SELECT user_id FROM sessions WHERE token=? AND expires_at>?", (token, now_iso())).fetchone()
        user = db.execute("SELECT * FROM users WHERE user_id=? AND active=1", (session["user_id"],)).fetchone() if session else None
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


@app.post("/api/auth/options")
def api_auth_options():
    with connect() as db:
        faculty = db.execute("SELECT user_id,name,department FROM users WHERE role='Faculty' AND active=1 ORDER BY name").fetchall()
        team = db.execute("SELECT user_id,name,team_name FROM users WHERE role='Team Member' AND active=1 ORDER BY name").fetchall()
    return {"faculty": [{"userId": row["user_id"], "name": row["name"], "department": row["department"]} for row in faculty], "teams": [{"userId": row["user_id"], "name": row["name"], "teamName": row["team_name"]} for row in team]}


@app.post("/api/auth/signup-request")
async def api_signup_request(request: Request):
    body = await request.json()
    faculty_id = str(body.get("facultyId", "")).strip().upper()
    name = str(body.get("name", "")).strip()
    department = str(body.get("department", "")).strip()
    password = str(body.get("password", ""))
    if not faculty_id or not name or department not in DEPARTMENTS or len(password) < 6:
        raise HTTPException(status_code=400, detail="Faculty ID, name, valid department, and a password of at least 6 characters are required")
    with connect() as db:
        exists = db.execute("SELECT 1 FROM users WHERE user_id=? UNION SELECT 1 FROM access_requests WHERE faculty_id=? AND status='Pending'", (faculty_id, faculty_id)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="This Faculty ID already exists or has a pending request")
        db.execute("INSERT INTO access_requests(faculty_id,name,department,designation,phone,password_hash,created_at) VALUES(?,?,?,?,?,?,?)", (faculty_id, name, department, str(body.get("designation", "Faculty")).strip(), str(body.get("phone", "")).strip(), password_hash(password), now_iso()))
        for admin in db.execute("SELECT user_id FROM users WHERE role='Administrator' AND active=1"):
            notify(db, admin["user_id"], "Faculty access request", f"{faculty_id} · {name}")
    return JSONResponse({"ok": True, "message": "Access request sent to the administrator for review."}, status_code=201)


@app.post("/api/auth/login")
async def api_login(request: Request):
    body = await request.json()
    user = find_user(str(body.get("userId", "")))
    if not user or not verify_password(str(body.get("password", "")), user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid User ID or password")
    token = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token, user["user_id"], (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(timespec="seconds")))
    return {"sessionToken": token, "user": user_public(user)}


@app.post("/api/auth/logout")
async def api_logout(request: Request):
    body = await request.json()
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE token=?", (str(body.get("sessionToken", "")),))
    return {"ok": True}


@app.post("/api/bootstrap")
async def api_bootstrap(request: Request):
    user = api_body_user(await request.json())
    tickets = ticket_rows(user)
    counts = {status: sum(ticket["status"] == status for ticket in tickets) for status in STATUSES}
    counts["slaBreached"] = sum(ticket["sla_status"] == "Breached" for ticket in tickets)
    with connect() as db:
        categories = db.execute("SELECT * FROM categories WHERE active=1 ORDER BY name").fetchall()
        subcategories = db.execute("SELECT * FROM subcategories WHERE active=1 ORDER BY category,name").fetchall()
        teams = db.execute("SELECT * FROM teams WHERE active=1 ORDER BY name").fetchall()
        locations = db.execute("SELECT * FROM locations WHERE active=1 ORDER BY name").fetchall()
        rules = db.execute("SELECT * FROM routing_rules WHERE active=1 ORDER BY category,subcategory").fetchall()
    return {"user": user_public(user), "dashboard": {"counts": counts, "tickets": [api_ticket(ticket) for ticket in tickets], "total": len(tickets)}, "categories": [api_resource("categories", row) for row in categories], "subcategories": [api_resource("subcategories", row) for row in subcategories], "teams": [api_resource("teams", row) for row in teams], "locations": [api_resource("locations", row) for row in locations], "routingRules": [api_resource("routing_rules", row) for row in rules]}


@app.post("/api/tickets/list")
async def api_ticket_list(request: Request):
    body = await request.json()
    user = api_body_user(body)
    tickets = ticket_rows(user, status=body.get("status", "") if body.get("status") != "All" else "", priority=body.get("priority", "") if body.get("priority") != "All" else "", search=str(body.get("search", "")))
    return {"tickets": [api_ticket(ticket) for ticket in tickets]}


@app.post("/api/tickets/detail")
async def api_ticket_detail(request: Request):
    body = await request.json()
    user = api_body_user(body)
    ticket = ticket_for_user(str(body.get("token", "")), user)
    with connect() as db:
        comments = db.execute("SELECT * FROM comments WHERE ticket_id=? ORDER BY created_at", (ticket["id"],)).fetchall()
        history = db.execute("SELECT * FROM ticket_history WHERE ticket_id=? ORDER BY created_at", (ticket["id"],)).fetchall()
        participants = db.execute("SELECT * FROM participants WHERE ticket_id=?", (ticket["id"],)).fetchall()
    item = api_ticket(ticket)
    item["affectedCount"] = len(participants) + 1
    comment_items = [{"id": row["id"], "ticketId": row["ticket_id"], "authorId": row["author_id"], "authorName": row["author_name"], "comment": row["comment"], "createdAt": row["created_at"], "internal": bool(row["internal"])} for row in comments]
    history_items = [{"id": row["id"], "action": row["action"], "detail": row["detail"], "actorId": row["actor_id"], "actorName": row["actor_name"], "createdAt": row["created_at"]} for row in history]
    participant_items = [{"ticketId": row["ticket_id"], "facultyId": row["faculty_id"], "facultyName": row["faculty_name"], "joinedAt": row["joined_at"]} for row in participants]
    return {"ticket": item, "comments": comment_items, "history": history_items, "participants": participant_items}


@app.post("/api/tickets")
async def api_create_ticket(request: Request):
    body = await request.json()
    user = api_body_user(body)
    if user["role"] != "Faculty":
        raise HTTPException(status_code=403, detail="Only faculty can create tickets")
    required = ("category", "subcategory", "subject", "description", "location")
    if any(not str(body.get(key, "")).strip() for key in required):
        raise HTTPException(status_code=400, detail="Category, subcategory, subject, description, and location are required")
    with connect() as db:
        route = db.execute("SELECT team_name FROM routing_rules WHERE category=? AND subcategory=? AND active=1", (body["category"], body["subcategory"])).fetchone()
        if not route or not db.execute("SELECT 1 FROM locations WHERE name=? AND active=1", (body["location"],)).fetchone():
            raise HTTPException(status_code=400, detail="No active routing rule or location exists")
        number = db.execute("SELECT MAX(CAST(SUBSTR(token,4) AS INTEGER)) FROM tickets").fetchone()[0] or 0
        token = f"FT-{number + 1:05d}"
        created = datetime.now(timezone.utc)
        priority = body.get("priority", "Medium") if body.get("priority") in PRIORITIES else "Medium"
        response_minutes, resolution_minutes = sla_minutes(priority, db)
        cursor = db.execute("""INSERT INTO tickets(token,subject,description,category,subcategory,faculty_id,faculty_name,department,location,people_affected,urgency,priority,team_name,status,created_at,updated_at,response_deadline,resolution_deadline)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'New',?,?,?,?)""", (token, str(body["subject"]).strip(), str(body["description"]).strip(), body["category"], body["subcategory"], user["user_id"], user["name"], user["department"], body["location"], max(1, int(body.get("peopleAffected", 1))), body.get("urgency", "Normal"), priority, route["team_name"], created.isoformat(timespec="seconds"), created.isoformat(timespec="seconds"), (created + timedelta(minutes=response_minutes)).isoformat(timespec="seconds"), (created + timedelta(minutes=resolution_minutes)).isoformat(timespec="seconds")))
        event(db, cursor.lastrowid, "Ticket created", f"Ticket {token} created", user["user_id"], user["name"])
        event(db, cursor.lastrowid, "Ticket routed", f"Automatically routed to {route['team_name']}", "SYSTEM", "System")
        for member in db.execute("SELECT user_id FROM users WHERE role='Team Member' AND team_name=? AND active=1", (route["team_name"],)):
            notify(db, member["user_id"], "New ticket routed", f"{token} · {body['subject']}")
        notify(db, user["user_id"], "Ticket created", f"{token} routed to {route['team_name']}")
    return JSONResponse({"ticket": {"token": token, "teamName": route["team_name"]}}, status_code=201)


@app.post("/api/tickets/join")
async def api_join_ticket(request: Request):
    body = await request.json()
    user = api_body_user(body)
    if user["role"] != "Faculty":
        raise HTTPException(status_code=403, detail="Faculty access required")
    with connect() as db:
        ticket = db.execute("SELECT * FROM tickets WHERE token=? AND shared=1", (body.get("token"),)).fetchone()
        if not ticket:
            raise HTTPException(status_code=404, detail="Shared ticket not found")
        added = db.execute("INSERT OR IGNORE INTO participants(ticket_id,faculty_id,joined_at) VALUES(?,?,?)", (ticket["id"], user["user_id"], now_iso())).rowcount
        if added:
            event(db, ticket["id"], "Faculty joined issue", f"{user['name']} is also affected by this issue", user["user_id"], user["name"])
            notify(db, ticket["faculty_id"], "Faculty joined your ticket", f"{user['name']} reported the same issue")
        count = db.execute("SELECT COUNT(*) FROM participants WHERE ticket_id=?", (ticket["id"],)).fetchone()[0] + 1
    return {"ok": True, "affectedCount": count}


@app.post("/api/comments")
async def api_comment(request: Request):
    body = await request.json()
    user = api_body_user(body)
    ticket = ticket_for_user(str(body.get("token", "")), user)
    comment = str(body.get("comment", "")).strip()
    if not comment:
        raise HTTPException(status_code=400, detail="Comment is required")
    with connect() as db:
        cursor = db.execute("INSERT INTO comments(ticket_id,author_id,author_name,comment,created_at) VALUES(?,?,?,?,?)", (ticket["id"], user["user_id"], user["name"], comment, now_iso()))
        event(db, ticket["id"], "Comment added", "Comment added", user["user_id"], user["name"])
    return {"id": cursor.lastrowid}


@app.post("/api/tickets/action")
async def api_ticket_action(request: Request):
    body = await request.json()
    user = api_body_user(body)
    ticket = ticket_for_user(str(body.get("token", "")), user)
    action = body.get("action")
    if user["role"] == "Faculty" and action != "close":
        raise HTTPException(status_code=403, detail="Faculty cannot perform this action")
    if user["role"] == "Team Member" and ticket["team_name"] != user["team_name"]:
        raise HTTPException(status_code=403, detail="Ticket is outside your team queue")
    if action == "accept":
        new_status, assignee, detail = "Assigned", user["user_id"], f"Assigned to {user['name']}"
    elif action == "status" and body.get("status") in STATUSES:
        new_status, assignee, detail = body["status"], ticket["assigned_to"], f"Status changed to {body['status']}"
    elif action in ("resolve", "close", "escalate"):
        new_status = {"resolve": "Resolved", "close": "Closed", "escalate": "Escalated"}[action]
        assignee, detail = ticket["assigned_to"], f"Ticket {new_status.lower()}"
    else:
        raise HTTPException(status_code=400, detail="Unsupported ticket action")
    with connect() as db:
        db.execute("UPDATE tickets SET status=?,assigned_to=?,updated_at=? WHERE id=?", (new_status, assignee, now_iso(), ticket["id"]))
        event(db, ticket["id"], detail, detail, user["user_id"], user["name"])
        notify(db, ticket["faculty_id"], f"Ticket {ticket['token']} updated", detail)
    return {"ok": True, "status": new_status}


@app.post("/api/upload")
async def api_upload(request: Request):
    body = await request.json()
    user = api_body_user(body)
    ticket = ticket_for_user(str(body.get("token", "")), user)
    filename = Path(str(body.get("fileName", ""))).name
    content_type = str(body.get("contentType", ""))
    encoded = str(body.get("base64", ""))
    allowed = {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "video/quicktime", "application/pdf"}
    if not filename or content_type not in allowed or not encoded:
        raise HTTPException(status_code=400, detail="A supported evidence file is required")
    if len(encoded) > 7_000_000:
        raise HTTPException(status_code=413, detail="File exceeds the 5 MB upload limit")
    try:
        contents = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 file data") from exc
    if not contents or len(contents) > 5_000_000:
        raise HTTPException(status_code=413, detail="File exceeds the 5 MB upload limit")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    stored_name = f"{ticket['token']}-{secrets.token_hex(8)}-{safe_name}"
    (UPLOAD_DIR / stored_name).write_bytes(contents)
    attachment = {"fileName": safe_name, "contentType": content_type, "path": stored_name, "url": f"/uploads/{stored_name}"}
    with connect() as db:
        db.execute("UPDATE tickets SET attachment=?,updated_at=? WHERE id=?", (json.dumps(attachment), now_iso(), ticket["id"]))
        event(db, ticket["id"], "Attachment uploaded", safe_name, user["user_id"], user["name"])
    return {"attachment": attachment}


@app.post("/api/notifications/list")
async def api_notifications(request: Request):
    user = api_body_user(await request.json())
    with connect() as db:
        rows = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC", (user["user_id"],)).fetchall()
    return {"notifications": [{"id": row["id"], "userId": row["user_id"], "title": row["title"], "body": row["body"], "createdAt": row["created_at"], "read": bool(row["read"])} for row in rows]}


@app.post("/api/notifications/read")
async def api_notification_read(request: Request):
    body = await request.json()
    user = api_body_user(body)
    with connect() as db:
        db.execute("UPDATE notifications SET read=1 WHERE id=? AND user_id=?", (body.get("id"), user["user_id"]))
    return {"ok": True}


@app.post("/api/admin/data")
async def api_admin_data(request: Request):
    user = api_body_user(await request.json())
    require_admin(user)
    with connect() as db:
        resources = {name: [api_resource(name, row) for row in db.execute(f"SELECT * FROM {name}")] for name in ("users", "teams", "categories", "subcategories", "routing_rules", "locations", "access_requests", "sla_settings")}
        resources["departments"] = [{"id": name, "name": name, "active": True} for name in DEPARTMENTS]
        resources["tickets"] = [api_ticket(ticket) for ticket in ticket_rows(user)]
    return resources


@app.post("/api/admin/mutate")
async def api_admin_mutate(request: Request):
    body = await request.json()
    user = api_body_user(body)
    require_admin(user)
    kind = str(body.get("kind", ""))
    action = str(body.get("action", ""))
    record = body.get("record") or {}
    if kind == "access_requests":
        request_id = body.get("id")
        with connect() as db:
            access = db.execute("SELECT * FROM access_requests WHERE id=? AND status='Pending'", (request_id,)).fetchone()
            if not access or action not in ("approve", "reject"):
                raise HTTPException(status_code=404, detail="Pending access request not found")
            state = "Approved" if action == "approve" else "Rejected"
            if action == "approve":
                db.execute("INSERT INTO users(user_id,name,department,role,designation,phone,password_hash) VALUES(?,?,?,'Faculty',?,?,?)", (access["faculty_id"], access["name"], access["department"], access["designation"], access["phone"], access["password_hash"]))
            db.execute("UPDATE access_requests SET status=?,reviewed_by=?,reviewed_at=? WHERE id=?", (state, user["user_id"], now_iso(), request_id))
        return {"ok": True, "message": f"Faculty access {state.lower()}."}

    supported = {"teams", "categories", "subcategories", "routing_rules", "sla_settings", "locations", "users"}
    if kind not in supported or action not in ("create", "update", "delete"):
        raise HTTPException(status_code=400, detail="Unsupported admin resource or action")

    with connect() as db:
        if kind == "users":
            user_id = str(body.get("id") or record.get("userId") or record.get("user_id") or "").strip().upper()
            if not user_id:
                raise HTTPException(status_code=400, detail="User ID is required")
            if action == "delete":
                db.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
                return {"ok": True}
            values = {
                "name": str(record.get("name", "")).strip(),
                "department": str(record.get("department", "")).strip(),
                "role": str(record.get("role", "Faculty")),
                "team_name": record.get("teamName", record.get("team_name")),
                "designation": str(record.get("designation", "Support Staff")),
                "phone": str(record.get("phone", "")),
                "active": int(record.get("active", True) is not False),
            }
            if action == "create":
                password = str(record.get("password", ""))
                if not values["name"] or not values["department"] or values["role"] not in ("Faculty", "Team Member", "Administrator") or len(password) < 6:
                    raise HTTPException(status_code=400, detail="User details and a password of at least 6 characters are required")
                db.execute("INSERT INTO users(user_id,name,department,role,team_name,designation,phone,password_hash,active) VALUES(?,?,?,?,?,?,?,?,?)", (user_id, values["name"], values["department"], values["role"], values["team_name"], values["designation"], values["phone"], password_hash(password), values["active"]))
            else:
                updates = {key: value for key, value in values.items() if key in record or key in ("active",)}
                password = str(record.get("password", ""))
                if password:
                    if len(password) < 6:
                        raise HTTPException(status_code=400, detail="Password must contain at least 6 characters")
                    updates["password_hash"] = password_hash(password)
                if updates:
                    assignment = ",".join(f"{key}=?" for key in updates)
                    db.execute(f"UPDATE users SET {assignment} WHERE user_id=?", (*updates.values(), user_id))
            return {"ok": True}

        if kind == "routing_rules":
            old_id = str(body.get("id", ""))
            old_category, _, old_subcategory = old_id.partition(":")
            category = str(record.get("category", old_category)).strip()
            subcategory = str(record.get("subcategory", old_subcategory)).strip()
            team_name = str(record.get("teamName", record.get("team_name", ""))).strip()
            if action == "delete":
                db.execute("UPDATE routing_rules SET active=0 WHERE category=? AND subcategory=?", (old_category, old_subcategory))
                return {"ok": True}
            if not category or not subcategory or not db.execute("SELECT 1 FROM teams WHERE name=? AND active=1", (team_name,)).fetchone():
                raise HTTPException(status_code=400, detail="Choose a category, subcategory, and active support team")
            duplicate = db.execute("SELECT 1 FROM routing_rules WHERE category=? AND subcategory=? AND active=1 AND NOT (category=? AND subcategory=?)", (category, subcategory, old_category, old_subcategory)).fetchone()
            if duplicate:
                raise HTTPException(status_code=409, detail="An active routing rule already exists for this category and subcategory")
            if action == "create":
                db.execute("INSERT INTO routing_rules(category,subcategory,team_name,active) VALUES(?,?,?,?)", (category, subcategory, team_name, int(record.get("active", True) is not False)))
            else:
                db.execute("DELETE FROM routing_rules WHERE category=? AND subcategory=?", (old_category, old_subcategory))
                db.execute("INSERT INTO routing_rules(category,subcategory,team_name,active) VALUES(?,?,?,?)", (category, subcategory, team_name, int(record.get("active", True) is not False)))
            db.execute("INSERT OR IGNORE INTO subcategories(category,name) VALUES(?,?)", (category, subcategory))
            return {"ok": True}

        if kind == "sla_settings":
            priority = str(record.get("priority", body.get("id", "")))
            response = int(record.get("responseMinutes", record.get("response_minutes", 0)))
            resolution = int(record.get("resolutionMinutes", record.get("resolution_minutes", 0)))
            if priority not in PRIORITIES or response < 1 or resolution < 1:
                raise HTTPException(status_code=400, detail="Choose a priority and positive SLA durations")
            if action == "delete":
                db.execute("UPDATE sla_settings SET active=0 WHERE priority=?", (priority,))
            else:
                db.execute("INSERT INTO sla_settings(priority,response_minutes,resolution_minutes,active) VALUES(?,?,?,?) ON CONFLICT(priority) DO UPDATE SET response_minutes=excluded.response_minutes,resolution_minutes=excluded.resolution_minutes,active=excluded.active", (priority, response, resolution, int(record.get("active", True) is not False)))
            return {"ok": True}

        table = {"teams": "teams", "categories": "categories", "locations": "locations", "subcategories": "subcategories"}[kind]
        name = str(record.get("name", "")).strip()
        old_id = str(body.get("id", ""))
        if kind == "subcategories":
            category = str(record.get("category", "")).strip()
            old_category, _, old_name = old_id.partition(":")
            if action == "delete":
                db.execute("UPDATE subcategories SET active=0 WHERE category=? AND name=?", (old_category, old_name))
            elif not category or not name:
                raise HTTPException(status_code=400, detail="Category and subcategory name are required")
            elif action == "create":
                db.execute("INSERT INTO subcategories(category,name,active) VALUES(?,?,?)", (category, name, int(record.get("active", True) is not False)))
            else:
                db.execute("UPDATE subcategories SET category=?,name=?,active=? WHERE category=? AND name=?", (category, name, int(record.get("active", True) is not False), old_category, old_name))
            return {"ok": True}
        if action == "delete":
            db.execute(f"UPDATE {table} SET active=0 WHERE name=?", (old_id,))
        elif not name:
            raise HTTPException(status_code=400, detail="Resource name is required")
        elif action == "create":
            db.execute(f"INSERT INTO {table}(name,active) VALUES(?,?)", (name, int(record.get("active", True) is not False)))
        else:
            db.execute(f"UPDATE {table} SET name=?,active=? WHERE name=?", (name, int(record.get("active", True) is not False), old_id))
    return {"ok": True}


@app.post("/api/reports")
async def api_reports(request: Request):
    user = api_body_user(await request.json())
    if user["role"] not in ("Administrator", "Team Member"):
        raise HTTPException(status_code=403, detail="Reports access required")
    tickets = ticket_rows(user)
    def count_by(field: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ticket in tickets:
            counts[ticket[field]] = counts.get(ticket[field], 0) + 1
        return counts
    return {"total": len(tickets), "byStatus": count_by("status"), "byPriority": count_by("priority"), "byCategory": count_by("category"), "byTeam": count_by("team_name"), "byDepartment": count_by("department"), "breached": sum(ticket["sla_status"] == "Breached" for ticket in tickets), "tickets": [api_ticket(ticket) for ticket in tickets]}


@app.post("/api/cron/sla-monitor")
def sla_monitor(authorization: str = Header(default="")):
    secret = os.getenv("SLA_CRON_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="SLA monitor is not configured")
    if not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    updated = 0
    with connect() as db:
        tickets = db.execute("SELECT * FROM tickets WHERE status!='Closed'").fetchall()
        for ticket in tickets:
            if ticket["sla_alerted"] or sla_status(ticket) != "Breached":
                continue
            status = ticket["status"] if ticket["status"] == "Resolved" else "Escalated"
            db.execute("UPDATE tickets SET sla_alerted=1,status=?,updated_at=? WHERE id=?", (status, now_iso(), ticket["id"]))
            event(db, ticket["id"], "SLA breached", f"Resolution SLA breached for {ticket['token']}", "SYSTEM", "System")
            notify(db, ticket["faculty_id"], "SLA breached", f"{ticket['token']} requires attention")
            recipients = db.execute("SELECT user_id FROM users WHERE active=1 AND (role='Administrator' OR (role='Team Member' AND team_name=?))", (ticket["team_name"],))
            for recipient in recipients:
                notify(db, recipient["user_id"], "SLA breached", f"{ticket['token']} requires attention")
            updated += 1
    return {"ok": True, "updated": updated}


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") or "text/html" not in request.headers.get("accept", ""):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    user = session_user(request)
    return render(request, user, "error", status_code=exc.status_code, message=str(exc.detail))


if os.getenv("VERCEL"):
    app.frontend("/", directory=BASE_DIR / "dist", fallback="index.html")