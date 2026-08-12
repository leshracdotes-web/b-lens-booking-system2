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

# GMAIL CONFIGURATION
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
        print("Confirmation email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')


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
    except Exception as e:
        print("Error fetching bookings from Supabase:", e)
        bookings_db = []

    slots = []
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')

    current_time_with_buffer = None
    if date_str == today_str:
        buffered_hour = min(now.hour + 2, 23)
        current_time_with_buffer = dt_time(buffered_hour, now.minute)

    booked_times = set()
    blocked_by_buffer = set()

    for b in bookings_db:
        if b.get("date") == date_str and b.get("status") != "Cancelled":
            b_time = b.get("schedule") or b.get("time")
            if b_time:
                booked_times.add(b_time)

                extra_t = b.get("extra_time", 0)
                try:
                    if isinstance(extra_t, str):
                        extra_mins = int(''.join(filter(str.isdigit, extra_t)) or 0)
                    else:
                        extra_mins = int(extra_t or 0)
                except:
                    extra_mins = 0

                total_duration = 15 + extra_mins

                if total_duration > 30:
                    for i, s in enumerate(default_slots):
                        if s["time"] == b_time and i + 1 < len(default_slots):
                            current_slot_obj = s["time_obj"]
                            next_slot_obj = default_slots[i + 1]["time_obj"]

                            diff_minutes = (next_slot_obj.hour * 60 + next_slot_obj.minute) - (
                                        current_slot_obj.hour * 60 + current_slot_obj.minute)
                            if diff_minutes <= 90:
                                blocked_by_buffer.add(default_slots[i + 1]["time"])
                            break

    for s in default_slots:
        is_disabled = False
        reason = ""

        if date_str == today_str and current_time_with_buffer:
            if s["time_obj"] <= current_time_with_buffer:
                is_disabled = True
                reason = " (Too late)"

        if s["time"] in booked_times:
            is_disabled = True
            reason = " (Already Booked)"
        elif s["time"] in blocked_by_buffer:
            is_disabled = True
            reason = " (Buffer Time)"

        slots.append({
            "time": s["time"],
            "disabled": is_disabled,
            "reason": reason
        })

    return jsonify({"slots": slots})


@app.route('/save-booking', methods=['POST'])
def save_booking():
    try:
        pkg_type = request.form.get("package_type", "Starter")
        extra_backdrop = int(request.form.get("extra_backdrop", 0) or 0)

        max_allowed_extra = 1 if pkg_type == 'Starter' else 2
        if extra_backdrop > max_allowed_extra:
            return jsonify({
                "success": False,
                "message": f"Maximum extra backdrops exceeded! For {pkg_type} packages, you can only add up to {max_allowed_extra} extra backdrop(s)."
            }), 400

        payment_file = request.files.get('payment_screenshot')
        screenshot_url = ""

        if payment_file and payment_file.filename != '':
            filename = secure_filename(payment_file.filename)
            file_path = f"proofs/{int(time.time())}_{filename}"

            try:
                supabase.storage.from_("booking-proofs").upload(
                    file=payment_file.read(),
                    path=file_path,
                    file_options={"content-type": payment_file.content_type}
                )

                # Manu-manong binuo ang tamang URL para maiwasan ang 404 error sa Admin Dashboard
                screenshot_url = f"{SUPABASE_URL}/storage/v1/object/public/booking-proofs/{file_path}"

            except Exception as storage_err:
                return jsonify({"success": False, "message": f"Storage Error: {str(storage_err)}"}), 500
        else:
            return jsonify({
                "success": False,
                "message": "Please upload your payment screenshot for the downpayment!"
            }), 400

        downpayment_amount = float(request.form.get("downpayment", 0) or 0)
        booking_date = request.form.get("date")
        customer_name = request.form.get("customer_name")
        pkg_name = request.form.get("package")

        new_booking = {
            "date": booking_date,
            "schedule": request.form.get("schedule"),
            "name": customer_name,
            "customer_name": customer_name,
            "contact_no": request.form.get("contact_no"),
            "email": request.form.get("email"),
            "social_media": request.form.get("social_media"),
            "package": pkg_name,
            "package_type": pkg_type,
            "is_student": request.form.get("is_student"),
            "extra_pax": request.form.get("extra_pax"),
            "extra_pet": request.form.get("extra_pet"),
            "extra_time": request.form.get("extra_time"),
            "has_digital_copies": request.form.get("has_digital_copies"),
            "digital_copies": request.form.get("digital_copies"),
            "enhanced_copies": request.form.get("enhanced_copies"),
            "extra_enhanced_qty": request.form.get("extra_enhanced_qty"),
            "extra_backdrop": extra_backdrop,
            "backdrop_order": request.form.get("backdrop_order"),
            "has_infant": request.form.get("has_infant"),
            "infant_details": request.form.get("infant_details"),
            "has_balloons": request.form.get("has_balloons"),
            "balloon_qty": request.form.get("balloon_qty"),
            "balloon_numbers": request.form.get("balloon_numbers"),
            "grand_total": request.form.get("grand_total"),
            "downpayment": downpayment_amount,
            "balance": request.form.get("balance"),
            "payment_screenshot": screenshot_url,
            "status": "Pending"
        }

        supabase.table("bookings").insert(new_booking).execute()

        transactions_db.append({
            "id": len(transactions_db) + 1,
            "date": booking_date,
            "type": "Incoming",
            "category": "Booking Downpayment",
            "description": f"{customer_name} - {pkg_name} ({pkg_type})",
            "amount": downpayment_amount,
            "account": "Gcash/Maya/Bank"
        })

        return jsonify({"success": True, "message": "Booking successfully saved!"})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"success": False, "message": f"Server Error: {str(e)}"}), 500


