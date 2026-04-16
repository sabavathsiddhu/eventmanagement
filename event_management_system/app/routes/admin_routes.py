"""
Admin Routes Module
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from utils.auth import login_required, hash_password, verify_password
from utils.database import get_one, get_all, insert, update, delete
from utils.validation import validate_event_creation
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@login_required('admin')
def dashboard():
    """Admin dashboard"""
    admin_id = session.get('admin_id')
    
    try:
        # Get statistics
        total_students = get_one("SELECT COUNT(*) as count FROM students WHERE is_active = TRUE")
        total_events = get_one("SELECT COUNT(*) as count FROM events WHERE is_active = TRUE")
        total_registrations = get_one("SELECT COUNT(*) as count FROM registrations")
        total_payments = get_one(
            "SELECT SUM(amount) as total, COUNT(*) as count FROM payments WHERE payment_status = 'completed'"
        )
        
        # Get recent events
        recent_events = get_all("""
            SELECT * FROM events
            WHERE admin_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (admin_id,))
        
        # Get pending certifications
        pending_certs = get_one("""
            SELECT COUNT(*) as count FROM registrations r
            WHERE r.registration_status = 'participated' 
            AND NOT EXISTS (
                SELECT 1 FROM certificates c WHERE c.registration_id = r.registration_id
            )
        """)
        
        stats = {
            'total_students': total_students['count'] if total_students else 0,
            'total_events': total_events['count'] if total_events else 0,
            'total_registrations': total_registrations['count'] if total_registrations else 0,
            'total_payments': total_payments['total'] if total_payments and total_payments['total'] else 0,
            'payment_count': total_payments['count'] if total_payments else 0,
            'pending_certificates': pending_certs['count'] if pending_certs else 0
        }
        
        return render_template('admin/dashboard.html',
                             stats=stats,
                             recent_events=recent_events)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('index'))


@admin_bp.route('/events')
@login_required('admin')
def manage_events():
    """Manage events"""
    admin_id = session.get('admin_id')
    
    try:
        query = """
            SELECT e.*, o.name as organiser_name
            FROM events e
            LEFT JOIN event_organisers o ON e.organiser_id = o.organiser_id
            WHERE e.admin_id = %s OR e.admin_id IS NULL
            ORDER BY e.event_date DESC
        """
        events = get_all(query, (admin_id,))
        
        return render_template('admin/events.html', events=events)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/event/create', methods=['GET', 'POST'])
