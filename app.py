from flask import Flask, g, redirect, render_template, request
import logging
import os
import sqlite3

import mysql.connector
from mysql.connector import Error as MySQLError

app = Flask(__name__)

TABLE_CANDIDATES = {
    "patient": ["patient", "Patient"],
    "doctor": ["doctor", "Doctor"],
    "consultation": ["consultation", "Consultation"],
    "prescription": ["prescription", "Prescription"],
}

SQLITE_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS patient (
        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        dob TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT NOT NULL,
        address TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS doctor (
        doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        specialization TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT NOT NULL,
        department TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consultation (
        consultation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        symptoms TEXT NOT NULL,
        diagnosis TEXT NOT NULL,
        FOREIGN KEY (patient_id) REFERENCES patient(patient_id),
        FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS prescription (
        prescription_id INTEGER PRIMARY KEY AUTOINCREMENT,
        consultation_id INTEGER NOT NULL,
        medicine_name TEXT NOT NULL,
        dosage TEXT NOT NULL,
        duration TEXT NOT NULL,
        notes TEXT NOT NULL,
        FOREIGN KEY (consultation_id) REFERENCES consultation(consultation_id)
    )
    """,
]


def get_db_config():
    return {
        "host": os.environ.get("DB_HOST", "sql.freedb.tech"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "freedb_telemedicine"),
        "password": os.environ.get("DB_PASSWORD"),
        "database": os.environ.get("DB_NAME", "freedb_telemedicine_db"),
        "connection_timeout": int(os.environ.get("DB_TIMEOUT", "10")),
    }


def get_sqlite_path():
    return os.environ.get("SQLITE_PATH", os.path.join(app.root_path, "telemedicine.db"))


def init_sqlite_db(connection):
    cursor = connection.cursor()
    for statement in SQLITE_SCHEMA:
        cursor.execute(statement)
    connection.commit()
    cursor.close()


def get_db():
    if "db" in g:
        return g.db

    config = get_db_config()
    password = config.get("password")

    if password:
        try:
            g.db = mysql.connector.connect(**config)
            g.db_backend = "mysql"
            return g.db
        except MySQLError as exc:
            app.logger.warning("MySQL unavailable, falling back to SQLite: %s", exc)
    else:
        app.logger.warning("DB_PASSWORD is not set, falling back to SQLite.")

    sqlite_path = get_sqlite_path()
    g.db = sqlite3.connect(sqlite_path)
    g.db.row_factory = None
    g.db_backend = "sqlite"
    init_sqlite_db(g.db)
    return g.db


def get_backend():
    get_db()
    return g.db_backend


def get_cursor():
    if "cursor" not in g:
        g.cursor = get_db().cursor()
    return g.cursor


def adapt_query(query):
    if get_backend() == "sqlite":
        return query.replace("%s", "?")
    return query


def execute_query(query, params=()):
    cursor = get_cursor()
    cursor.execute(adapt_query(query), params)
    return cursor


def commit_db():
    get_db().commit()


def get_table_name(logical_name):
    cache = g.setdefault("table_name_cache", {})
    if logical_name in cache:
        return cache[logical_name]

    if get_backend() == "sqlite":
        cache[logical_name] = logical_name
        return logical_name

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
    backend = g.pop("db_backend", None)
    g.pop("table_name_cache", None)
    if db is None:
        return

    if backend == "mysql" and db.is_connected():
        db.close()
    elif backend == "sqlite":
        db.close()


def fetch_count(table_name):
    resolved_table = get_table_name(table_name)
    cursor = execute_query(f"SELECT COUNT(*) FROM `{resolved_table}`")
    return cursor.fetchone()[0]


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
    patient_table = get_table_name("patient")
    patients = execute_query(
        "SELECT patient_id, name, dob, phone, email, address "
        f"FROM `{patient_table}` ORDER BY patient_id DESC"
    ).fetchall()
    return render_template("patient_list.html", patients=patients)


@app.route("/delete_patient/<int:patient_id>")
def delete_patient(patient_id):
    patient_table = get_table_name("patient")
    execute_query(f"DELETE FROM `{patient_table}` WHERE patient_id = %s", (patient_id,))
    commit_db()
    return redirect("/patient_list")


@app.route("/doctor")
def doctor():
    return render_template("doctor.html")


@app.route("/doctor_list")
def doctor_list():
    doctor_table = get_table_name("doctor")
    doctors = execute_query(
        "SELECT doctor_id, name, specialization, phone, email, department "
        f"FROM `{doctor_table}` ORDER BY doctor_id DESC"
    ).fetchall()
    return render_template("doctor_list.html", doctors=doctors)


@app.route("/delete_doctor/<int:doctor_id>")
def delete_doctor(doctor_id):
    doctor_table = get_table_name("doctor")
    execute_query(f"DELETE FROM `{doctor_table}` WHERE doctor_id = %s", (doctor_id,))
    commit_db()
    return redirect("/doctor_list")


@app.route("/consultation")
def consultation():
    patient_table = get_table_name("patient")
    doctor_table = get_table_name("doctor")
    patients = execute_query(
        f"SELECT patient_id, name FROM `{patient_table}` ORDER BY name"
    ).fetchall()
    doctors = execute_query(
        f"SELECT doctor_id, name FROM `{doctor_table}` ORDER BY name"
    ).fetchall()
    return render_template("consultation.html", patients=patients, doctors=doctors)


@app.route("/prescription")
def prescription():
    consultation_table = get_table_name("consultation")
    patient_table = get_table_name("patient")
    doctor_table = get_table_name("doctor")
    consultations = execute_query(
        "SELECT c.consultation_id, p.name, d.name, c.date, c.time "
        f"FROM `{consultation_table}` c "
        f"JOIN `{patient_table}` p ON c.patient_id = p.patient_id "
        f"JOIN `{doctor_table}` d ON c.doctor_id = d.doctor_id "
        "ORDER BY c.consultation_id DESC"
    ).fetchall()
    return render_template("prescription.html", consultations=consultations)


@app.route("/save_consultation", methods=["POST"])
def save_consultation():
    consultation_table = get_table_name("consultation")
    execute_query(
        f"INSERT INTO `{consultation_table}` "
        "(patient_id, doctor_id, date, time, symptoms, diagnosis) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (
            request.form["patient_id"],
            request.form["doctor_id"],
            request.form["date"],
            request.form["time"],
            request.form["symptoms"],
            request.form["diagnosis"],
        ),
    )
    commit_db()
    return redirect("/reports")


@app.route("/save_prescription", methods=["POST"])
def save_prescription():
    prescription_table = get_table_name("prescription")
    execute_query(
        f"INSERT INTO `{prescription_table}` "
        "(consultation_id, medicine_name, dosage, duration, notes) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            request.form["consultation_id"],
            request.form["medicine_name"],
            request.form["dosage"],
            request.form["duration"],
            request.form["notes"],
        ),
    )
    commit_db()
    return redirect("/reports")


@app.route("/reports")
def reports():
    consultation_table = get_table_name("consultation")
    patient_table = get_table_name("patient")
    doctor_table = get_table_name("doctor")
    prescription_table = get_table_name("prescription")

    consultations = execute_query(
        "SELECT c.consultation_id, p.name, d.name, c.date, c.time, c.symptoms, c.diagnosis "
        f"FROM `{consultation_table}` c "
        f"JOIN `{patient_table}` p ON c.patient_id = p.patient_id "
        f"JOIN `{doctor_table}` d ON c.doctor_id = d.doctor_id "
        "ORDER BY c.consultation_id DESC"
    ).fetchall()

    prescriptions = execute_query(
        "SELECT r.prescription_id, r.consultation_id, p.name, d.name, r.medicine_name, "
        "r.dosage, r.duration, r.notes "
        f"FROM `{prescription_table}` r "
        f"JOIN `{consultation_table}` c ON r.consultation_id = c.consultation_id "
        f"JOIN `{patient_table}` p ON c.patient_id = p.patient_id "
        f"JOIN `{doctor_table}` d ON c.doctor_id = d.doctor_id "
        "ORDER BY r.prescription_id DESC"
    ).fetchall()

    return render_template(
        "reports.html",
        consultations=consultations,
        prescriptions=prescriptions,
    )


@app.route("/doctor_dashboard")
def doctor_dashboard():
    consultation_table = get_table_name("consultation")
    patient_table = get_table_name("patient")
    consultations = execute_query(
        "SELECT c.consultation_id, p.name, c.date, c.time, c.diagnosis "
        f"FROM `{consultation_table}` c "
        f"JOIN `{patient_table}` p ON c.patient_id = p.patient_id "
        "ORDER BY c.consultation_id DESC"
    ).fetchall()
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
    patient_table = get_table_name("patient")
    execute_query(
        f"INSERT INTO `{patient_table}` (name, dob, phone, email, address) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            request.form["name"],
            request.form["dob"],
            request.form["phone"],
            request.form["email"],
            request.form["address"],
        ),
    )
    commit_db()
    return redirect("/admin")


@app.route("/save_doctor", methods=["POST"])
def save_doctor():
    doctor_table = get_table_name("doctor")
    execute_query(
        f"INSERT INTO `{doctor_table}` (name, specialization, phone, email, department) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            request.form["name"],
            request.form["specialization"],
            request.form["phone"],
            request.form["email"],
            request.form["department"],
        ),
    )
    commit_db()
    return redirect("/admin")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