# ==========================================
# ADMIN API ROUTES (Bookings, POS, Inventory)
# ==========================================

@app.route('/api/admin/bookings', methods=['GET'])
def api_admin_bookings():
    try:
        response = supabase.table("bookings").select("*").execute()
        bookings_data = response.data if response.data else []
        return jsonify({"bookings": bookings_data})
    except Exception as e:
        print("Error fetching bookings:", e)
        return jsonify({"bookings": []})


@app.route('/api/admin/update-status', methods=['POST'])
def api_admin_update_status():
    data = request.json
    booking_id = data.get('id')
    index = data.get('index')
    new_status = data.get('status')

    try:
        response = supabase.table("bookings").select("*").execute()
        bookings_data = response.data if response.data else []

        target_booking = None
        if booking_id:
            for b in bookings_data:
                if b.get('id') == booking_id:
                    target_booking = b
                    break
        elif index is not None and 0 <= index < len(bookings_data):
            target_booking = bookings_data[index]

        if target_booking:
            old_status = target_booking.get('status')
            row_id = target_booking.get('id')

            supabase.table("bookings").update({"status": new_status}).eq("id", row_id).execute()

            if new_status == 'Confirmed' and old_status != 'Confirmed':
                send_confirmation_email(
                    target_booking['email'],
                    target_booking['customer_name'],
                    target_booking['date'],
                    target_booking['schedule'],
                    f"{target_booking['package']} ({target_booking['package_type']})",
                    target_booking['grand_total'],
                    target_booking['balance']
                )

            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Booking not found"}), 404
    except Exception as e:
        print("Error updating status:", e)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/admin/delete-booking', methods=['POST'])
def api_admin_delete_booking():
    data = request.json
    booking_id = data.get('id')
    index = data.get('index')

    try:
        response = supabase.table("bookings").select("*").execute()
        bookings_data = response.data if response.data else []

        target_id = None
        if booking_id:
            target_id = booking_id
        elif index is not None and 0 <= index < len(bookings_data):
            target_id = bookings_data[index].get('id')

        if target_id is not None:
            supabase.table("bookings").delete().eq("id", target_id).execute()
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Booking not found"}), 404
    except Exception as e:
        print("Error deleting booking:", e)
        return jsonify({"success": False, "message": str(e)}), 500


# POS / Transactions Endpoints
@app.route('/api/admin/transactions', methods=['GET', 'POST'])
def api_admin_transactions():
    if request.method == 'GET':
        return jsonify({"transactions": transactions_db})

    data = request.json
    new_tx = {
        "id": len(transactions_db) + 1,
        "date": data.get("date"),
        "type": data.get("type"),
        "category": data.get("category"),
        "description": data.get("description"),
        "amount": float(data.get("amount", 0)),
        "account": data.get("account")
    }
    transactions_db.append(new_tx)
    return jsonify({"success": True, "transaction": new_tx})


@app.route('/api/admin/transactions/delete', methods=['POST'])
def api_admin_delete_transaction():
    data = request.json
    tx_id = data.get("id")
    global transactions_db
    transactions_db = [t for t in transactions_db if t["id"] != tx_id]
    return jsonify({"success": True})


# Inventory Endpoints (Studio & Daily Supplies)
@app.route('/api/admin/inventory', methods=['GET', 'POST'])
def api_admin_inventory():
    if request.method == 'GET':
        return jsonify({"inventory": inventory_db})

    data = request.json
    new_item = {
        "id": len(inventory_db) + 1,
        "category": data.get("category"),
        "name": data.get("name"),
        "quantity": int(data.get("quantity", 0)),
        "unit": data.get("unit", "pcs")
    }
    inventory_db.append(new_item)
    return jsonify({"success": True, "item": new_item})


@app.route('/api/admin/inventory/update', methods=['POST'])
def api_admin_update_inventory():
    data = request.json
    item_id = data.get("id")
    qty_change = int(data.get("quantity_change", 0))

    for item in inventory_db:
        if item["id"] == item_id:
            item["quantity"] += qty_change
            if item["quantity"] < 0:
                item["quantity"] = 0
            return jsonify({"success": True, "item": item})

    return jsonify({"success": False, "message": "Item not found"}), 404


@app.route('/api/admin/inventory/delete', methods=['POST'])
def api_admin_delete_inventory():
    data = request.json
    item_id = data.get("id")
    global inventory_db
    inventory_db = [item for item in inventory_db if item["id"] != item_id]
    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(debug=True)