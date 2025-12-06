from flask import Flask
import os

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    app.config['EXPORT_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'exports')
    app.config['TEMPLATES_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Templates')
    app.config['DATA_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

    # Database configuration
    # SQLite for local development, can be swapped for PostgreSQL/MySQL on AWS
    # Set DATABASE_URL environment variable for production (e.g., postgresql://user:pass@host/db)
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        # Local SQLite database
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'commissions.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Ensure folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)

    # Initialize database
    from app.models import db
    db.init_app(app)

    with app.app_context():
        db.create_all()

    from app.routes import main
    app.register_blueprint(main)

    return app
