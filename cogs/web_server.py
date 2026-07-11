import os
from flask import Flask, render_template
from flask_socketio import SocketIO

# Chemin absolu vers le dossier templates à la racine du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

def create_app_and_server(log_handler):
    app = Flask(__name__, template_folder=TEMPLATES_DIR)
    app.config['SECRET_KEY'] = 'secret!'
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    @app.route('/')
    def index():
        return render_template('logs.html', logs=log_handler.logs_list[-100:])
    
    @socketio.on('connect')
    def handle_connect():
        print("[WEB] Client connecté au panel")
        # Envoyer les 50 derniers logs
        for log in log_handler.logs_list[-50:]:
            socketio.emit('new_log', {'message': log})
    
    return app, socketio
