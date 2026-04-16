"""
Event Organiser Routes Module
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from utils.auth import login_required
from utils.database import get_one, get_all, insert, update, delete
from utils.validation import validate_event_creation
from datetime import datetime

organiser_bp = Blueprint('organiser', __name__, url_prefix='/organiser')


@organiser_bp.route('/dashboard')
@login_required('organiser')
def dashboard():
    """Organiser dashboard"""
    organiser_id = session.get('organiser_id')
    
    try:
        # Get assigned events
        events = get_all("""
            SELECT e.*, COUNT(r.registration_id) as total_registrations
            FROM events e
            LEFT JOIN registrations r ON e.event_id = r.event_id
            WHERE e.organiser_id = %s
            GROUP BY e.event_id
            ORDER BY e.event_date DESC
        """, (organiser_id,))
        
        # Calculate statistics
        stats = {
            'total_events': len(events) if events else 0,
            'upcoming_events': len([e for e in events or [] if e['event_status'] == 'upcoming']),
            'ongoing_events': len([e for e in events or [] if e['event_status'] == 'ongoing']),
            'completed_events': len([e for e in events or [] if e['event_status'] == 'completed']),
            'total_registrations': sum(e['total_registrations'] or 0 for e in events or [])
        }
        
        return render_template('organiser/dashboard.html',
                             events=events,
                             stats=stats)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('index'))


@organiser_bp.route('/event/create', methods=['GET', 'POST'])
@login_required('organiser')
def create_event():
    """Create new event"""
    organiser_id = session.get('organiser_id')
    
    if request.method == 'POST':
        event_name = request.form.get('event_name', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '')
        event_time = request.form.get('event_time', '')
        location = request.form.get('location', '').strip()
        max_capacity = request.form.get('max_capacity', '')
        min_cgpa = request.form.get('min_cgpa', '0')
        min_attendance = request.form.get('min_attendance', '0')
        is_paid = request.form.get('is_paid') == 'on'
        event_fee = request.form.get('event_fee', '0') if is_paid else '0'
        
        # Validation
        data = {
            'event_name': event_name,
            'event_date': event_date,
            'min_cgpa': min_cgpa,
            'min_attendance': min_attendance,
            'is_paid': is_paid,
            'event_fee': event_fee
        }
        
        errors = validate_event_creation(data)
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('organiser/create_event.html')
        
        try:
            query = """
                INSERT INTO events 
                (event_name, description, event_date, event_time, location, max_capacity,
                 min_cgpa, min_attendance, is_paid, event_fee, organiser_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                event_name, description, event_date, event_time, location,
                int(max_capacity) if max_capacity else None,
                float(min_cgpa), float(min_attendance),
                is_paid, float(event_fee) if is_paid else 0,
                organiser_id
            )
            
            insert(query, params)
            
            flash('Event created successfully!', 'success')
            return redirect(url_for('organiser.dashboard'))
        
        except Exception as e:
            print(f"Database error: {e}")
            flash('An error occurred while creating the event', 'danger')
    
    return render_template('organiser/create_event.html')


@organiser_bp.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required('organiser')
def edit_event(event_id):
    """Edit event"""
    organiser_id = session.get('organiser_id')
    
    try:
        event = get_one(
            "SELECT * FROM events WHERE event_id = %s AND organiser_id = %s",
            (event_id, organiser_id)
        )
        
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('organiser.dashboard'))
        
        if request.method == 'POST':
            event_name = request.form.get('event_name', '').strip()
            description = request.form.get('description', '').strip()
            event_date = request.form.get('event_date', '')
            event_time = request.form.get('event_time', '')
            location = request.form.get('location', '').strip()
            max_capacity = request.form.get('max_capacity', '')
            min_cgpa = request.form.get('min_cgpa', '0')
            min_attendance = request.form.get('min_attendance', '0')
            is_paid = request.form.get('is_paid') == 'on'
            event_fee = request.form.get('event_fee', '0') if is_paid else '0'
            event_status = request.form.get('event_status', 'upcoming')
            
            query = """
                UPDATE events
                SET event_name = %s, description = %s, event_date = %s, event_time = %s,
                    location = %s, max_capacity = %s, min_cgpa = %s, min_attendance = %s,
                    is_paid = %s, event_fee = %s, event_status = %s
                WHERE event_id = %s AND organiser_id = %s
            """
            
            params = (
                event_name, description, event_date, event_time, location,
                int(max_capacity) if max_capacity else None,
                float(min_cgpa), float(min_attendance),
                is_paid, float(event_fee) if is_paid else 0,
                event_status,
                event_id, organiser_id
            )
            
            update(query, params)
            
            flash('Event updated successfully!', 'success')
            return redirect(url_for('organiser.dashboard'))
        
        return render_template('organiser/edit_event.html', event=event)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('organiser.dashboard'))


