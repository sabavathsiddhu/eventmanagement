import os
import sys

# Add the event_management_system directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'event_management_system'))

from app_factory import create_app

# Render needs an initialized app instance to serve as the WSGI application
app = create_app('production')

if __name__ == '__main__':
    # Add this block to run the server locally
    print("Starting server on http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)
