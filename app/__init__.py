from flask import Flask, session  # ⬅️ ¡Agrega 'session' aquí!
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import timedelta

app = Flask(__name__)

# Configuración de la base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cuponera.db'
app.config['SECRET_KEY'] = 'clave-super-secreta-123'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Tiempo máximo de sesión inactiva
app.permanent_session_lifetime = timedelta(minutes=5)

# Inicialización de extensiones
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Forzar que las sesiones sean permanentes
@app.before_request
def mantener_sesion_activa():
    session.permanent = True

from app import routes, models

import pytz
from datetime import datetime

@app.template_filter('localtime')
def localtime_filter(utc_dt):
    if utc_dt is None:
        return ''
    # Cambia a tu zona horaria local si vives en otra región
    local_tz = pytz.timezone('America/Mexico_City')
    # Si utc_dt no tiene tzinfo, asígnale UTC
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')