from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from datetime import timedelta
import pytz
from datetime import datetime
import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.extensions import login_manager  # mantiene tu login_view


app = Flask(__name__)

# =========================
# Configuración de Base de Datos
# =========================
# Usaremos siempre DATABASE_URL. En local, .env: sqlite:///instance/cuponera.db
# En Render: sqlite:////var/data/cuponera.db
uri = os.getenv("DATABASE_URL", "sqlite:///instance/cuponera.db")

# Si aún existiera una URL vieja de Postgres en algún entorno, normalizamos:
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

# Si fuera Postgres (no lo usaremos ya), agrega sslmode
if uri.startswith(("postgresql://", "postgresql+psycopg2://")):
    parsed = urlparse(uri)
    q = dict(parse_qsl(parsed.query))
    if "sslmode" not in q:
        q["sslmode"] = "require"
        uri = urlunparse(parsed._replace(query=urlencode(q)))

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Pool solo para Postgres (compatibilidad) ---
if uri.startswith(("postgresql://", "postgresql+psycopg2://")):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
        "connect_args": {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    }

db = SQLAlchemy(app)

# --- PRAGMAs y ajustes solo para SQLite ---
if uri.startswith("sqlite:///") or uri.startswith("sqlite:////"):
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.close()
        except Exception:
            pass

migrate = Migrate(app, db)


login_manager.init_app(app)

from app.models import Familia, Admin  # modelos existentes

@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith("familia-"):
        return Familia.query.get(int(user_id.split("-")[1]))
    elif user_id.startswith("admin-"):
        return Admin.query.get(int(user_id.split("-")[1]))
    return None

# =========================
# Configuración general
# =========================
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clave-super-secreta-123')

# 🔑 Cambiado de 30 min a 3 horas
app.permanent_session_lifetime = timedelta(hours=5)

app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB

# =========================
# Correo
# =========================
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'pasaporte-no-reply@cela.edu.mx')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'grgiuhmaoobcgeap')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'pasaporte-no-reply@cela.edu.mx')
app.config['MAIL_MAX_EMAILS'] = 50
app.config['MAIL_DEBUG'] = True

# Asegurar modalidad única
if app.config['MAIL_USE_SSL']:
    app.config['MAIL_USE_TLS'] = False
elif app.config['MAIL_USE_TLS']:
    app.config['MAIL_USE_SSL'] = False
else:
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

login_manager.init_app(app)


# =========================
# Mantener sesión activa
# =========================
@app.before_request
def mantener_sesion_activa():
    session.permanent = True  # 🔑 asegura que todas las sesiones duren 3h


# =========================
# Filtro para hora local
# =========================
@app.template_filter('localtime')
def localtime_filter(utc_dt):
    if utc_dt is None:
        return ''
    local_tz = pytz.timezone('America/Mexico_City')
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')

from app import routes, models
