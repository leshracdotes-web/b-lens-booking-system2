import os
import re
import secrets
import sqlite3
from calendar import monthrange
from datetime import datetime, date, time as dt_time, timedelta
from functools import wraps
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request, session
from supabase import create_client
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config.update(
    MAX_CONTENT_LENGTH=9 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("BLENS_DB_PATH", BASE_DIR / "b_lens.sqlite3"))
BUSINESS_TZ = ZoneInfo(os.environ.get("BUSINESS_TIMEZONE", "Asia/Manila"))
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "booking-proofs")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

DEFAULT_SLOTS = [
    ("10:00 AM", dt_time(10, 0)), ("11:00 AM", dt_time(11, 0)),
    ("01:00 PM", dt_time(13, 0)), ("02:00 PM", dt_time(14, 0)),
    ("03:00 PM", dt_time(15, 0)), ("04:00 PM", dt_time(16, 0)),
    ("05:00 PM", dt_time(17, 0)), ("06:00 PM", dt_time(18, 0)),
    ("07:00 PM", dt_time(19, 0)),
]
ACTIVE_STATUSES = {"Pending", "Confirmed", "Reschedule"}
ALLOWED_STATUSES = ACTIVE_STATUSES | {"Done Shoot/Fully Paid", "Cancelled"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

PET_SIZE_MAX = {"Small": 4, "Medium": 2, "Large": 1}
BACKDROP_COLORS = {"Beige", "White", "Pink", "Gray", "Mottled"}
MOTTLED_ALLOWED_PACKAGES = {"Solo", "Duo"}
PAX_MAX = {"Solo": 9, "Duo": 8, "Squad": 5, "Party": 2}
CHILD_TYPES = {"Infant", "Toddler", "Kid"}
CLOSED_WEEKDAYS = {0}  # Monday = 0

RATES = {
    "Solo": {"Starter": {"reg": 249, "stu": 199, "dur": 10, "baseBd": 1}, "Upgraded": {"reg": 449, "stu": 399, "dur": 20, "baseBd": 1}},
    "Duo": {"Starter": {"reg": 399, "stu": 349, "dur": 15, "baseBd": 1}, "Upgraded": {"reg": 599, "stu": 549, "dur": 25, "baseBd": 1}},
    "Squad": {"Starter": {"reg": 599, "stu": 499, "dur": 20, "baseBd": 2}, "Upgraded": {"reg": 799, "stu": 699, "dur": 30, "baseBd": 2}},
    "Party": {"Starter": {"reg": 899, "stu": 799, "dur": 30, "baseBd": 2}, "Upgraded": {"reg": 1099, "stu": 999, "dur": 40, "baseBd": 3}},
}
TIME_PRICES = {10: 99, 15: 149, 20: 199, 30: 299}
ENHANCED_PRICES = {"1_2": 49, "3_5": 99, "6_10": 199}


def max_booking_date():
    """One calendar month from today (e.g. Aug 29 -> Sep 29)."""
    today = date.today()
    month = today.month + 1
    year = today.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(today.day, monthrange(year, month)[1])
    return date(year, month, day)


def db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_local_db():
    with db_connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('Incoming', 'Outgoing')),
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount >= 0),
                account TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
                unit TEXT NOT NULL
            );
        """)
        if db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0:
            db.executemany("INSERT INTO transactions(date,type,category,description,amount,account) VALUES(?,?,?,?,?,?)", [
                ("2026-07-18", "Incoming", "Self Shoot Package", "Samantha Navades - Squad Starter", 797.00, "Gcash+Cash"),
                ("2026-07-21", "Outgoing", "Expenses", "3 Days FB Boost", 250.00, "Maya"),
            ])
        if db.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
            seed = [
                ("Studio Supplies", "4R Photo Papers", 100, "sheets"), ("Studio Supplies", "5R Photo Papers", 100, "sheets"),
                ("Studio Supplies", "A4 Photo Papers", 50, "sheets"), ("Studio Supplies", "Ink (Set)", 2, "bottles"),
                ("Studio Supplies", "Long Bond Papers", 500, "sheets"), ("Studio Supplies", "Short Bond Papers", 500, "sheets"),
                ("Studio Supplies", "A4 Bond Papers", 500, "sheets"), ("Studio Supplies", "Photo Paper Plastics", 200, "pcs"),
                ("Studio Supplies", "Pink Backdrop", 1, "roll"), ("Studio Supplies", "Beige Backdrop", 1, "roll"),
                ("Studio Supplies", "White Backdrop", 1, "roll"), ("Studio Supplies", "Gray Backdrop", 1, "roll"),
                ("Studio Supplies", "Laminating Film", 50, "pcs"), ("Daily Supplies", "Room Spray", 2, "bottles"),
                ("Daily Supplies", "Double A Batteries", 4, "pcs"), ("Daily Supplies", "Trashbags", 30, "pcs"),
                ("Daily Supplies", "Nano Tapes", 2, "rolls"), ("Daily Supplies", "Masking Tape", 3, "rolls"),
                ("Daily Supplies", "Scotch Tape", 3, "rolls"),
            ]
            db.executemany("INSERT INTO inventory(category,name,quantity,unit) VALUES(?,?,?,?)", seed)


init_local_db()


def require_supabase():
    if supabase is None:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY.")
    return supabase


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return jsonify({"success": False, "message": "Admin login required."}), 401
        return view(*args, **kwargs)
    return wrapped


def form_int(name, default=0, maximum=None):
    raw = request.form.get(name, default)
    try:
        value = int(raw or default)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number.")
    if value < 0 or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside the allowed range.")
    return value


def as_bool(value):
    return str(value).lower() in {"true", "1", "yes", "on"}


def calculate_totals(form, strict=True):
    category = form.get("package", "")
    package_type = form.get("package_type", "")
    if category not in RATES or package_type not in RATES[category]:
        raise ValueError("Please select a valid package.")
    package = RATES[category][package_type]
    student = as_bool(form.get("is_student", False))
    total = package["stu"] if student else package["reg"]
    extra_pax = int(form.get("extra_pax", 0) or 0)
    pet_size = form.get("pet_size", "").strip()
    has_pet = as_bool(form.get("has_pet", False))
    extra_pet = int(form.get("extra_pet", 0) or 0) if has_pet else 0
    has_extra_backdrop = as_bool(form.get("has_additional_backdrop", False))
    additional_backdrop_color = form.get("additional_backdrop_color", "").strip()
    backdrop_decide_later = as_bool(form.get("backdrop_decide_later", False))
    extra_time = int(form.get("extra_time", 0) or 0)
    enhanced = form.get("enhanced_copies", "0")
    enhanced_qty = int(form.get("extra_enhanced_qty", 0) or 0)
    balloon_qty = int(form.get("balloon_qty", 0) or 0)
    preferred_backdrop_list = [c.strip() for c in form.getlist("preferred_backdrop") if c.strip()]
    pax_max = PAX_MAX.get(category, 0)
    if strict:
        if not 0 <= extra_pax <= pax_max:
            raise ValueError(f"{category} packages allow up to {pax_max} extra pax.")
    else:
        extra_pax = max(0, min(extra_pax, pax_max))
    if has_pet:
        if strict:
            if pet_size not in PET_SIZE_MAX:
                raise ValueError("Please select a pet size (Small, Medium, or Large).")
            if not 1 <= extra_pet <= PET_SIZE_MAX[pet_size]:
                raise ValueError(f"{pet_size} breed pets are limited to {PET_SIZE_MAX[pet_size]} per session.")
        else:
            if pet_size not in PET_SIZE_MAX:
                pet_size = "Small"
            extra_pet = max(1, min(extra_pet or 1, PET_SIZE_MAX[pet_size]))
    required_backdrops = package["baseBd"]
    if backdrop_decide_later:
        preferred_backdrop_list = []
    elif strict:
        if len(preferred_backdrop_list) != required_backdrops or len(set(preferred_backdrop_list)) != required_backdrops:
            raise ValueError(f"Please choose exactly {required_backdrops} preferred backdrop color(s).")
        if any(color not in BACKDROP_COLORS for color in preferred_backdrop_list):
            raise ValueError("Please select a valid preferred backdrop color.")
        if "Mottled" in preferred_backdrop_list and category not in MOTTLED_ALLOWED_PACKAGES:
            raise ValueError("Mottled backdrop is only available for Solo and Duo packages.")
    else:
        preferred_backdrop_list = list(dict.fromkeys(c for c in preferred_backdrop_list if c in BACKDROP_COLORS))[:required_backdrops]
        if category not in MOTTLED_ALLOWED_PACKAGES:
            preferred_backdrop_list = [c for c in preferred_backdrop_list if c != "Mottled"]
    extra_backdrop = 0
    if has_extra_backdrop and not backdrop_decide_later:
        if strict:
            if additional_backdrop_color not in BACKDROP_COLORS:
                raise ValueError("Please choose a valid additional backdrop color.")
            if additional_backdrop_color in preferred_backdrop_list:
                raise ValueError("The additional backdrop color must be different from your preferred backdrop colors.")
            if additional_backdrop_color == "Mottled" and category not in MOTTLED_ALLOWED_PACKAGES:
                raise ValueError("Mottled backdrop is only available for Solo and Duo packages.")
        elif additional_backdrop_color == "Mottled" and category not in MOTTLED_ALLOWED_PACKAGES:
            additional_backdrop_color = ""
        extra_backdrop = 1
    if extra_time not in {0, 10, 15, 20, 30}:
        if strict:
            raise ValueError("Please select a valid time extension.")
        extra_time = 0
    total += extra_pax * 99 + extra_pet * 99 + TIME_PRICES.get(extra_time, 0) + extra_backdrop * 99
    session_minutes = package["dur"] + extra_time
    digital_copies = "0"
    if as_bool(form.get("has_digital_copies", False)):
        digital_price = 99 if session_minutes <= 15 else 149 if session_minutes <= 25 else 199
        digital_copies = "10_15" if session_minutes <= 15 else "20_25" if session_minutes <= 25 else "30_40"
        total += digital_price
    if enhanced in ENHANCED_PRICES:
        total += ENHANCED_PRICES[enhanced]
    elif enhanced == "more_10":
        if strict:
            if enhanced_qty < 11 or enhanced_qty > 100:
                raise ValueError("Enhanced photo quantity must be between 11 and 100.")
        else:
            enhanced_qty = max(11, min(enhanced_qty or 11, 100))
        total += enhanced_qty * 25
    elif enhanced != "0":
        if strict:
            raise ValueError("Please select a valid enhanced copy option.")
        enhanced = "0"
    if as_bool(form.get("has_balloons", False)):
        if strict:
            if not 1 <= balloon_qty <= 30:
                raise ValueError("Balloon quantity must be between 1 and 30.")
            balloon_numbers = [n.strip() for n in form.get("balloon_numbers", "").split(",") if n.strip()]
            if not balloon_numbers:
                raise ValueError("Please provide the balloon digit(s) or number(s).")
            if len(balloon_numbers) != balloon_qty:
                raise ValueError(f"Please provide exactly {balloon_qty} number(s) for the balloon quantity, separated by commas.")
        else:
            balloon_qty = max(1, min(balloon_qty or 1, 30))
        total += balloon_qty * 39
    elif balloon_qty != 0:
        balloon_qty = 0
    child_types = []
    total_children = 0
    if as_bool(form.get("has_children", False)):
        child_types = [c.strip() for c in form.getlist("children_types") if c.strip()]
        if strict:
            if not child_types or any(c not in CHILD_TYPES for c in child_types):
                raise ValueError("Please select at least one child age group.")
            total_children = int(form.get("total_children", 0) or 0)
            if not 1 <= total_children <= 20:
                raise ValueError("Please enter a valid total number of children.")
        else:
            child_types = [c for c in child_types if c in CHILD_TYPES]
            total_children = int(form.get("total_children", 0) or 0)
            total_children = max(1, min(total_children or 1, 20)) if child_types else 0
    downpayment = (total + 1) // 2
    return {
        "total": total, "downpayment": downpayment, "balance": total - downpayment, "digital_copies": digital_copies,
        "extra_pax": extra_pax, "has_pet": has_pet, "pet_size": pet_size if has_pet else "", "extra_pet": extra_pet,
        "preferred_backdrop_list": preferred_backdrop_list, "extra_backdrop": extra_backdrop,
        "additional_backdrop_color": additional_backdrop_color if extra_backdrop else "", "extra_time": extra_time,
        "enhanced_copies": enhanced, "extra_enhanced_qty": enhanced_qty, "has_balloons": as_bool(form.get("has_balloons", False)),
        "balloon_qty": balloon_qty, "child_types": child_types, "total_children": total_children,
    }


def parse_booking_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("Please choose a valid booking date.")


def supabase_bookings():
    response = require_supabase().table("bookings").select("*").execute()
    return response.data or []


def get_blocked_dates():
    try:
        response = require_supabase().table("blocked_dates").select("*").execute()
        result = {}
        for row in (response.data or []):
            key = str(row.get("date", ""))[:10]
            times = [t.strip() for t in str(row.get("times") or "").split(",") if t.strip()]
            result[key] = {"reason": row.get("reason", ""), "times": times}
        return result
    except Exception:
        return {}


def slot_rows(selected_date, bypass_cutoff=False, manually_blocked=None, block_reason=""):
    manually_blocked = manually_blocked or set()
    bookings = supabase_bookings()
    booked = set()
    buffer_blocked = set()
    for booking in bookings:
        if str(booking.get("date", ""))[:10] != selected_date.isoformat() or booking.get("status") in ("Cancelled", "Reschedule"):
            continue
        booked_time = booking.get("schedule") or booking.get("time")
        if booked_time:
            booked.add(booked_time)
            try:
                extra = int(booking.get("extra_time", 0) or 0)
            except (TypeError, ValueError):
                extra = 0
            if 15 + extra > 30:
                for index, (label, _) in enumerate(DEFAULT_SLOTS):
                    if label == booked_time and index + 1 < len(DEFAULT_SLOTS):
                        buffer_blocked.add(DEFAULT_SLOTS[index + 1][0])
    now = datetime.now(BUSINESS_TZ)
    rows = []
    for label, slot_time in DEFAULT_SLOTS:
        if label in manually_blocked:
            rows.append({"time": label, "disabled": True, "reason": block_reason or "Blocked by the studio"})
            continue
        disabled = label in booked or label in buffer_blocked
        reason = "Already booked" if label in booked else "Buffer after a long session" if label in buffer_blocked else ""
        if selected_date == now.date() and not bypass_cutoff and datetime.combine(selected_date, slot_time, BUSINESS_TZ) <= now + timedelta(hours=2):
            disabled, reason = True, "Too close to start time"
        rows.append({"time": label, "disabled": disabled, "reason": reason})
    return rows


def record_transaction(values):
    with db_connection() as db:
        db.execute("INSERT INTO transactions(date,type,category,description,amount,account) VALUES(?,?,?,?,?,?)", values)


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@app.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    return jsonify({"success": False, "message": "Uploaded file is too large. Maximum is 8 MB."}), 413


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin_dashboard():
    return render_template("admin.html")


@app.get("/api/admin/session")
def admin_session():
    if not ADMIN_PASSWORD:
        return jsonify({"authenticated": False, "message": "ADMIN_PASSWORD is not configured."}), 503
    if not session.get("admin_authenticated"):
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True})


@app.post("/api/admin/login")
def admin_login():
    if not ADMIN_PASSWORD:
        return jsonify({"success": False, "message": "Set ADMIN_PASSWORD before using the admin dashboard."}), 503
    data = request.get_json(silent=True) or {}
    if not secrets.compare_digest(str(data.get("password", "")), ADMIN_PASSWORD):
        return jsonify({"success": False, "message": "Incorrect admin password."}), 401
    session.clear()
    session["admin_authenticated"] = True
    return jsonify({"success": True})


@app.post("/api/admin/logout")
def admin_logout():
    session.clear()
    return jsonify({"success": True})


@app.get("/get-slots")
def get_slots():
    try:
        selected_date = parse_booking_date(request.args.get("date"))
        if selected_date < date.today():
            return jsonify({"slots": []})
        if selected_date > max_booking_date():
            return jsonify({"slots": [], "message": "Bookings are only open up to one month ahead."}), 400
        if selected_date.weekday() in CLOSED_WEEKDAYS:
            return jsonify({"slots": [], "message": "The studio is closed on Mondays."}), 400
        blocked = get_blocked_dates()
        info = blocked.get(selected_date.isoformat())
        if info and not info["times"]:
            reason = info["reason"]
            return jsonify({"slots": [], "message": f"The studio is closed on this date{f': {reason}' if reason else '.'}"}), 400
        manually_blocked = set(info["times"]) if info else set()
        return jsonify({"slots": slot_rows(selected_date, manually_blocked=manually_blocked, block_reason=info["reason"] if info else "")})
    except Exception as error:
        return jsonify({"slots": [], "message": str(error)}), 500


def create_booking_record(bypass_cutoff=False, require_proof=True, default_status="Pending", source="Website"):
    uploaded_path = None
    required = {"customer_name": "full name", "contact_no": "contact number", "email": "email", "social_media": "social media", "date": "date", "schedule": "time slot"}
    missing = [label for field, label in required.items() if not request.form.get(field, "").strip()]
    if missing:
        return {"success": False, "message": f"Please provide: {', '.join(missing)}."}, 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", request.form["email"].strip()):
        return {"success": False, "message": "Please provide a valid email address."}, 400
    if source == "Website" and not as_bool(request.form.get("agreed_to_terms")):
        return {"success": False, "message": "Please agree to the Customer Agreement and Data Privacy Consent to continue."}, 400
    booking_date = parse_booking_date(request.form["date"])
    if booking_date < date.today():
        return {"success": False, "message": "Booking date cannot be in the past."}, 400
    if booking_date > max_booking_date():
        return {"success": False, "message": "Bookings are only open up to one month ahead."}, 400
    if booking_date.weekday() in CLOSED_WEEKDAYS:
        return {"success": False, "message": "The studio is closed on Mondays. Please pick another date."}, 400
    blocked = get_blocked_dates()
    booking_date_info = blocked.get(booking_date.isoformat())
    if booking_date_info and not booking_date_info["times"]:
        reason = booking_date_info["reason"]
        return {"success": False, "message": f"The studio is closed on this date{f': {reason}' if reason else '.'}"}, 400
    manually_blocked = set(booking_date_info["times"]) if booking_date_info else set()
    totals = calculate_totals(request.form)
    selected_slot = request.form["schedule"]
    allowed = {label for label, _ in DEFAULT_SLOTS}
    if selected_slot not in allowed:
        return {"success": False, "message": "Please select a valid time slot."}, 400
    current_slots = slot_rows(booking_date, bypass_cutoff=bypass_cutoff, manually_blocked=manually_blocked, block_reason=booking_date_info["reason"] if booking_date_info else "")
    slot = next(row for row in current_slots if row["time"] == selected_slot)
    if slot["disabled"]:
        return {"success": False, "message": f"That slot is no longer available: {slot['reason']}."}, 409
    try:
        screenshot_url = ""
        payment_file = request.files.get("payment_screenshot")
        if payment_file and payment_file.filename:
            if payment_file.content_type not in ALLOWED_IMAGE_TYPES:
                return {"success": False, "message": "Payment proof must be a PNG, JPG, or WEBP image."}, 400
            file_bytes = payment_file.read()
            if not file_bytes or len(file_bytes) > 8 * 1024 * 1024:
                return {"success": False, "message": "Payment screenshot must be 8 MB or smaller."}, 400
            extension = Path(secure_filename(payment_file.filename)).suffix.lower() or ".jpg"
            uploaded_path = f"proofs/{uuid4().hex}{extension}"
            require_supabase().storage.from_(SUPABASE_BUCKET).upload(file=file_bytes, path=uploaded_path, file_options={"content-type": payment_file.content_type})
            screenshot_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{uploaded_path}"
        elif require_proof:
            return {"success": False, "message": "Payment screenshot is required."}, 400
        actual_amount_sent = form_int("actual_amount_sent", default=0, maximum=1_000_000) or totals["downpayment"]
        backdrop_decide_later = as_bool(request.form.get("backdrop_decide_later"))
        payment_mode = request.form.get("payment_mode", "").strip() or ("Cash" if source == "Walk-in" else "Online")
        new_booking = {
            "date": booking_date.isoformat(), "schedule": selected_slot,
            "name": request.form["customer_name"].strip(), "customer_name": request.form["customer_name"].strip(),
            "contact_no": request.form["contact_no"].strip(), "email": request.form["email"].strip(), "social_media": request.form["social_media"].strip(),
            "package": request.form.get("package"), "package_type": request.form.get("package_type"),
            "is_student": str(as_bool(request.form.get("is_student"))).lower(),
            "extra_pax": form_int("extra_pax", maximum=PAX_MAX.get(request.form.get("package", ""), 9)),
            "has_pet": str(as_bool(request.form.get("has_pet"))).lower(),
            "extra_pet": form_int("extra_pet", maximum=4) if as_bool(request.form.get("has_pet")) else 0,
            "pet_size": request.form.get("pet_size", "").strip() if as_bool(request.form.get("has_pet")) else "",
            "preferred_backdrop": "Decide on the day of session" if backdrop_decide_later else ",".join(request.form.getlist("preferred_backdrop")),
            "extra_time": form_int("extra_time"), "has_digital_copies": str(as_bool(request.form.get("has_digital_copies"))).lower(),
            "digital_copies": totals["digital_copies"], "enhanced_copies": request.form.get("enhanced_copies", "0"),
            "extra_enhanced_qty": form_int("extra_enhanced_qty", 11 if request.form.get("enhanced_copies") == "more_10" else 0, 100),
            "extra_backdrop": 1 if (as_bool(request.form.get("has_additional_backdrop")) and not backdrop_decide_later) else 0,
            "additional_backdrop_color": request.form.get("additional_backdrop_color", "").strip() if (as_bool(request.form.get("has_additional_backdrop")) and not backdrop_decide_later) else "",
            "notes": request.form.get("backdrop_order", "").strip(),
            "has_children": str(as_bool(request.form.get("has_children"))).lower(),
            "children_types": ",".join(request.form.getlist("children_types")) if as_bool(request.form.get("has_children")) else "",
            "total_children": form_int("total_children", maximum=20) if as_bool(request.form.get("has_children")) else 0,
            "has_balloons": str(as_bool(request.form.get("has_balloons"))).lower(),
            "balloon_qty": form_int("balloon_qty"), "balloon_numbers": request.form.get("balloon_numbers", "").strip(),
            "grand_total": totals["total"], "downpayment": totals["downpayment"], "balance": totals["balance"],
            "actual_amount_sent": actual_amount_sent, "source": source, "payment_mode": payment_mode,
            "agreed_to_terms": str(as_bool(request.form.get("agreed_to_terms"))).lower(),
            "payment_screenshot": screenshot_url, "status": default_status,
        }
        inserted = require_supabase().table("bookings").insert(new_booking).execute()
        created = (inserted.data or [new_booking])[0]
        record_transaction((booking_date.isoformat(), "Incoming", "Booking Downpayment", f"{new_booking['customer_name']} - {new_booking['package']} ({new_booking['package_type']})", actual_amount_sent, payment_mode))
        return {"success": True, "message": "Booking submitted successfully.", "booking_id": created.get("id")}, 200
    except ValueError as error:
        return {"success": False, "message": str(error)}, 400
    except Exception:
        if uploaded_path and supabase is not None:
            try:
                supabase.storage.from_(SUPABASE_BUCKET).remove([uploaded_path])
            except Exception:
                pass
        app.logger.exception("Booking save failed")
        return {"success": False, "message": "We could not save the booking right now. Please try again."}, 500


@app.post("/save-booking")
def save_booking():
    try:
        require_supabase()
        result, status_code = create_booking_record(bypass_cutoff=False, require_proof=True, default_status="Pending", source="Website")
        return jsonify(result), status_code
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except Exception:
        app.logger.exception("Booking save failed")
        return jsonify({"success": False, "message": "We could not save the booking right now. Please try again."}), 500


@app.get("/api/admin/walkin-slots")
@admin_required
def api_admin_walkin_slots():
    try:
        selected_date = parse_booking_date(request.args.get("date"))
        if selected_date.weekday() in CLOSED_WEEKDAYS:
            return jsonify({"slots": [], "message": "The studio is closed on Mondays."}), 400
        blocked = get_blocked_dates()
        info = blocked.get(selected_date.isoformat())
        if info and not info["times"]:
            reason = info["reason"]
            return jsonify({"slots": [], "message": f"This date is blocked{f': {reason}' if reason else '.'}"}), 400
        manually_blocked = set(info["times"]) if info else set()
        return jsonify({"slots": slot_rows(selected_date, bypass_cutoff=True, manually_blocked=manually_blocked, block_reason=info["reason"] if info else "")})
    except Exception as error:
        return jsonify({"slots": [], "message": str(error)}), 500


@app.post("/api/admin/walkin-booking")
@admin_required
def api_admin_walkin_booking():
    try:
        require_supabase()
        result, status_code = create_booking_record(bypass_cutoff=True, require_proof=False, default_status="Pending", source="Walk-in")
        return jsonify(result), status_code
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except Exception:
        app.logger.exception("Walk-in booking save failed")
        return jsonify({"success": False, "message": "We could not save the walk-in booking right now. Please try again."}), 500


@app.get("/api/admin/blocked-dates")
@admin_required
def api_admin_blocked_dates():
    try:
        response = require_supabase().table("blocked_dates").select("*").order("date").execute()
        return jsonify({"blocked_dates": response.data or []})
    except Exception:
        app.logger.exception("Blocked dates fetch failed")
        return jsonify({"blocked_dates": [], "message": "Unable to load blocked dates."}), 503


@app.post("/api/admin/blocked-dates")
@admin_required
def api_admin_add_blocked_date():
    data = request.get_json(silent=True) or {}
    try:
        blocked_date = parse_booking_date(data.get("date"))
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    reason = str(data.get("reason", "")).strip()
    allowed_slots = {label for label, _ in DEFAULT_SLOTS}
    raw_times = data.get("times") or []
    if not isinstance(raw_times, list):
        return jsonify({"success": False, "message": "Times must be a list."}), 400
    times = [t for t in raw_times if t in allowed_slots]
    if raw_times and not times:
        return jsonify({"success": False, "message": "Please select valid time slots, or leave empty to block the whole day."}), 400
    times_value = ",".join(times)
    try:
        client = require_supabase()
        # Manual check-then-write instead of upsert(on_conflict="date"): upsert requires a
        # unique/exclusion constraint on the "date" column in Supabase, and fails silently
        # from the UI's perspective if that constraint isn't set up on the table.
        existing = client.table("blocked_dates").select("date").eq("date", blocked_date.isoformat()).execute()
        if existing.data:
            client.table("blocked_dates").update({"reason": reason, "times": times_value}).eq("date", blocked_date.isoformat()).execute()
        else:
            client.table("blocked_dates").insert({"date": blocked_date.isoformat(), "reason": reason, "times": times_value}).execute()
        return jsonify({"success": True})
    except Exception:
        app.logger.exception("Blocking date failed")
        return jsonify({"success": False, "message": "Unable to block that date. Make sure the 'blocked_dates' table exists in Supabase with 'date', 'reason', and 'times' columns."}), 500


@app.post("/api/admin/blocked-dates/delete")
@admin_required
def api_admin_delete_blocked_date():
    data = request.get_json(silent=True) or {}
    target_date = str(data.get("date", "")).strip()
    if not target_date:
        return jsonify({"success": False, "message": "Date is required."}), 400
    try:
        require_supabase().table("blocked_dates").delete().eq("date", target_date).execute()
        return jsonify({"success": True})
    except Exception:
        app.logger.exception("Unblocking date failed")
        return jsonify({"success": False, "message": "Unable to unblock that date."}), 500


@app.get("/api/admin/bookings")
@admin_required
def api_admin_bookings():
    try:
        bookings = supabase_bookings()
        bookings.sort(key=lambda booking: (str(booking.get("date", "")), str(booking.get("schedule", ""))))
        return jsonify({"bookings": bookings})
    except Exception:
        app.logger.exception("Booking fetch failed")
        return jsonify({"bookings": [], "message": "Unable to load bookings."}), 503


@app.post("/api/admin/update-status")
@admin_required
def api_admin_update_status():
    data = request.get_json(silent=True) or {}
    booking_id, new_status = data.get("id"), data.get("status")
    if not booking_id or new_status not in ALLOWED_STATUSES:
        return jsonify({"success": False, "message": "Invalid booking status update."}), 400
    try:
        existing = next((booking for booking in supabase_bookings() if str(booking.get("id")) == str(booking_id)), None)
        if not existing:
            return jsonify({"success": False, "message": "Booking not found."}), 404
        updates = {"status": new_status}
        if new_status == "Reschedule" and data.get("new_date") and data.get("new_time"):
            try:
                new_date = parse_booking_date(data.get("new_date"))
            except ValueError as error:
                return jsonify({"success": False, "message": str(error)}), 400
            allowed = {label for label, _ in DEFAULT_SLOTS}
            new_time = data.get("new_time")
            if new_time not in allowed:
                return jsonify({"success": False, "message": "Please select a valid time slot."}), 400
            blocked = get_blocked_dates()
            info = blocked.get(new_date.isoformat())
            if info and not info["times"]:
                reason = info["reason"]
                return jsonify({"success": False, "message": f"That date is closed{f': {reason}' if reason else '.'}"}), 400
            manually_blocked = set(info["times"]) if info else set()
            current_slots = slot_rows(new_date, bypass_cutoff=True, manually_blocked=manually_blocked, block_reason=info["reason"] if info else "")
            is_same_slot = str(existing.get("date", ""))[:10] == new_date.isoformat() and existing.get("schedule") == new_time
            slot = next((row for row in current_slots if row["time"] == new_time), None)
            if slot and slot["disabled"] and not is_same_slot:
                return jsonify({"success": False, "message": f"That slot is not available: {slot['reason']}."}), 409
            updates["date"] = new_date.isoformat()
            updates["schedule"] = new_time
        require_supabase().table("bookings").update(updates).eq("id", booking_id).execute()
        return jsonify({"success": True})
    except Exception:
        app.logger.exception("Status update failed")
        return jsonify({"success": False, "message": "Unable to update booking status."}), 500


@app.post("/api/admin/update-booking")
@admin_required
def api_admin_update_booking():
    booking_id = request.form.get("id")
    if not booking_id:
        return jsonify({"success": False, "message": "Booking id is required."}), 400
    try:
        existing = next((booking for booking in supabase_bookings() if str(booking.get("id")) == str(booking_id)), None)
        if not existing:
            return jsonify({"success": False, "message": "Booking not found."}), 404
        totals = calculate_totals(request.form, strict=False)
        backdrop_decide_later = as_bool(request.form.get("backdrop_decide_later"))
        actual_amount_sent = form_int("actual_amount_sent", default=0, maximum=1_000_000) or totals["downpayment"]
        updates = {
            "package": request.form.get("package"), "package_type": request.form.get("package_type"),
            "is_student": str(as_bool(request.form.get("is_student"))).lower(),
            "extra_pax": totals["extra_pax"],
            "has_pet": str(totals["has_pet"]).lower(),
            "extra_pet": totals["extra_pet"] if totals["has_pet"] else 0,
            "pet_size": totals["pet_size"],
            "preferred_backdrop": "Decide on the day of session" if backdrop_decide_later else ",".join(totals["preferred_backdrop_list"]),
            "extra_time": totals["extra_time"], "has_digital_copies": str(as_bool(request.form.get("has_digital_copies"))).lower(),
            "digital_copies": totals["digital_copies"], "enhanced_copies": totals["enhanced_copies"],
            "extra_enhanced_qty": totals["extra_enhanced_qty"] if totals["enhanced_copies"] == "more_10" else 0,
            "extra_backdrop": totals["extra_backdrop"],
            "additional_backdrop_color": totals["additional_backdrop_color"],
            "has_children": str(bool(totals["child_types"])).lower(),
            "children_types": ",".join(totals["child_types"]),
            "total_children": totals["total_children"],
            "has_balloons": str(totals["has_balloons"]).lower(),
            "balloon_qty": totals["balloon_qty"], "balloon_numbers": request.form.get("balloon_numbers", "").strip() if totals["has_balloons"] else "",
            "grand_total": totals["total"], "downpayment": totals["downpayment"], "balance": totals["balance"],
            "actual_amount_sent": actual_amount_sent,
        }
        require_supabase().table("bookings").update(updates).eq("id", booking_id).execute()
        return jsonify({"success": True, "message": "Booking updated."})
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except Exception:
        app.logger.exception("Booking update failed")
        return jsonify({"success": False, "message": "Unable to update this booking."}), 500


@app.post("/api/admin/delete-booking")
@admin_required
def api_admin_delete_booking():
    data = request.get_json(silent=True) or {}
    if not data.get("id"):
        return jsonify({"success": False, "message": "Booking id is required."}), 400
    try:
        require_supabase().table("bookings").delete().eq("id", data["id"]).execute()
        return jsonify({"success": True})
    except Exception:
        app.logger.exception("Booking delete failed")
        return jsonify({"success": False, "message": "Unable to delete booking."}), 500


@app.get("/api/admin/transactions")
@admin_required
def api_admin_transactions_get():
    with db_connection() as db:
        rows = db.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC").fetchall()
    return jsonify({"transactions": [dict(row) for row in rows]})


@app.post("/api/admin/transactions")
@admin_required
def api_admin_transactions_create():
    data = request.get_json(silent=True) or {}
    if data.get("type") not in {"Incoming", "Outgoing"} or not data.get("date") or not data.get("category", "").strip() or not data.get("description", "").strip():
        return jsonify({"success": False, "message": "Complete the transaction fields."}), 400
    try:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Amount must be greater than zero."}), 400
    with db_connection() as db:
        cursor = db.execute("INSERT INTO transactions(date,type,category,description,amount,account) VALUES(?,?,?,?,?,?)", (data["date"], data["type"], data["category"].strip(), data["description"].strip(), amount, data.get("account", "Cash")))
        item = db.execute("SELECT * FROM transactions WHERE id=?", (cursor.lastrowid,)).fetchone()
    return jsonify({"success": True, "transaction": dict(item)})


@app.post("/api/admin/transactions/delete")
@admin_required
def api_admin_transactions_delete():
    data = request.get_json(silent=True) or {}
    with db_connection() as db:
        db.execute("DELETE FROM transactions WHERE id=?", (data.get("id"),))
    return jsonify({"success": True})


@app.get("/api/admin/inventory")
@admin_required
def api_admin_inventory_get():
    with db_connection() as db:
        rows = db.execute("SELECT * FROM inventory ORDER BY category, name").fetchall()
    return jsonify({"inventory": [dict(row) for row in rows]})


@app.post("/api/admin/inventory")
@admin_required
def api_admin_inventory_create():
    data = request.get_json(silent=True) or {}
    try:
        quantity = int(data.get("quantity", 0))
        if quantity < 0 or not data.get("name", "").strip() or not data.get("unit", "").strip() or data.get("category") not in {"Studio Supplies", "Daily Supplies"}:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Complete the inventory fields."}), 400
    with db_connection() as db:
        cursor = db.execute("INSERT INTO inventory(category,name,quantity,unit) VALUES(?,?,?,?)", (data["category"], data["name"].strip(), quantity, data["unit"].strip()))
        item = db.execute("SELECT * FROM inventory WHERE id=?", (cursor.lastrowid,)).fetchone()
    return jsonify({"success": True, "item": dict(item)})


@app.post("/api/admin/inventory/update")
@admin_required
def api_admin_inventory_update():
    data = request.get_json(silent=True) or {}
    try:
        item_id, change = int(data.get("id")), int(data.get("quantity_change"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid stock update."}), 400
    with db_connection() as db:
        item = db.execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
        if not item:
            return jsonify({"success": False, "message": "Item not found."}), 404
        new_quantity = max(0, item["quantity"] + change)
        db.execute("UPDATE inventory SET quantity=? WHERE id=?", (new_quantity, item_id))
        updated = db.execute("SELECT * FROM inventory WHERE id=?", (item_id,)).fetchone()
    return jsonify({"success": True, "item": dict(updated)})


@app.post("/api/admin/inventory/delete")
@admin_required
def api_admin_inventory_delete():
    data = request.get_json(silent=True) or {}
    with db_connection() as db:
        db.execute("DELETE FROM inventory WHERE id=?", (data.get("id"),))
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
