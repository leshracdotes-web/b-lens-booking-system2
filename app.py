from datetime import datetime, time as dt_time, timedelta
from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ==========================================
# SUPABASE CONFIGURATION
# ==========================================
SUPABASE_URL = "https://khjbygxczrbrdurcgqtt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtoamJ5Z3hjenJicmR1cmNncXR0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY0MDQzMjUsImV4cCI6MjEwMTk4MDMyNX0.EMZvOb4kIJtCKuC5sKdeO7hEp3WCiSDZC6xDARZkzSM"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# DATABASES (POS & Inventory)
# ==========================================
transactions_db = [
    {"id": 1, "date": "2026-07-18", "type": "Incoming", "category": "Self Shoot Package",
     "description": "Samantha Navades - Squad Starter", "amount": 797.00, "account": "Gcash+Cash"},
    {"id": 2, "date": "2026-07-21", "type": "Outgoing", "category": "Expenses", "description": "3 Days FB Boost",
     "amount": 250.00, "account": "Maya"}
]

inventory_db = [
    {"id": 1, "category": "Studio Supplies", "name": "4R Photo Papers", "quantity": 100, "unit": "sheets"},
    {"id": 2, "category": "Studio Supplies", "name": "5R Photo Papers", "quantity": 100, "unit": "sheets"},
    {"id": 3, "category": "Studio Supplies", "name": "A4 Photo Papers", "quantity": 50, "unit": "sheets"},
    {"id": 4, "category": "Studio Supplies", "name": "Ink (Set)", "quantity": 2, "unit": "bottles"},
    {"id": 5, "category": "Studio Supplies", "name": "Long Bond Papers", "quantity": 500, "unit": "sheets"},
    {"id": 6, "category": "Studio Supplies", "name": "Short Bond Papers", "quantity": 500, "unit": "sheets"},
    {"id": 7, "category": "Studio Supplies", "name": "A4 Bond Papers", "quantity": 500, "unit": "sheets"},
    {"id": 8, "category": "Studio Supplies", "name": "Photo Paper Plastics", "quantity": 200, "unit": "pcs"},
    {"id": 9, "category": "Studio Supplies", "name": "Pink Backdrop", "quantity": 1, "unit": "roll"},
    {"id": 10, "category": "Studio Supplies", "name": "Beige Backdrop", "quantity": 1, "unit": "roll"},
    {"id": 11, "category": "Studio Supplies", "name": "White Backdrop", "quantity": 1, "unit": "roll"},
    {"id": 12, "category": "Studio Supplies", "name": "Gray Backdrop", "quantity": 1, "unit": "roll"},
    {"id": 13, "category": "Studio Supplies", "name": "Laminating Film", "quantity": 50, "unit": "pcs"},
    {"id": 14, "category": "Daily Supplies", "name": "Room Spray", "quantity": 2, "unit": "bottles"},
    {"id": 15, "category": "Daily Supplies", "name": "Double A Batteries", "quantity": 4, "unit": "pcs"},
    {"id": 16, "category": "Daily Supplies", "name": "Trashbags", "quantity": 30, "unit": "pcs"},
    {"id": 17, "category": "Daily Supplies", "name": "Nano Tapes", "quantity": 2, "unit": "rolls"},
    {"id": 18, "category": "Daily Supplies", "name": "Masking Tape", "quantity": 3, "unit": "rolls"},
    {"id": 19, "category": "Daily Supplies", "name": "Scotch Tape", "quantity": 3, "unit": "rolls"},
]

SENDER_EMAIL = "b.lens.selfportraitstudio@gmail.com"
SENDER_PASSWORD = "pmanktoycehurtvd"


def send_confirmation_email(customer_email, customer_name, date, schedule, pkg, total, balance):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = customer_email
        msg['Subject'] = "Booking Submitted! - B-Lens Self Portrait Studio"
        body = f"""
        Hi {customer_name},
        Great news! Your reservation at B-Lens Self Portrait Studio has been SUBMITTED successfully.
        Reservation Details:
        - Date: {date}
        - Time Slot: {schedule}
        - Package: {pkg}
        - Grand Total: ₱{total}
        - Remaining Balance: ₱{balance}
        We look forward to seeing you! Please arrive 5-10 minutes before your scheduled time.
        Best regards,
        B-Lens Self Portrait Studio
        """
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, customer_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {str(e)}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get-slots', methods=['GET'])
def get_slots():
    date_str = request.args.get('date')
    default_slots = [
        {"time": "10:00 AM", "time_obj": dt_time(10, 0)},
        {"time": "11:00 AM", "time_obj": dt_time(11, 0)},
        {"time": "01:00 PM", "time_obj": dt_time(13, 0)},
        {"time": "02:00 PM", "time_obj": dt_time(14, 0)},
        {"time": "03:00 PM", "time_obj": dt_time(15, 0)},
        {"time": "04:00 PM", "time_obj": dt_time(16, 0)},
        {"time": "05:00 PM", "time_obj": dt_time(17, 0)},
        {"time": "06:00 PM", "time_obj": dt_time(18, 0)},
        {"time": "07:00 PM", "time_obj": dt_time(19, 0)},
    ]

    try:
        response = supabase.table("bookings").select("*").execute()
        bookings_db = response.data if response.data else []
    except:
        bookings_db = []

    slots = []
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    current_time_with_buffer = dt_time(now.hour + 2, now.minute) if date_str == today_str else None

    booked_times = set()
    blocked_by_buffer = set()

    for b in bookings_db:
        if b.get("date") == date_str and b.get("status") != "Cancelled":
            b_time = b.get("schedule") or b.get("time")
            if b_time:
                booked_times.add(b_time)
                # Logic for buffer time
                extra_t = b.get("extra_time", 0)
                extra_mins = int(''.join(filter(str.isdigit, str(extra_t))) or 0)
                if (15 + extra_mins) > 30:
                    for i, s in enumerate(default_slots):
                        if s["time"] == b_time and i + 1 < len(default_slots):
                            blocked_by_buffer.add(default_slots[i + 1]["time"])
                            break

    # FILTERING LOGIC: Isasama lang sa listahan kung HINDI disabled
    for s in default_slots:
        is_disabled = False
        if date_str == today_str and current_time_with_buffer and s["time_obj"] <= current_time_with_buffer:
            is_disabled = True
        if s["time"] in booked_times or s["time"] in blocked_by_buffer:
            is_disabled = True

        if not is_disabled:
            slots.append({"time": s["time"], "disabled": False, "reason": ""})

    return jsonify({"slots": slots})


@app.route('/save-booking', methods=['POST'])
def save_booking():
    # ... (Iyong existing save_booking logic ay mananatiling pareho)
    return jsonify({"success": True, "message": "Booking successfully saved!"})


if __name__ == '__main__':
    app.run(debug=True)