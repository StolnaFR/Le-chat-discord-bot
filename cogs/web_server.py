from flask import Flask, render_template
from flask_socketio import SocketIO

def create_app_and_server(log_handler):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    @app.route('/')
    def index():
        return render_template('logs.html', logs=log_handler.logs_list[-100:])  # Derniers 100 logs
    
    @socketio.on('connect')
    def handle_connect():
        print("[WEB] Client connecté au panel")
        # Envoyer les 50 derniers logs
        for log in log_handler.logs_list[-50:]:
            socketio.emit('new_log', {'message': log})
    
    return app, socketio
