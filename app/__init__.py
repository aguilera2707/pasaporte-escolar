from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from datetime import timedelta
import pytz
from datetime import datetime
import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from app.extensions import login_manager


app = Flask(__name__)

# =========================
# Configuración de Base de Datos
# =========================
# Usa DATABASE_URL si existe (Render o local con PostgreSQL),
# de lo contrario usa SQLite como fallback
uri = os.getenv("DATABASE_URL", "sqlite:///cuponera.db")

# Render a veces manda "postgres://" y SQLAlchemy espera "postgresql://"
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

# Asegurar sslmode=require para Postgres en Render si no viene en la URL
if uri.startswith("postgresql://") or uri.startswith("postgresql+psycopg2://"):
    parsed = urlparse(uri)
    q = dict(parse_qsl(parsed.query))
    if "sslmode" not in q:
        q["sslmode"] = "require"
        uri = urlunparse(parsed._replace(query=urlencode(q)))

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- ✅ POOL DE CONEXIONES (solo para Postgres) ---
if uri.startswith("postgresql://") or uri.startswith("postgresql+psycopg2://"):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": 5,          # conexiones persistentes
        "max_overflow": 10,      # conexiones extra en picos
        "pool_timeout": 30,      # segundos de espera por una conexión libre
        "pool_recycle": 1800,    # reciclar cada 30min (evita expiraciones)
        "pool_pre_ping": True,   # verifica conexión viva antes de usarla
        # Opcional: keepalives para conexiones largas (psycopg2)
        "connect_args": {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
        },
    }
# --- fin pool ---

# =========================
# Configuración general
# =========================
app.config['SECRET_KEY'] = 'clave-super-secreta-123'
app.permanent_session_lifetime = timedelta(minutes=30)

app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB

# =========================
# Configuración de correo
# =========================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pasaporte-no-reply@cela.edu.mx'
app.config['MAIL_PASSWORD'] = 'grgiuhmaoobcgeap'  # contraseña de aplicación
app.config['MAIL_DEFAULT_SENDER'] = 'pasaporte-no-reply@cela.edu.mx'

# =========================
# Inicialización de extensiones
# =========================
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)
login_manager.init_app(app)

from app.models import Familia, Admin

@login_manager.user_loader
def load_user(user_id):
    # Flask-Login necesita devolver el usuario autenticado
    return Familia.query.get(int(user_id)) or Admin.query.get(int(user_id))

# =========================
# Mantener sesión activa
# =========================
@app.before_request
def mantener_sesion_activa():
    session.permanent = True

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

# =========================
# Importaciones finales
# =========================
from app import routes, models