@organiser_bp.route('/event/<int:event_id>/delete', methods=['POST'])
@login_required('organiser')
def delete_event(event_id):
    """Delete event"""
    organiser_id = session.get('organiser_id')
    
    try:
        event = get_one(
            "SELECT event_id FROM events WHERE event_id = %s AND organiser_id = %s",
            (event_id, organiser_id)
        )
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        delete("DELETE FROM events WHERE event_id = %s AND organiser_id = %s", (event_id, organiser_id))
        
        flash('Event deleted successfully!', 'success')
        return redirect(url_for('organiser.dashboard'))
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred while deleting the event', 'danger')
        return redirect(url_for('organiser.dashboard'))


@organiser_bp.route('/event/<int:event_id>')
@login_required('organiser')
def view_event(event_id):
    """View event details"""
    organiser_id = session.get('organiser_id')
    
    try:
        event = get_one("""
            SELECT e.* FROM events e
            WHERE e.event_id = %s AND e.organiser_id = %s
        """, (event_id, organiser_id))
        
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('organiser.dashboard'))
        
        # Get registered students
        students = get_all("""
            SELECT r.*, s.student_id, s.name, s.email, s.enrollment_number,
                   a.attendance_status, c.certificate_id
            FROM registrations r
            JOIN students s ON r.student_id = s.student_id
            LEFT JOIN attendance a ON r.registration_id = a.registration_id
            LEFT JOIN certificates c ON r.registration_id = c.registration_id
            WHERE r.event_id = %s
            ORDER BY s.name
        """, (event_id,))
        
        return render_template('organiser/event_details.html',
                             event=event,
                             students=students)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('organiser.dashboard'))


@organiser_bp.route('/attendance/<int:event_id>')
@login_required('organiser')
def mark_attendance(event_id):
    """Mark attendance for event"""
    organiser_id = session.get('organiser_id')
    
    try:
        event = get_one("""
            SELECT e.* FROM events e
            WHERE e.event_id = %s AND e.organiser_id = %s
        """, (event_id, organiser_id))
        
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('organiser.dashboard'))
        
        # Get registered students
        students = get_all("""
            SELECT r.registration_id, s.student_id, s.name, s.email,
                   COALESCE(a.attendance_status, 'absent') as attendance_status
            FROM registrations r
            JOIN students s ON r.student_id = s.student_id
            LEFT JOIN attendance a ON r.registration_id = a.registration_id
            WHERE r.event_id = %s
            ORDER BY s.name
        """, (event_id,))
        
        return render_template('organiser/mark_attendance.html',
                             event=event,
                             students=students)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('organiser.dashboard'))


