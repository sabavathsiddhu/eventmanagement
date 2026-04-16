-- Smart Campus Event Management System Database Schema
-- PostgreSQL version for Supabase

-- =============================================
-- STUDENTS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS students (
    student_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    cgpa DECIMAL(3, 2) DEFAULT 0.00,
    attendance DECIMAL(5, 2) DEFAULT 0.00,
    phone VARCHAR(15),
    enrollment_number VARCHAR(50) UNIQUE,
    department VARCHAR(100),
    semester INT,
    profile_image BYTEA,
    face_encoding BYTEA,
    face_image BYTEA,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_students_email ON students(email);
CREATE INDEX idx_students_enrollment ON students(enrollment_number);

-- =============================================
-- ADMIN TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS admin (
    admin_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'super_admin',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_admin_email ON admin(email);

-- =============================================
-- EVENT ORGANISERS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS event_organisers (
    organiser_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    department VARCHAR(100),
    contact_number VARCHAR(15),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_event_organisers_email ON event_organisers(email);

-- =============================================
-- EVENTS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS events (
    event_id SERIAL PRIMARY KEY,
    event_name VARCHAR(200) NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    event_time TIME,
    location VARCHAR(200),
    max_capacity INT,
    min_cgpa DECIMAL(3, 2) DEFAULT 0.00,
    min_attendance DECIMAL(5, 2) DEFAULT 0.00,
    is_paid BOOLEAN DEFAULT FALSE,
    event_fee DECIMAL(10, 2) DEFAULT 0.00,
    organiser_id INT REFERENCES event_organisers(organiser_id) ON DELETE SET NULL,
    admin_id INT REFERENCES admin(admin_id) ON DELETE SET NULL,
    event_status VARCHAR(50) DEFAULT 'upcoming',
    banner_image BYTEA,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_status ON events(event_status);
CREATE INDEX idx_events_organiser ON events(organiser_id);

-- =============================================
-- REGISTRATIONS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS registrations (
    registration_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    event_id INT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    registration_status VARCHAR(50) DEFAULT 'registered',
    is_eligible BOOLEAN DEFAULT FALSE,
    ineligibility_reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, event_id)
);

CREATE INDEX idx_registrations_student ON registrations(student_id);
CREATE INDEX idx_registrations_event ON registrations(event_id);
CREATE INDEX idx_registrations_status ON registrations(registration_status);

-- =============================================
-- PAYMENTS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS payments (
    payment_id SERIAL PRIMARY KEY,
    registration_id INT NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    event_id INT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    razorpay_order_id VARCHAR(100) UNIQUE,
    razorpay_payment_id VARCHAR(100) UNIQUE,
    razorpay_signature VARCHAR(255),
    payment_status VARCHAR(50) DEFAULT 'pending',
    payment_method VARCHAR(50) DEFAULT 'razorpay',
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payments_student ON payments(student_id);
CREATE INDEX idx_payments_event ON payments(event_id);
CREATE INDEX idx_payments_status ON payments(payment_status);
CREATE INDEX idx_payments_razorpay_id ON payments(razorpay_payment_id);

-- =============================================
-- ATTENDANCE TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    event_id INT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    registration_id INT NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
    attendance_status VARCHAR(50) DEFAULT 'absent',
    check_in_time TIMESTAMP,
    check_out_time TIMESTAMP,
    face_recognition_used BOOLEAN DEFAULT FALSE,
    attendance_face_image BYTEA,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, event_id)
);

CREATE INDEX idx_attendance_event ON attendance(event_id);
CREATE INDEX idx_attendance_status ON attendance(attendance_status);

-- =============================================
-- CERTIFICATES TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS certificates (
    certificate_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    event_id INT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    registration_id INT NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
    certificate_number VARCHAR(100) UNIQUE NOT NULL,
    issue_date DATE,
    certificate_file_path VARCHAR(255),
    certificate_pdf BYTEA,
    is_downloaded BOOLEAN DEFAULT FALSE,
    download_count INT DEFAULT 0,
    last_download_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_certificates_student ON certificates(student_id);
CREATE INDEX idx_certificates_event ON certificates(event_id);
CREATE INDEX idx_certificates_number ON certificates(certificate_number);

-- =============================================
-- INSERT DEFAULT ADMIN USER
-- =============================================
-- Password: admin123
-- This is a bcrypt hash example - update with your actual password hash
INSERT INTO admin (name, email, password_hash, role, is_active) 
VALUES (
    'Super Admin', 
    'admin@campus.edu', 
    '$2b$12$zXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', 
    'super_admin', 
    TRUE
)
ON CONFLICT (email) DO NOTHING;
