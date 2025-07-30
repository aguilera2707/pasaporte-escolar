from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from datetime import timedelta
import pytz
from datetime import datetime

app = Flask(__name__)

# Configuración general
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cuponera.db'
app.config['SECRET_KEY'] = 'clave-super-secreta-123'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.permanent_session_lifetime = timedelta(minutes=30)

# Configuración de correo
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pasaporte-no-reply@cela.edu.mx'
app.config['MAIL_PASSWORD'] = 'lrznarqzdskamqxm'  # ← contraseña de aplicación
app.config['MAIL_DEFAULT_SENDER'] = 'pasaporte-no-reply@cela.edu.mx'

# Inicialización de extensiones
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)

# Mantener sesión activa
@app.before_request
def mantener_sesion_activa():
    session.permanent = True

# Filtro para hora local
@app.template_filter('localtime')
def localtime_filter(utc_dt):
    if utc_dt is None:
        return ''
    local_tz = pytz.timezone('America/Mexico_City')
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(local_tz).strftime('%Y-%m-%d %H:%M')

# Importaciones finales
from app import routes, models
