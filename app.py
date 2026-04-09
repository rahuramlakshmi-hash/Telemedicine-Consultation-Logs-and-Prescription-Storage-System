from flask import Flask, g, redirect, render_template, request
import mysql.connector
import os

app = Flask(__name__)

TABLE_CANDIDATES = {
    "patient": ["patient", "Patient"],
    "doctor": ["doctor", "Doctor"],
    "consultation": ["consultation", "Consultation"],
    "prescription": ["prescription", "Prescription"],
}


def get_db_config():
    return {
        "host": os.environ.get("DB_HOST", "sql.freedb.tech"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "freedb_telemedicine"),
        "password": os.environ.get("DB_PASSWORD"),
        "database": os.environ.get("DB_NAME", "freedb_telemedicine_db"),
        "connection_timeout": int(os.environ.get("DB_TIMEOUT", "10")),
    }


def get_db():
    if "db" not in g:
        config = get_db_config()
        if not config["password"]:
            raise RuntimeError(
                "DB_PASSWORD is not set. Add your FreeDB password in Render environment variables."
            )
        g.db = mysql.connector.connect(**config)
    return g.db


def get_cursor():
    if "cursor" not in g:
        g.cursor = get_db().cursor()
    return g.cursor


def get_table_name(logical_name):
    cache = g.setdefault("table_name_cache", {})
    if logical_name in cache:
        return cache[logical_name]

    cursor = get_cursor()
    cursor.execute("SHOW TABLES")
    available_tables = {row[0] for row in cursor.fetchall()}
    available_by_lower = {name.lower(): name for name in available_tables}

    for candidate in TABLE_CANDIDATES.get(logical_name, [logical_name]):
        if candidate in available_tables:
            cache[logical_name] = candidate
            return candidate
        if candidate.lower() in available_by_lower:
            cache[logical_name] = available_by_lower[candidate.lower()]
            return cache[logical_name]

    raise RuntimeError(
        f"Missing expected table for '{logical_name}'. Found tables: {sorted(available_tables)}"
    )


@app.teardown_appcontext
def close_db(error):
    cursor = g.pop("cursor", None)
    if cursor is not None:
        cursor.close()

    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def fetch_count(table_name):
    cursor = get_cursor()
    resolved_table = get_table_name(table_name)
    cursor.execute(f"SELECT COUNT(*) FROM `{resolved_table}`")
    return cursor.fetchone()[0]


# ROUTES
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        patient_count=fetch_count("patient"),
        doctor_count=fetch_count("doctor"),
        consultation_count=fetch_count("consultation"),
        prescription_count=fetch_count("prescription"),
    )


@app.route("/patient")
def patient():
    return render_template("patient.html")


@app.route("/patient_list")
def patient_list():
    cursor = get_cursor()
    patient_table = get_table_name("patient")
    cursor.execute(
        "SELECT patient_id, name, dob, phone, email, address "
        f"FROM `{patient_table}` ORDER BY patient_id DESC"
    )
    patients = cursor.fetchall()
    return render_template("patient_list.html", patients=patients)


@app.route("/delete_patient/<int:patient_id>")
def delete_patient(patient_id):
    cursor = get_cursor()
    patient_table = get_table_name("patient")
    cursor.execute(f"DELETE FROM `{patient_table}` WHERE patient_id = %s", (patient_id,))
    get_db().commit()
    return redirect("/patient_list")


@app.route("/doctor")
def doctor():
    return render_template("doctor.html")


@app.route("/doctor_list")
def doctor_list():
    cursor = get_cursor()
    doctor_table = get_table_name("doctor")
    cursor.execute(
        "SELECT doctor_id, name, specialization, phone, email, department "
        f"FROM `{doctor_table}` ORDER BY doctor_id DESC"
    )
    doctors = cursor.fetchall()
    return render_template("doctor_list.html", doctors=doctors)


@app.route("/delete_doctor/<int:doctor_id>")
def delete_doctor(doctor_id):
    cursor = get_cursor()
    doctor_table = get_table_name("doctor")
    cursor.execute(f"DELETE FROM `{doctor_table}` WHERE doctor_id = %s", (doctor_id,))
    get_db().commit()
    return redirect("/doctor_list")


@app.route("/consultation")
def consultation():
    cursor = get_cursor()
    patient_table = get_table_name("patient")
    doctor_table = get_table_name("doctor")
    cursor.execute(f"SELECT patient_id, name FROM `{patient_table}` ORDER BY name")
    patients = cursor.fetchall()
    cursor.execute(f"SELECT doctor_id, name FROM `{doctor_table}` ORDER BY name")
    doctors = cursor.fetchall()
    return render_template("consultation.html", patients=patients, doctors=doctors)


@app.route("/prescription")
def prescription():
    cursor = get_cursor()
    consultation_table = get_table_name("consultation")
    patient_table = get_table_name("patient")
    doctor_table = get_table_name("doctor")
    cursor.execute(
        "SELECT c.consultation_id, p.name, d.name, c.date, c.time "
        f"FROM `{consultation_table}` c "
        f"JOIN `{patient_table}` p ON c.patient_id = p.patient_id "
        f"JOIN `{doctor_table}` d ON c.doctor_id = d.doctor_id "
        "ORDER BY c.consultation_id DESC"
    )
    consultations = cursor.fetchall()
    return render_template("prescription.html", consultations=consultations)