@organiser_bp.route('/attendance/save', methods=['POST'])
@login_required('organiser')
def save_attendance():
    """Save attendance records"""
    organiser_id = session.get('organiser_id')
    
    try:
        data = request.get_json()
        event_id = data.get('event_id')
        attendance_records = data.get('attendance', [])
        
        # Verify event belongs to organiser
        event = get_one("""
            SELECT event_id FROM events WHERE event_id = %s AND organiser_id = %s
        """, (event_id, organiser_id))
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        for record in attendance_records:
            registration_id = record.get('registration_id')
            attendance_status = record.get('status')
            
            # Check if attendance record exists
            existing = get_one("""
                SELECT attendance_id FROM attendance
                WHERE registration_id = %s AND event_id = %s
            """, (registration_id, event_id))
            
            if existing:
                # Update existing
                update("""
                    UPDATE attendance
                    SET attendance_status = %s, check_in_time = NOW()
                    WHERE registration_id = %s
                """, (attendance_status, registration_id))
            else:
                # Insert new
                insert("""
                    INSERT INTO attendance
                    (registration_id, event_id, student_id, attendance_status, check_in_time)
                    SELECT r.registration_id, r.event_id, r.student_id, %s, NOW()
                    FROM registrations r
                    WHERE r.registration_id = %s
                """, (attendance_status, registration_id))
        
        # Update registration status to 'participated' if attended
        update("""
            UPDATE registrations
            SET registration_status = 'participated'
            WHERE event_id = %s AND registration_id IN (
                SELECT a.registration_id FROM attendance a
                WHERE a.event_id = %s AND a.attendance_status = 'present'
            )
        """, (event_id, event_id))
        
        return jsonify({'success': True, 'message': 'Attendance saved successfully'})
    
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500


@organiser_bp.route('/face-recognition/<int:event_id>', methods=['POST'])
@login_required('organiser')
def face_recognition_attendance(event_id):
    """Mark attendance using face recognition via WebRTC"""
    organiser_id = session.get('organiser_id')
    
    try:
        data = request.get_json(silent=True) or {}
        face_image_b64 = data.get('face_image')
        
        if not face_image_b64:
            return jsonify({'success': False, 'message': 'Face image required.'}), 400
            
        event = get_one("""
            SELECT e.* FROM events e
            WHERE e.event_id = %s AND e.organiser_id = %s
        """, (event_id, organiser_id))
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found.'}), 404
        
        from app.modules.face_recognition_module import get_face_manager
        import os
        import uuid

        fm = get_face_manager()
        
        # Fetch registered students for this event to compare
        students = get_all("""
            SELECT r.registration_id, s.student_id, s.name, s.face_encoding 
            FROM registrations r
            JOIN students s ON r.student_id = s.student_id
            WHERE r.event_id = %s
        """, (event_id,))
        
        # Perform recognition
        best_match, img_bytes = fm.recognize_single_face(face_image_b64, students)
        
        if best_match:
            # Create uploads directory for faces if it doesn't exist
            faces_upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'faces')
            os.makedirs(faces_upload_dir, exist_ok=True)
            
            # Save attendance image
            attendance_img_name = f"attendance_{event_id}_{best_match['student_id']}_{uuid.uuid4().hex[:8]}.jpg"
            attendance_img_path = os.path.join(faces_upload_dir, attendance_img_name)
            with open(attendance_img_path, 'wb') as f:
                f.write(img_bytes)
                
            reg_id = best_match['registration_id']
            stud_id = best_match['student_id']
            
            existing = get_one("SELECT attendance_id FROM attendance WHERE registration_id=%s", (reg_id,))
            if existing:
                update("UPDATE attendance SET attendance_status='present', check_in_time=NOW(), face_recognition_used=True, attendance_face_image=%s WHERE registration_id=%s", (attendance_img_name, reg_id))
            else:
                insert("INSERT INTO attendance (registration_id, event_id, student_id, attendance_status, check_in_time, face_recognition_used, attendance_face_image) VALUES (%s, %s, %s, 'present', NOW(), True, %s)", (reg_id, event_id, stud_id, attendance_img_name))
            
            update("UPDATE registrations SET registration_status='participated' WHERE registration_id=%s", (reg_id,))
            
            return jsonify({
                'success': True, 
                'message': f"Matched with registered student: {best_match['name']}. Attendance marked Present."
            })
        else:
            return jsonify({
                'success': False, 
                'message': 'Unmatched with registered student. Attendance NOT marked.'
            })
            
    except Exception as e:
        print(f"Face recognition error: {e}")
        return jsonify({'success': False, 'message': f"Face recognition error: {str(e)}"}), 500


