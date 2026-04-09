from flask import Flask, render_template, request, redirect
import mysql.connector

app = Flask(__name__)

# DATABASE CONNECTION
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root123",
    database="telemedicine"
)

cursor = db.cursor()

# ROUTES
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin():
    cursor.execute("SELECT COUNT(*) FROM patient")
    patient_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM doctor")
    doctor_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM consultation")
    consultation_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM prescription")
    prescription_count = cursor.fetchone()[0]
    return render_template(
        'admin.html',
        patient_count=patient_count,
        doctor_count=doctor_count,
        consultation_count=consultation_count,
        prescription_count=prescription_count,
    )

@app.route('/patient')
def patient():
    return render_template('patient.html')

@app.route('/patient_list')
def patient_list():
    cursor.execute("SELECT patient_id, name, dob, phone, email, address FROM patient ORDER BY patient_id DESC")
    patients = cursor.fetchall()
    return render_template('patient_list.html', patients=patients)

@app.route('/delete_patient/<int:patient_id>')
def delete_patient(patient_id):
    cursor.execute("DELETE FROM patient WHERE patient_id = %s", (patient_id,))
    db.commit()
    return redirect('/patient_list')

@app.route('/doctor')
def doctor():
    return render_template('doctor.html')

@app.route('/doctor_list')
def doctor_list():
    cursor.execute("SELECT doctor_id, name, specialization, phone, email, department FROM doctor ORDER BY doctor_id DESC")
    doctors = cursor.fetchall()
    return render_template('doctor_list.html', doctors=doctors)

@app.route('/delete_doctor/<int:doctor_id>')
def delete_doctor(doctor_id):
    cursor.execute("DELETE FROM doctor WHERE doctor_id = %s", (doctor_id,))
    db.commit()
    return redirect('/doctor_list')

@app.route('/consultation')
def consultation():
    cursor.execute("SELECT patient_id, name FROM patient ORDER BY name")
    patients = cursor.fetchall()
    cursor.execute("SELECT doctor_id, name FROM doctor ORDER BY name")
    doctors = cursor.fetchall()
    return render_template('consultation.html', patients=patients, doctors=doctors)

@app.route('/prescription')
def prescription():
    cursor.execute(
        "SELECT c.consultation_id, p.name, d.name, c.date, c.time FROM consultation c JOIN patient p ON c.patient_id = p.patient_id JOIN doctor d ON c.doctor_id = d.doctor_id ORDER BY c.consultation_id DESC"
    )
    consultations = cursor.fetchall()
    return render_template('prescription.html', consultations=consultations)

@app.route('/save_consultation', methods=['POST'])
def save_consultation():
    patient_id = request.form['patient_id']
    doctor_id = request.form['doctor_id']
    date = request.form['date']
    time = request.form['time']
    symptoms = request.form['symptoms']
    diagnosis = request.form['diagnosis']

    cursor.execute(
        "INSERT INTO consultation (patient_id, doctor_id, date, time, symptoms, diagnosis) VALUES (%s, %s, %s, %s, %s, %s)",
        (patient_id, doctor_id, date, time, symptoms, diagnosis),
    )
    db.commit()
    return redirect('/reports')

@app.route('/save_prescription', methods=['POST'])
def save_prescription():
    consultation_id = request.form['consultation_id']
    medicine_name = request.form['medicine_name']
    dosage = request.form['dosage']
    duration = request.form['duration']
    notes = request.form['notes']

    cursor.execute(
        "INSERT INTO prescription (consultation_id, medicine_name, dosage, duration, notes) VALUES (%s, %s, %s, %s, %s)",
        (consultation_id, medicine_name, dosage, duration, notes),
    )
    db.commit()
    return redirect('/reports')

@app.route('/reports')
def reports():
    cursor.execute(
        "SELECT c.consultation_id, p.name, d.name, c.date, c.time, c.symptoms, c.diagnosis FROM consultation c JOIN patient p ON c.patient_id = p.patient_id JOIN doctor d ON c.doctor_id = d.doctor_id ORDER BY c.consultation_id DESC"
    )
    consultations = cursor.fetchall()
    cursor.execute(
        "SELECT r.prescription_id, r.consultation_id, p.name, d.name, r.medicine_name, r.dosage, r.duration, r.notes FROM prescription r JOIN consultation c ON r.consultation_id = c.consultation_id JOIN patient p ON c.patient_id = p.patient_id JOIN doctor d ON c.doctor_id = d.doctor_id ORDER BY r.prescription_id DESC"
    )
    prescriptions = cursor.fetchall()
    return render_template('reports.html', consultations=consultations, prescriptions=prescriptions)

@app.route('/doctor_dashboard')
def doctor_dashboard():
    cursor.execute(
        "SELECT c.consultation_id, p.name, c.date, c.time, c.diagnosis FROM consultation c JOIN patient p ON c.patient_id = p.patient_id ORDER BY c.consultation_id DESC"
    )
    consultations = cursor.fetchall()
    return render_template('doctor-dashboard.html', consultations=consultations)

@app.route('/doctor-dashboard')
def doctor_dashboard_dash():
    return redirect('/doctor_dashboard')

@app.route('/doctor-dashboard.html')
def doctor_dashboard_html():
    return redirect('/doctor_dashboard')

@app.route('/consultation.html')
def consultation_html():
    return redirect('/consultation')

@app.route('/prescription.html')
def prescription_html():
    return redirect('/prescription')

@app.route('/admin.html')
def admin_html():
    return redirect('/admin')

@app.route('/patient.html')
def patient_html():
    return redirect('/patient')

@app.route('/doctor.html')
def doctor_html():
    return redirect('/doctor')

@app.route('/reports.html')
def reports_html():
    return redirect('/reports')

@app.route('/index.html')
def index_html():
    return redirect('/')

# SAVE PATIENT
@app.route('/save_patient', methods=['POST'])
def save_patient():
    name = request.form['name']
    dob = request.form['dob']
    phone = request.form['phone']
    email = request.form['email']
    address = request.form['address']

    sql = "INSERT INTO Patient (name, dob, phone, email, address) VALUES (%s, %s, %s, %s, %s)"
    values = (name, dob, phone, email, address)

    cursor.execute(sql, values)
    db.commit()

    return redirect('/admin')

# SAVE DOCTOR
@app.route('/save_doctor', methods=['POST'])
def save_doctor():
    name = request.form['name']
    specialization = request.form['specialization']
    phone = request.form['phone']
    email = request.form['email']
    department = request.form['department']

    sql = "INSERT INTO Doctor (name, specialization, phone, email, department) VALUES (%s, %s, %s, %s, %s)"
    values = (name, specialization, phone, email, department)

    cursor.execute(sql, values)
    db.commit()

    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)