@app.route("/save_consultation", methods=["POST"])
def save_consultation():
    patient_id = request.form["patient_id"]
    doctor_id = request.form["doctor_id"]
    date = request.form["date"]
    time = request.form["time"]
    symptoms = request.form["symptoms"]
    diagnosis = request.form["diagnosis"]

    cursor = get_cursor()
    consultation_table = get_table_name("consultation")
    cursor.execute(
        f"INSERT INTO `{consultation_table}` "
        "(patient_id, doctor_id, date, time, symptoms, diagnosis) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (patient_id, doctor_id, date, time, symptoms, diagnosis),
    )
    get_db().commit()
    return redirect("/reports")


@app.route("/save_prescription", methods=["POST"])
def save_prescription():
    consultation_id = request.form["consultation_id"]
    medicine_name = request.form["medicine_name"]
    dosage = request.form["dosage"]
    duration = request.form["duration"]
    notes = request.form["notes"]

    cursor = get_cursor()
    prescription_table = get_table_name("prescription")
    cursor.execute(
        f"INSERT INTO `{prescription_table}` "
        "(consultation_id, medicine_name, dosage, duration, notes) "
        "VALUES (%s, %s, %s, %s, %s)",
        (consultation_id, medicine_name, dosage, duration, notes),
    )
    get_db().commit()
    return redirect("/reports")


@app.route("/reports")
def reports():
    cursor = get_cursor()
    consultation_table = get_table_name("consultation")
    patient_table = get_table_name("patient")
    doctor_table = get_table_name("doctor")
    prescription_table = get_table_name("prescription")
    cursor.execute(
        "SELECT c.consultation_id, p.name, d.name, c.date, c.time, c.symptoms, c.diagnosis "
        f"FROM `{consultation_table}` c "
        f"JOIN `{patient_table}` p ON c.patient_id = p.patient_id "
        f"JOIN `{doctor_table}` d ON c.doctor_id = d.doctor_id "
        "ORDER BY c.consultation_id DESC"
    )
    consultations = cursor.fetchall()
    cursor.execute(
        "SELECT r.prescription_id, r.consultation_id, p.name, d.name, r.medicine_name, "
        "r.dosage, r.duration, r.notes "
        f"FROM `{prescription_table}` r "
        f"JOIN `{consultation_table}` c ON r.consultation_id = c.consultation_id "
        f"JOIN `{patient_table}` p ON c.patient_id = p.patient_id "
        f"JOIN `{doctor_table}` d ON c.doctor_id = d.doctor_id "
        "ORDER BY r.prescription_id DESC"
    )
    prescriptions = cursor.fetchall()
    return render_template(
        "reports.html",
        consultations=consultations,
        prescriptions=prescriptions,
    )


@app.route("/doctor_dashboard")
def doctor_dashboard():
    cursor = get_cursor()
    consultation_table = get_table_name("consultation")
    patient_table = get_table_name("patient")
    cursor.execute(
        "SELECT c.consultation_id, p.name, c.date, c.time, c.diagnosis "
        f"FROM `{consultation_table}` c "
        f"JOIN `{patient_table}` p ON c.patient_id = p.patient_id "
        "ORDER BY c.consultation_id DESC"
    )
    consultations = cursor.fetchall()
    return render_template("doctor-dashboard.html", consultations=consultations)


@app.route("/doctor-dashboard")
def doctor_dashboard_dash():
    return redirect("/doctor_dashboard")


@app.route("/doctor-dashboard.html")
def doctor_dashboard_html():
    return redirect("/doctor_dashboard")


@app.route("/consultation.html")
def consultation_html():
    return redirect("/consultation")


@app.route("/prescription.html")
def prescription_html():
    return redirect("/prescription")


@app.route("/admin.html")
def admin_html():
    return redirect("/admin")


@app.route("/patient.html")
def patient_html():
    return redirect("/patient")


@app.route("/doctor.html")
def doctor_html():
    return redirect("/doctor")


@app.route("/reports.html")
def reports_html():
    return redirect("/reports")


@app.route("/index.html")
def index_html():
    return redirect("/")


@app.route("/save_patient", methods=["POST"])
def save_patient():
    name = request.form["name"]
    dob = request.form["dob"]
    phone = request.form["phone"]
    email = request.form["email"]
    address = request.form["address"]

    cursor = get_cursor()
    patient_table = get_table_name("patient")
    cursor.execute(
        f"INSERT INTO `{patient_table}` (name, dob, phone, email, address) "
        "VALUES (%s, %s, %s, %s, %s)",
        (name, dob, phone, email, address),
    )
    get_db().commit()
    return redirect("/admin")


@app.route("/save_doctor", methods=["POST"])
def save_doctor():
    name = request.form["name"]
    specialization = request.form["specialization"]
    phone = request.form["phone"]
    email = request.form["email"]
    department = request.form["department"]

    cursor = get_cursor()
    doctor_table = get_table_name("doctor")
    cursor.execute(
        f"INSERT INTO `{doctor_table}` (name, specialization, phone, email, department) "
        "VALUES (%s, %s, %s, %s, %s)",
        (name, specialization, phone, email, department),
    )
    get_db().commit()
    return redirect("/admin")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
