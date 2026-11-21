import os
from flask import Flask
from dotenv import load_dotenv
from .db import init_db

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

    from .routes import main
    app.register_blueprint(main)
    init_db()
    return app
