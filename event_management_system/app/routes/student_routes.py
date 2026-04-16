"""
Student Routes Module
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from utils.auth import login_required
from utils.database import get_one, get_all, insert, update, delete
from utils.validation import check_student_eligibility
from datetime import datetime
import os

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/dashboard')
@login_required('student')
def dashboard():
    """Student dashboard"""
    student_id = session.get('student_id')
    
    try:
        # Get student info
        student = get_one(
            "SELECT * FROM students WHERE student_id = %s",
            (student_id,)
        )
        
        # Get upcoming events
        query = """
            SELECT e.* FROM events e
            WHERE e.event_status = 'upcoming' AND e.is_active = TRUE
            ORDER BY e.event_date ASC
            LIMIT 10
        """
        upcoming_events = get_all(query)
        
        # Get registered events
        query = """
            SELECT e.*, r.registration_id, r.registration_status,
                   CASE 
                       WHEN a.attendance_status = 'present' THEN 'Attended'
                       ELSE 'Not Attended'
                   END as attendance_status
            FROM events e
            JOIN registrations r ON e.event_id = r.event_id
            LEFT JOIN attendance a ON r.registration_id = a.registration_id
            WHERE r.student_id = %s
            ORDER BY e.event_date DESC
        """
        registered_events = get_all(query, (student_id,))
        
        # Get certificates
        query = """
            SELECT c.*, e.event_name FROM certificates c
            JOIN events e ON c.event_id = e.event_id
            WHERE c.student_id = %s
            ORDER BY c.issue_date DESC
        """
        certificates = get_all(query, (student_id,))
        
        return render_template('student/dashboard.html',
                             student=student,
                             upcoming_events=upcoming_events,
                             registered_events=registered_events,
                             certificates=certificates)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash(f'Dashboard Error: {str(e)}', 'danger')
        return redirect(url_for('index'))


@student_bp.route('/events')
@login_required('student')
def view_events():
    """View all available events"""
    student_id = session.get('student_id')
    
    try:
        # Get student CGPA and attendance
        student = get_one(
            "SELECT cgpa, attendance FROM students WHERE student_id = %s",
            (student_id,)
        )
        
        # Search and filter
        search = request.args.get('search', '')
        department_filter = request.args.get('department', '')
        date_filter = request.args.get('date', '')
        
        query = """
            SELECT DISTINCT e.* FROM events e
            WHERE e.event_status IN ('upcoming', 'ongoing') AND e.is_active = TRUE
        """
        params = []
        
        if search:
            query += " AND e.event_name LIKE %s"
            params.append(f"%{search}%")
        
        if date_filter:
            query += " AND DATE(e.event_date) = %s"
            params.append(date_filter)
        
        query += " ORDER BY e.event_date ASC"
        
        events = get_all(query, params) if params else get_all(query)
        
        # Check eligibility for each event
        for event in events or []:
            eligible, reasons = check_student_eligibility(
                student['cgpa'],
                student['attendance'],
                event['min_cgpa'],
                event['min_attendance']
            )
            event['is_eligible'] = eligible
            event['ineligibility_reasons'] = reasons
            
            # Check if already registered
            reg = get_one(
                "SELECT registration_id FROM registrations WHERE student_id = %s AND event_id = %s",
                (student_id, event['event_id'])
            )
            event['is_registered'] = reg is not None
        
        return render_template('student/events.html',
                             events=events,
                             student=student)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('student.dashboard'))


@student_bp.route('/register/<int:event_id>', methods=['POST'])
@login_required('student')
def register_event(event_id):
    """Register for an event"""
    student_id = session.get('student_id')
    
    try:
        # Get student info
        student = get_one(
            "SELECT cgpa, attendance, name FROM students WHERE student_id = %s",
            (student_id,)
        )
        
        # Get event info
        event = get_one(
            "SELECT * FROM events WHERE event_id = %s",
            (event_id,)
        )
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        # Check eligibility
        eligible, reasons = check_student_eligibility(
            student['cgpa'],
            student['attendance'],
            event['min_cgpa'],
            event['min_attendance']
        )
        
        if not eligible:
            return jsonify({
                'success': False,
                'message': 'You do not meet the eligibility criteria',
                'reasons': reasons
            }), 400
        
        # Check if already registered
        existing = get_one(
            "SELECT registration_id FROM registrations WHERE student_id = %s AND event_id = %s",
            (student_id, event_id)
        )
        
        if existing:
            return jsonify({
                'success': False,
                'message': 'You are already registered for this event'
            }), 400
            
        # Face Capture from WebRTC
        try:
            req_data = request.get_json(silent=True) or {}
            face_image_b64 = req_data.get('face_image')
            
            if not face_image_b64:
                return jsonify({'success': False, 'message': 'Face image is required for registration.'}), 400

            from app.modules.face_recognition_module import get_face_manager
            import os
            fm = get_face_manager()
            
            print("Processing face recognition from base64...")
            enc, img_filename = fm.process_base64_face(f"student_{student_id}", face_image_b64)
            
            if enc is not None:
                # Update student face encoding globally if needed
                update("UPDATE students SET face_encoding = %s WHERE student_id = %s", (f"student_{student_id}.pkl", student_id))
            else:
                return jsonify({'success': False, 'message': 'No face detected or capture failed. Registration aborted.'}), 400
        except Exception as face_err:
            print(f"Face capture error: {face_err}")
            return jsonify({'success': False, 'message': f'Face capture error: {str(face_err)}'}), 500
        
        # Create registration
        query = """
            INSERT INTO registrations (student_id, event_id, is_eligible, registered_face_image)
            VALUES (%s, %s, %s, %s)
            RETURNING registration_id
        """
        # Because insert in database.py might not fully support RETURNING reliably unless we use PostgreSQL,
        # Let's do standard insert and get ID if SQLite, but they use supabase.
        registration_id = insert(query, (student_id, event_id, True, img_filename))
        
        # If event is paid, create payment order
        if event['is_paid']:
            return jsonify({
                'success': True,
                'message': 'Registration successful. Please proceed to payment.',
                'registration_id': registration_id,
                'requires_payment': True,
                'amount': float(event['event_fee']),
                'redirect_url': url_for('student.initiate_payment', registration_id=registration_id)
            })
        else:
            flash('Successfully registered for the event!', 'success')
            return jsonify({
                'success': True,
                'message': 'Successfully registered for the event!',
                'requires_payment': False
            })
    
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500


@student_bp.route('/payment/<int:registration_id>')
@login_required('student')
def initiate_payment(registration_id):
    """Initiate payment for event"""
    student_id = session.get('student_id')
    
    try:
        # Get registration and event details
        query = """
            SELECT r.*, e.event_name, e.event_fee, s.email, s.name
            FROM registrations r
            JOIN events e ON r.event_id = e.event_id
            JOIN students s ON r.student_id = s.student_id
            WHERE r.registration_id = %s AND r.student_id = %s
        """
        registration = get_one(query, (registration_id, student_id))
        
        if not registration:
            flash('Registration not found', 'danger')
            return redirect(url_for('student.dashboard'))
        
        return render_template('student/payment.html',
                             registration=registration)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('student.dashboard'))


@student_bp.route('/payment/verify', methods=['POST'])
@login_required('student')
def verify_payment():
    """Verify Razorpay payment"""
    student_id = session.get('student_id')
    
    try:
        data = request.get_json()
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')
        registration_id = data.get('registration_id')
        
        # Get registration details
        registration = get_one(
            "SELECT * FROM registrations WHERE registration_id = %s AND student_id = %s",
            (registration_id, student_id)
        )
        
        if not registration:
            return jsonify({'success': False, 'message': 'Registration not found'}), 404
        
        # Verify payment signature
        from app.modules.payment_module import get_payment_manager
        from flask import current_app
        
        payment_manager = get_payment_manager(current_app)
        key_secret = current_app.config['RAZORPAY_KEY_SECRET']
        
        is_valid = payment_manager.verify_payment_signature(
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
            key_secret
        )
        
        if not is_valid:
            return jsonify({'success': False, 'message': 'Payment verification failed'}), 400
        
        # Get event details for payment record
        event = get_one(
            "SELECT event_fee FROM events WHERE event_id = %s",
            (registration['event_id'],)
        )
        
        # Insert payment record
        query = """
            INSERT INTO payments 
            (registration_id, student_id, event_id, amount, razorpay_order_id, 
             razorpay_payment_id, razorpay_signature, payment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed')
        """
        insert(query, (
            registration_id,
            student_id,
            registration['event_id'],
            event['event_fee'],
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature
        ))
        
        # Update registration status
        update(
            "UPDATE registrations SET registration_status = 'registered' WHERE registration_id = %s",
            (registration_id,)
        )
        
        return jsonify({'success': True, 'message': 'Payment successful!'})
    
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500


@student_bp.route('/payment/demo-process', methods=['POST'])
@login_required('student')
def process_demo_payment():
    """Process demo payment without real gateway"""
    student_id = session.get('student_id')
    import time
    import uuid
    
    try:
        data = request.get_json()
        registration_id = data.get('registration_id')
        payment_method = data.get('payment_method') # 'QR' or 'Card'
        
        # Get registration details
        registration = get_one(
            "SELECT * FROM registrations WHERE registration_id = %s AND student_id = %s",
            (registration_id, student_id)
        )
        
        if not registration:
            return jsonify({'success': False, 'message': 'Registration not found'}), 404
            
        # Check if already paid
        existing_payment = get_one(
            "SELECT payment_id FROM payments WHERE registration_id = %s AND payment_status = 'completed'",
            (registration_id,)
        )
        if existing_payment:
            return jsonify({'success': False, 'message': 'Payment already completed for this event'})

        # Simulate processing delay
        time.sleep(1.5)
        
        # Get event details
        event = get_one("SELECT event_fee, event_id FROM events WHERE event_id = %s", (registration['event_id'],))
        
        # Fake transaction IDs
        fake_order_id = f"demo_order_{uuid.uuid4().hex[:8]}"
        fake_payment_id = f"demo_pay_{uuid.uuid4().hex[:10]}"
        
        # Insert payment record
        query = """
            INSERT INTO payments 
            (registration_id, student_id, event_id, amount, razorpay_order_id, 
             razorpay_payment_id, payment_status, payment_method)
            VALUES (%s, %s, %s, %s, %s, %s, 'completed', %s)
        """
        insert(query, (
            registration_id,
            student_id,
            registration['event_id'],
            event['event_fee'],
            fake_order_id,
            fake_payment_id,
            payment_method
        ))
        
        # Update registration status
        update(
            "UPDATE registrations SET registration_status = 'registered' WHERE registration_id = %s",
            (registration_id,)
        )
        
        return jsonify({'success': True, 'message': 'Payment Successful!'})
        
    except Exception as e:
        print(f"Demo Payment error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@student_bp.route('/certificates')
@login_required('student')
def view_certificates():
    """View certificates"""
    student_id = session.get('student_id')
    
    try:
        query = """
            SELECT c.*, e.event_name, e.event_date
            FROM certificates c
            JOIN events e ON c.event_id = e.event_id
            WHERE c.student_id = %s
            ORDER BY c.issue_date DESC
        """
        certificates = get_all(query, (student_id,))
        
        return render_template('student/certificates.html',
                             certificates=certificates)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('student.dashboard'))


@student_bp.route('/certificate/download/<int:certificate_id>')
@login_required('student')
def download_certificate(certificate_id):
    """Download certificate"""
    student_id = session.get('student_id')
    
    try:
        cert = get_one(
            "SELECT * FROM certificates WHERE certificate_id = %s AND student_id = %s",
            (certificate_id, student_id)
        )
        
        if not cert:
            flash('Certificate record not found', 'danger')
            return redirect(url_for('student.view_certificates'))
        
        # Update download count
        update(
            "UPDATE certificates SET download_count = download_count + 1, last_download_date = CURRENT_TIMESTAMP WHERE certificate_id = %s",
            (certificate_id,)
        )

        # Check if we should serve from database BLOB or file path
        if cert.get('certificate_pdf'):
            import io
            # Convert BYTEA/BLOB to BytesIO for Flask to send
            pdf_data = cert['certificate_pdf']
            # Handle potential memoryview objects from psycopg2
            if isinstance(pdf_data, memoryview):
                pdf_data = pdf_data.tobytes()
                
            return send_file(
                io.BytesIO(pdf_data),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"certificate_{cert['certificate_number']}.pdf"
            )
        elif cert.get('certificate_file_path') and os.path.exists(cert['certificate_file_path']):
            return send_file(cert['certificate_file_path'],
                            as_attachment=True,
                            download_name=f"certificate_{cert['certificate_number']}.pdf")
        else:
            flash('Certificate file not found on server or database', 'danger')
            return redirect(url_for('student.view_certificates'))
    
    except Exception as e:
        print(f"Database error: {e}")
        flash(f'Download Error: {str(e)}', 'danger')
        return redirect(url_for('student.view_certificates'))


@student_bp.route('/profile')
@login_required('student')
def profile():
    """View student profile"""
    student_id = session.get('student_id')
    
    try:
        student = get_one(
            "SELECT * FROM students WHERE student_id = %s",
            (student_id,)
        )
        
        return render_template('student/profile.html', student=student)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('student.dashboard'))


@student_bp.route('/profile/update', methods=['POST'])
@login_required('student')
def update_profile():
    """Update student profile"""
    student_id = session.get('student_id')
    
    try:
        cgpa = request.form.get('cgpa', '0')
        attendance = request.form.get('attendance', '0')
        phone = request.form.get('phone', '')
        
        query = """
            UPDATE students
            SET cgpa = %s, attendance = %s, phone = %s
            WHERE student_id = %s
        """
        update(query, (float(cgpa), float(attendance), phone, student_id))
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('student.profile'))
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('student.profile'))
