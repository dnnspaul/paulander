from flask import Blueprint, render_template

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@web_bp.route('/config')
def config():
    """Configuration page"""
    return render_template('config.html')