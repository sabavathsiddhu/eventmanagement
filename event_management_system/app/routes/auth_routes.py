"""
Authentication Routes Module
"""
import time
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.auth import hash_password, verify_password, validate_email, validate_password_strength, login_required
from utils.validation import validate_student_registration
from utils.database import get_one, insert, update

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Universal login page"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user_type = request.form.get('user_type', 'student')
        
        if not email or not password:
            flash('Email and password are required', 'danger')
            return render_template('auth/login.html')
        
        try:
            # Check student login
            if user_type == 'student':
                query = """
                    SELECT student_id, name, email, password_hash 
                    FROM students 
                    WHERE email = %s AND is_active = TRUE
                """
                user = get_one(query, (email,))
                
                if user and verify_password(password, user['password_hash']):
                    session['student_id'] = user['student_id']
                    session['user_type'] = 'student'
                    session['user_name'] = user['name']
                    session['role'] = 'student'
                    session['last_activity'] = time.time()
                    flash(f'Welcome {user["name"]}!', 'success')
                    return redirect(url_for('student.dashboard'))
                else:
                    flash('Invalid email or password', 'danger')
            
            # Check admin login
            elif user_type == 'admin':
                query = """
                    SELECT admin_id, name, email, password_hash, role 
                    FROM admin 
                    WHERE email = %s AND is_active = TRUE
                """
                user = get_one(query, (email,))
                
                if user and verify_password(password, user['password_hash']):
                    session['admin_id'] = user['admin_id']
                    session['user_type'] = 'admin'
                    session['user_name'] = user['name']
                    session['role'] = user['role']
                    session['last_activity'] = time.time()
                    flash(f'Welcome Admin {user["name"]}!', 'success')
                    return redirect(url_for('admin.dashboard'))
                else:
                    flash('Invalid email or password', 'danger')
            
            # Check organiser login
            elif user_type == 'organiser':
                query = """
                    SELECT organiser_id, name, email, password_hash 
                    FROM event_organisers 
                    WHERE email = %s AND is_active = TRUE
                """
                user = get_one(query, (email,))
                
                if user and verify_password(password, user['password_hash']):
                    session['organiser_id'] = user['organiser_id']
                    session['user_type'] = 'organiser'
                    session['user_name'] = user['name']
                    session['role'] = 'organiser'
                    session['last_activity'] = time.time()
                    flash(f'Welcome {user["name"]}!', 'success')
                    return redirect(url_for('organiser.dashboard'))
                else:
                    flash('Invalid email or password', 'danger')
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Database error: {e}", flush=True)
            flash(f'Login Error: {str(e)}', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/register/student', methods=['GET', 'POST'])
def register_student():
    """Student registration"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        cgpa = request.form.get('cgpa', '0')
        attendance = request.form.get('attendance', '0')
        enrollment_number = request.form.get('enrollment_number', '').strip()
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # Validation
        data = {
            'name': name,
            'email': email,
            'password': password,
            'cgpa': cgpa,
            'attendance': attendance
        }
        
        errors = validate_student_registration(data)
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if not validate_email(email):
            errors.append('Invalid email format')
        
        if not enrollment_number:
            errors.append('Enrollment number is required')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register_student.html')
        
        try:
            # Check if email already exists
            existing = get_one("SELECT email FROM students WHERE email = %s", (email,))
            if existing:
                flash('Email already registered', 'danger')
                return render_template('auth/register_student.html')
            
            # Get face data
            face_image_b64 = request.form.get('face_image')
            
            # Basic validation
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return render_template('auth/register_student.html')
                
            if not face_image_b64:
                flash('Face capture is required for registration', 'danger')
                return render_template('auth/register_student.html')

            try:
                # Hash password
                password_hash = hash_password(password)
                
                # 1. First, create a temporary unique ID for the student to save their face
                import uuid
                temp_student_id = f"temp_{uuid.uuid4().hex[:8]}"
                
                # 2. Process the face image to get encoding
                from app.modules.face_recognition_module import get_face_manager
                import pickle, os
                fm = get_face_manager()
                face_encoding, face_img_filename = fm.process_base64_face(temp_student_id, face_image_b64)
                
                if face_encoding is None:
                    flash('Could not detect a face in the photo. Please try again with better lighting.', 'danger')
                    return render_template('auth/register_student.html')

                # Prepare binary data for database persistence
                import base64
                if ',' in face_image_b64:
                    face_image_b64 = face_image_b64.split(',')[1]
                face_image_binary = base64.b64decode(face_image_b64)
                
                # We also want to store the binary of the pickle for persistence
                pickle_binary = pickle.dumps({'student_id': temp_student_id, 'encoding': face_encoding})

                # 3. Insert student into database
                query = """
                    INSERT INTO students (name, email, password_hash, cgpa, attendance, 
                                       enrollment_number, department, phone, face_encoding, face_image)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                params = (name, email, password_hash, float(cgpa), float(attendance), 
                         enrollment_number, department, phone, pickle_binary, face_image_binary)
                
                student_id = insert(query, params)
                
                # Update the ID in the pickle for future consistency if needed
                new_pickle = pickle.dumps({'student_id': student_id, 'encoding': face_encoding})
                update("UPDATE students SET face_encoding = %s WHERE student_id = %s", (new_pickle, student_id))

                flash('Registration successful! You can now log in.', 'success')
                return redirect(url_for('auth.login'))
            
            except Exception as e:
                print(f"Database error: {e}")
                flash(f'Registration Error: {str(e)}', 'danger')
        
        except Exception as e:
            print(f"Database error: {e}")
            flash(f'Registration Error: {str(e)}', 'danger')
    
    return render_template('auth/register_student.html')


@auth_bp.route('/register/organiser', methods=['GET', 'POST'])
@login_required('admin')
def register_organiser():
    """Event organiser registration (by admin only)"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        department = request.form.get('department', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        
        # Validation
        if not name or len(name) < 2:
            flash('Name must be at least 2 characters long', 'danger')
            return render_template('auth/register_organiser.html')
        
        if not validate_email(email):
            flash('Invalid email format', 'danger')
            return render_template('auth/register_organiser.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long', 'danger')
            return render_template('auth/register_organiser.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/register_organiser.html')
        
        try:
            # Check if email already exists
            existing = get_one("SELECT email FROM event_organisers WHERE email = %s", (email,))
            if existing:
                flash('Email already registered', 'danger')
                return render_template('auth/register_organiser.html')
            
            # Hash password
            password_hash = hash_password(password)
            
            # Insert organiser
            query = """
                INSERT INTO event_organisers 
                (name, email, password_hash, department, contact_number) 
                VALUES (%s, %s, %s, %s, %s)
            """
            params = (name, email, password_hash, department, contact_number)
            
            insert(query, params)
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            print(f"Database error: {e}")
            flash(f'Registration Error: {str(e)}', 'danger')
    
    return render_template('auth/register_organiser.html')
