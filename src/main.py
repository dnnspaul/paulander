import os
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from src.routes.api import api_bp
from src.routes.web import web_bp
from src.services.scheduler import SchedulerService

load_dotenv()

app = Flask(__name__, static_folder='../static', template_folder='../templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

CORS(app)

app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(web_bp)

scheduler = SchedulerService()
scheduler.start()  # Start scheduler immediately when app loads

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.getenv('FLASK_ENV') == 'development')