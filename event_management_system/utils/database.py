"""
Database Connection Module
Supports SQLite (local) and PostgreSQL (Supabase)
"""
import sqlite3
import os
from flask import g, current_app
from contextlib import contextmanager

# Database file path (relative to the project root)
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database')
DB_PATH = os.path.join(DB_DIR, 'event_management.db')

USE_SQLITE = False  # Flag to use SQLite


def dict_factory(cursor, row):
    """Convert sqlite3 rows to dictionaries"""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


def get_db_connection():
    """Get database connection from Flask app context"""
    if 'db' not in g:
        try:
            if USE_SQLITE:
                os.makedirs(DB_DIR, exist_ok=True)
                g.db = sqlite3.connect(DB_PATH)
                g.db.row_factory = dict_factory
                g.db.execute("PRAGMA journal_mode=WAL")
                g.db.execute("PRAGMA foreign_keys=ON")
            else:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                g.db = psycopg2.connect(
                    host=current_app.config['POSTGRES_HOST'],
                    user=current_app.config['POSTGRES_USER'],
                    password=current_app.config['POSTGRES_PASSWORD'],
                    database=current_app.config['POSTGRES_DB'],
                    port=current_app.config['POSTGRES_PORT'],
                    cursor_factory=RealDictCursor
                )
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise
    return g.db


def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@contextmanager
def get_cursor():
    """Context manager for database cursor"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()


def _convert_query(query):
    """Convert PostgreSQL-style %s placeholders to SQLite ? placeholders"""
    if USE_SQLITE:
        # Replace %s with ? for SQLite
        return query.replace('%s', '?')
    return query


def init_db(app):
    """Initialize database with Flask app"""
    app.teardown_appcontext(close_db)

    if USE_SQLITE:
        # Create tables on startup for SQLite
        with app.app_context():
            _create_sqlite_tables()
    else:
        # Create tables on startup for PostgreSQL/Supabase
        with app.app_context():
            try:
                base_dir = os.path.dirname(os.path.dirname(__file__))
                schema_path = os.path.join(base_dir, 'database', 'schema_postgresql.sql')
                if os.path.exists(schema_path):
                    with open(schema_path, 'r') as f:
                        schema_sql = f.read()
                    
                    with get_cursor() as cursor:
                        # Split by semicolon to execute multiple statements if needed, 
                        # or just execute the whole block if your driver supports it.
                        # psycopg2 usually handles the whole block if it's multiple commands.
                        cursor.execute(schema_sql)
                    print("PostgreSQL database initialized/verified successfully!")
            except Exception as e:
                print(f"Warning: PostgreSQL initialization failed (might already exist): {e}")


def _create_sqlite_tables():
    """Create all tables in SQLite"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            cgpa REAL DEFAULT 0.00,
            attendance REAL DEFAULT 0.00,
            phone VARCHAR(15),
            enrollment_number VARCHAR(50) UNIQUE,
            department VARCHAR(100),
            semester INTEGER,
            profile_image BLOB,
            face_encoding BLOB,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Admin table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'super_admin',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Event Organisers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_organisers (
            organiser_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            department VARCHAR(100),
            contact_number VARCHAR(15),
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name VARCHAR(200) NOT NULL,
            description TEXT,
            event_date DATE NOT NULL,
            event_time TIME,
            location VARCHAR(200),
            max_capacity INTEGER,
            min_cgpa REAL DEFAULT 0.00,
            min_attendance REAL DEFAULT 0.00,
            is_paid BOOLEAN DEFAULT 0,
            event_fee REAL DEFAULT 0.00,
            organiser_id INTEGER REFERENCES event_organisers(organiser_id) ON DELETE SET NULL,
            admin_id INTEGER REFERENCES admin(admin_id) ON DELETE SET NULL,
            event_status VARCHAR(50) DEFAULT 'upcoming',
            banner_image BLOB,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Registrations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
            event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            registration_status VARCHAR(50) DEFAULT 'registered',
            is_eligible BOOLEAN DEFAULT 0,
            ineligibility_reason VARCHAR(255),
            registered_face_image VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, event_id)
        )
    """)

    # Payments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
            event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
            amount REAL NOT NULL,
            razorpay_order_id VARCHAR(100) UNIQUE,
            razorpay_payment_id VARCHAR(100) UNIQUE,
            razorpay_signature VARCHAR(255),
            payment_status VARCHAR(50) DEFAULT 'pending',
            payment_method VARCHAR(50) DEFAULT 'razorpay',
            transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
            event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
            registration_id INTEGER NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
            attendance_status VARCHAR(50) DEFAULT 'absent',
            check_in_time TIMESTAMP,
            check_out_time TIMESTAMP,
            face_recognition_used BOOLEAN DEFAULT 0,
            attendance_face_image VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, event_id)
        )
    """)

    # Certificates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            certificate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
            event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
            registration_id INTEGER NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
            certificate_number VARCHAR(100) UNIQUE NOT NULL,
            issue_date DATE,
            certificate_file_path VARCHAR(255),
            certificate_pdf BLOB,
            is_downloaded BOOLEAN DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            last_download_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed default admin user if not exists
    cursor.execute("SELECT COUNT(*) as cnt FROM admin WHERE email = ?", ('admin@campus.edu',))
    result = cursor.fetchone()
    if result['cnt'] == 0:
        import bcrypt
        password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
        cursor.execute(
            "INSERT INTO admin (name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?)",
            ('Super Admin', 'admin@campus.edu', password_hash, 'super_admin', 1)
        )

    conn.commit()
    print("SQLite database initialized successfully!")


def execute_query(query, params=None, fetchone=False, fetchall=False):
    """Execute a database query"""
    query = _convert_query(query)
    with get_cursor() as cursor:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetchone:
            return cursor.fetchone()
        elif fetchall:
            return cursor.fetchall()
        else:
            return cursor.rowcount


def get_one(query, params=None):
    """Get a single record"""
    return execute_query(query, params, fetchone=True)


def get_all(query, params=None):
    """Get all records"""
    return execute_query(query, params, fetchall=True)


def insert(query, params):
    """Insert a record"""
    query = _convert_query(query)
    with get_cursor() as cursor:
        cursor.execute(query, params)
        if USE_SQLITE:
            return cursor.lastrowid
        else:
            # Only try to fetch if the query uses a RETURNING clause
            if 'returning' in query.lower():
                result = cursor.fetchone()
                if result:
                    if isinstance(result, dict):
                        return list(result.values())[0]
                    return result[0] if isinstance(result, tuple) else result
        return None


def update(query, params):
    """Update records"""
    return execute_query(query, params)


def delete(query, params):
    """Delete records"""
    return execute_query(query, params)