@login_required('admin')
def create_event():
    """Create new event"""
    admin_id = session.get('admin_id')
    
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
        organiser_id = request.form.get('organiser_id', '')
        
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
            
            organisers = get_all("SELECT organiser_id, name FROM event_organisers WHERE is_active = TRUE")
            return render_template('admin/create_event.html', organisers=organisers)
        
        try:
            query = """
                INSERT INTO events 
                (event_name, description, event_date, event_time, location, max_capacity,
                 min_cgpa, min_attendance, is_paid, event_fee, organiser_id, admin_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                event_name, description, event_date, event_time, location,
                int(max_capacity) if max_capacity else None,
                float(min_cgpa), float(min_attendance),
                is_paid, float(event_fee) if is_paid else 0,
                int(organiser_id) if organiser_id else None,
                admin_id
            )
            
            event_id = insert(query, params)
            
            flash('Event created successfully!', 'success')
            return redirect(url_for('admin.manage_events'))
        
        except Exception as e:
            print(f"Database error: {e}")
            flash('An error occurred while creating the event', 'danger')
    
    try:
        organisers = get_all("SELECT organiser_id, name FROM event_organisers WHERE is_active = TRUE")
        return render_template('admin/create_event.html', organisers=organisers)
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('admin.manage_events'))


@admin_bp.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required('admin')
def edit_event(event_id):
    """Edit event"""
    admin_id = session.get('admin_id')
    
    try:
        event = get_one(
            "SELECT * FROM events WHERE event_id = %s AND admin_id = %s",
            (event_id, admin_id)
        )
        
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('admin.manage_events'))
        
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
            organiser_id = request.form.get('organiser_id', '')
            
            query = """
                UPDATE events
                SET event_name = %s, description = %s, event_date = %s, event_time = %s,
                    location = %s, max_capacity = %s, min_cgpa = %s, min_attendance = %s,
                    is_paid = %s, event_fee = %s, event_status = %s, organiser_id = %s
                WHERE event_id = %s AND admin_id = %s
            """
            
            params = (
                event_name, description, event_date, event_time, location,
                int(max_capacity) if max_capacity else None,
                float(min_cgpa), float(min_attendance),
                is_paid, float(event_fee) if is_paid else 0,
                event_status,
                int(organiser_id) if organiser_id else None,
                event_id, admin_id
            )
            
            update(query, params)
            
            flash('Event updated successfully!', 'success')
            return redirect(url_for('admin.manage_events'))
        
        organisers = get_all("SELECT organiser_id, name FROM event_organisers WHERE is_active = TRUE")
        return render_template('admin/edit_event.html', event=event, organisers=organisers)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('admin.manage_events'))


@admin_bp.route('/event/<int:event_id>/delete', methods=['POST'])
@login_required('admin')
def delete_event(event_id):
    """Delete event"""
    admin_id = session.get('admin_id')
    
    try:
        event = get_one(
            "SELECT event_id FROM events WHERE event_id = %s AND admin_id = %s",
            (event_id, admin_id)
        )
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        delete("DELETE FROM events WHERE event_id = %s", (event_id,))
        
        return jsonify({'success': True, 'message': 'Event deleted successfully'})
    
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500


@admin_bp.route('/registrations')
@login_required('admin')
def view_registrations():
    """View all registrations"""
    
    try:
        query = """
            SELECT r.*, s.name as student_name, s.email as student_email, e.event_name
            FROM registrations r
            JOIN students s ON r.student_id = s.student_id
            JOIN events e ON r.event_id = e.event_id
            ORDER BY r.registration_date DESC
        """
        registrations = get_all(query)
        
        return render_template('admin/registrations.html',
                             registrations=registrations)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/students')
@login_required('admin')
def manage_students():
    """Manage students"""
    
    try:
        search = request.args.get('search', '')
        
        query = "SELECT * FROM students WHERE is_active = TRUE"
        params = []
        
        if search:
            query += " AND (name LIKE %s OR email LIKE %s OR enrollment_number LIKE %s)"
            search_param = f"%{search}%"
            params = [search_param, search_param, search_param]
        
        query += " ORDER BY created_at DESC"
        
        students = get_all(query, params) if params else get_all(query)
        
        return render_template('admin/students.html', students=students)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/analytics')
@login_required('admin')
def analytics():
    """View analytics"""
    
    try:
        # Event statistics
        event_stats = get_all("""
            SELECT e.event_name, COUNT(r.registration_id) as registrations,
                   SUM(CASE WHEN p.payment_status = 'completed' THEN p.amount ELSE 0 END) as revenue,
                   COUNT(DISTINCT CASE WHEN a.attendance_status = 'present' THEN a.student_id END) as attended
            FROM events e
            LEFT JOIN registrations r ON e.event_id = r.event_id
            LEFT JOIN payments p ON r.registration_id = p.registration_id
            LEFT JOIN attendance a ON r.registration_id = a.registration_id
            GROUP BY e.event_id
            ORDER BY e.event_date DESC
        """)
        
        # Payment statistics
        payment_stats = get_one("""
            SELECT 
                COUNT(*) as total_payments,
                SUM(amount) as total_revenue,
                COUNT(CASE WHEN payment_status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN payment_status = 'failed' THEN 1 END) as failed
            FROM payments
        """)
        
        return render_template('admin/analytics.html',
                             event_stats=event_stats,
                             payment_stats=payment_stats)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/organisers')
@login_required('admin')
def manage_organisers():
    """Manage event organisers"""
    
    try:
        organisers = get_all("""
            SELECT o.*, COUNT(e.event_id) as event_count
            FROM event_organisers o
            LEFT JOIN events e ON o.organiser_id = e.organiser_id
            GROUP BY o.organiser_id
            ORDER BY o.created_at DESC
        """)
        
        return render_template('admin/organisers.html', organisers=organisers)
    
    except Exception as e:
        print(f"Database error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/event/<int:event_id>')
@login_required('admin')
def view_event(event_id):
    """View event details (Admin)"""
    admin_id = session.get('admin_id')
    try:
        event = get_one("SELECT * FROM events WHERE event_id = %s", (event_id,))
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('admin.manage_events'))
        
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
        
        return render_template('admin/event_details.html', event=event, students=students)
    except Exception as e:
        print(f"Database error: {e}")
        flash(f'Error viewing event: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_events'))

@admin_bp.route('/certificates/<int:event_id>')
@login_required('admin')
def generate_certificates(event_id):
    """View certificate generation page for Admin"""
    try:
        event = get_one("SELECT * FROM events WHERE event_id = %s", (event_id,))
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('admin.manage_events'))
        
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
        
        return render_template('admin/generate_certificates.html', event=event, eligible_students=eligible_students)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_events'))

@admin_bp.route('/certificates/generate', methods=['POST'])
@login_required('admin')
def create_certificates():
    """Create certificates for selected students (Admin)"""
    try:
        data = request.get_json()
        event_id = data.get('event_id')
        student_ids = data.get('student_ids', [])
        
        from app.modules.certificate_module import get_certificate_generator
        import uuid
        
        event = get_one("SELECT event_id, event_name, event_date FROM events WHERE event_id = %s", (event_id,))
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        cert_generator = get_certificate_generator()
        count = 0
        for student_id in student_ids:
            student = get_one("SELECT name FROM students WHERE student_id = %s", (student_id,))
            reg = get_one("SELECT registration_id FROM registrations WHERE student_id = %s AND event_id = %s", (student_id, event_id))
            
            if not student or not reg:
                continue
            
            cert_number = f"CERT-{uuid.uuid4().hex[:8].upper()}"
            filepath = cert_generator.generate_certificate(student['name'], event['event_name'], event['event_date'], cert_number)
            
            if filepath:
                # Read binary for persistence
                pdf_binary = None
                try:
                    with open(filepath, 'rb') as f:
                        pdf_binary = f.read()
                except: pass
                
                insert("""
                    INSERT INTO certificates (student_id, event_id, registration_id, certificate_number, issue_date, certificate_file_path, certificate_pdf)
                    VALUES (%s, %s, %s, %s, NOW(), %s, %s)
                """, (student_id, event_id, reg['registration_id'], cert_number, filepath, pdf_binary))
                count += 1
        
        return jsonify({'success': True, 'message': f'Generated {count} certificates'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/attendance/<int:event_id>')
@login_required('admin')
def mark_attendance(event_id):
    """Mark attendance for event (Admin)"""
    try:
        event = get_one("SELECT * FROM events WHERE event_id = %s", (event_id,))
        if not event:
            flash('Event not found', 'danger')
            return redirect(url_for('admin.manage_events'))
        
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
        
        return render_template('admin/mark_attendance.html', event=event, students=students)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('admin.manage_events'))

@admin_bp.route('/attendance/save', methods=['POST'])
@login_required('admin')
def save_attendance():
    """Save attendance records (Admin)"""
    try:
        data = request.get_json()
        event_id = data.get('event_id')
        attendance_records = data.get('attendance', [])
        
        for record in attendance_records:
            reg_id = record.get('registration_id')
            status = record.get('status')
            
            existing = get_one("SELECT attendance_id FROM attendance WHERE registration_id = %s", (reg_id,))
            if existing:
                update("UPDATE attendance SET attendance_status = %s, check_in_time = NOW() WHERE registration_id = %s", (status, reg_id))
            else:
                insert("""
                    INSERT INTO attendance (registration_id, event_id, student_id, attendance_status, check_in_time)
                    SELECT r.registration_id, r.event_id, r.student_id, %s, NOW()
                    FROM registrations r WHERE r.registration_id = %s
                """, (status, reg_id))
        
        return jsonify({'success': True, 'message': 'Attendance saved'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/face-recognition/<int:event_id>', methods=['POST'])
@login_required('admin')
def face_recognition_attendance(event_id):
    """Mark attendance using face recognition (Admin)"""
    try:
        data = request.get_json(silent=True) or {}
        face_image_b64 = data.get('face_image')
        if not face_image_b64:
            return jsonify({'success': False, 'message': 'Face image required'}), 400
            
        from app.modules.face_recognition_module import get_face_manager
        import os, uuid
        fm = get_face_manager()
        
        students = get_all("""
            SELECT r.registration_id, s.student_id, s.name, s.face_encoding 
            FROM registrations r
            JOIN students s ON r.student_id = s.student_id
            WHERE r.event_id = %s
        """, (event_id,))
        
        best_match, img_bytes = fm.recognize_single_face(face_image_b64, students)
        if best_match:
            reg_id = best_match['registration_id']
            existing = get_one("SELECT attendance_id FROM attendance WHERE registration_id=%s", (reg_id,))
            if existing:
                update("UPDATE attendance SET attendance_status='present', check_in_time=NOW(), face_recognition_used=True, attendance_face_image=%s WHERE registration_id=%s", (img_bytes, reg_id))
            else:
                insert("INSERT INTO attendance (registration_id, event_id, student_id, attendance_status, check_in_time, face_recognition_used, attendance_face_image) VALUES (%s, %s, %s, 'present', NOW(), True, %s)", (reg_id, event_id, best_match['student_id'], img_bytes))
            
            return jsonify({'success': True, 'message': f"Matched: {best_match['name']}. Attendance marked Present."})
        else:
            return jsonify({'success': False, 'message': 'Match not found.'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