@organiser_bp.route('/certificates/<int:event_id>')
@login_required('organiser')
def generate_certificates(event_id):
    """Generate certificates for event participants"""
    organiser_id = session.get('organiser_id')
    
    try:
        event = get_one("""
            SELECT e.* FROM events e
            WHERE e.event_id = %s AND e.organiser_id = %s
        """, (event_id, organiser_id))
        
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('organiser.dashboard'))
        
        # Get students who attended and don't have certificates
        eligible_students = get_all("""
            SELECT r.registration_id, s.student_id, s.name, a.attendance_status
            FROM registrations r
            JOIN students s ON r.student_id = s.student_id
            LEFT JOIN attendance a ON r.registration_id = a.registration_id
            WHERE r.event_id = %s AND a.attendance_status = 'present'
            AND NOT EXISTS (
                SELECT 1 FROM certificates c WHERE c.registration_id = r.registration_id
            )
            ORDER BY s.name
        """, (event_id,))
        
        return render_template('organiser/generate_certificates.html',
                             event=event,
                             eligible_students=eligible_students)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('organiser.dashboard'))


@organiser_bp.route('/certificates/generate', methods=['POST'])
@login_required('organiser')
def create_certificates():
    """Create certificates for selected students"""
    organiser_id = session.get('organiser_id')
    
    try:
        data = request.get_json()
        event_id = data.get('event_id')
        student_ids = data.get('student_ids', [])
        
        from app.modules.certificate_module import get_certificate_generator
        from app.config import get_config
        import os
        import uuid
        
        # Get event details
        event = get_one("""
            SELECT e.event_id, e.event_name, e.event_date, o.organiser_id
            FROM events e
            LEFT JOIN event_organisers o ON e.organiser_id = o.organiser_id
            WHERE e.event_id = %s
        """, (event_id,))
        
        if not event or event['organiser_id'] != organiser_id:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        print(f"Received request to generate certificates for event {event_id} and students {student_ids}")
        
        cert_generator = get_certificate_generator()
        
        count = 0
        for student_id in student_ids:
            print(f"Processing student {student_id}...")
            # Get student info
            student = get_one(
                "SELECT student_id, name FROM students WHERE student_id = %s",
                (student_id,)
            )
            
            # Get registration
            reg = get_one("""
                SELECT registration_id FROM registrations
                WHERE student_id = %s AND event_id = %s
            """, (student_id, event_id))
            
            if not student or not reg:
                print(f"Skipping student {student_id}: student={bool(student)}, reg={bool(reg)}")
                continue
            
            print(f"Found student {student['name']} and registration {reg['registration_id']}")
            
            # Generate unique certificate number
            cert_number = f"CERT-{uuid.uuid4().hex[:8].upper()}"
            
            # Generate certificate PDF
            filepath = cert_generator.generate_certificate(
                student_name=student['name'],
                event_name=event['event_name'],
                event_date=event['event_date'],
                certificate_number=cert_number
            )
            
            if filepath:
                print(f"Successfully generated certificate at {filepath}")
                
                # NEW: Read the PDF binary data to save to database
                pdf_binary = None
                try:
                    with open(filepath, 'rb') as f:
                        pdf_binary = f.read()
                except Exception as read_err:
                    print(f"Failed to read PDF for database storage: {read_err}")
                
                # Save certificate record with binary data
                insert("""
                    INSERT INTO certificates
                    (student_id, event_id, registration_id, certificate_number, issue_date, certificate_file_path, certificate_pdf)
                    VALUES (%s, %s, %s, %s, NOW(), %s, %s)
                """, (student_id, event_id, reg['registration_id'], cert_number, filepath, pdf_binary))
                
                count += 1
            else:
                print(f"Failed to generate certificate PDF for student {student_id}")
        
        return jsonify({
            'success': True,
            'message': f'Generated {count} certificates successfully'
        })
    
    except Exception as e:
        print(f"Error generating certificates: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500


@organiser_bp.route('/profile')
@login_required('organiser')
def profile():
    """View organiser profile"""
    organiser_id = session.get('organiser_id')
    
    try:
        organiser = get_one(
            "SELECT * FROM event_organisers WHERE organiser_id = %s",
            (organiser_id,)
        )
        
        return render_template('organiser/profile.html', organiser=organiser)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('organiser.dashboard'))
