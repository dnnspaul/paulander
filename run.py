#!/usr/bin/env python3
"""
Paulander startup script
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import app

if __name__ == '__main__':
    # Development server
    app.run(host='0.0.0.0', port=5000, debug=os.getenv('FLASK_ENV') == 'development')