from flask_login import UserMixin
from app import db
from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash

# -------- FUNCIÓN DE HORA LOCAL --------
def hora_local_merida():
    return datetime.now(pytz.timezone('America/Merida')).replace(tzinfo=None)

# -------- MODELOS --------

class Familia(db.Model,UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    puntos = db.Column(db.Integer, default=0)
    qr_version = db.Column(db.Integer, default=1)

    def __repr__(self):
        return f'<Familia {self.nombre} – {self.puntos} puntos>'


class MovimientoPuntos(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familia.id'), nullable=False)
    cambio = db.Column(db.Integer, nullable=False)  # Positivo para sumar, negativo para restar
    motivo = db.Column(db.String(200))              # Ej: "Llegó tarde", "Asistió a evento"
    fecha = db.Column(db.DateTime, default=hora_local_merida, nullable=False)

    familia = db.relationship('Familia', backref=db.backref('movimientos', lazy=True))

    def __repr__(self):
        signo = '+' if self.cambio >= 0 else ''
        return f'<Movimiento {signo}{self.cambio} – {self.motivo}>'


class Transaccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familia.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # "suma" o "canje"
    puntos = db.Column(db.Integer, nullable=False)
    descripcion = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=hora_local_merida, nullable=False)

    familia = db.relationship('Familia', backref=db.backref('transacciones', lazy=True))

    def __repr__(self):
        return f'<Transacción {self.tipo} – {self.puntos}>'


class Admin(db.Model,UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    rol = db.Column(db.String(20), default='admin')  # 'admin' o 'supervisor'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verificar_password(self, password):
        return check_password_hash(self.password_hash, password)

    def es_supervisor(self):
        return self.rol == 'supervisor'

    def es_admin(self):
        return self.rol == 'admin'

    def __repr__(self):
        return f'<Admin {self.usuario} ({self.rol})>'


class EventoQR(db.Model):
    __tablename__ = 'evento_qr'
    id = db.Column(db.Integer, primary_key=True)
    nombre_evento = db.Column(db.String(100), nullable=False)
    puntos = db.Column(db.Integer, nullable=False)
    qr_filename = db.Column(db.String(200), nullable=True)
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    requiere_ubic = db.Column(db.Boolean, default=True)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_to = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<EventoQR {self.nombre_evento} – {self.puntos} puntos>'


class EventoQRRegistro(db.Model):
    __tablename__ = 'evento_qr_registro'
    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familia.id'), nullable=False)
    evento_id = db.Column(db.Integer, db.ForeignKey('evento_qr.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=hora_local_merida, nullable=False)

    familia = db.relationship('Familia', backref='eventos_escaneados')
    evento = db.relationship('EventoQR', backref='registros')

    def __repr__(self):
        return f'<Registro Evento {self.evento_id} – Familia {self.familia_id}>'


class Beneficio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.Text, nullable=False, unique=True)  # antes: String(100)
    puntos_requeridos = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<Beneficio {self.nombre} – {self.puntos_requeridos}>'


class LugarFrecuente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    latitud = db.Column(db.String(50), nullable=False)
    longitud = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Lugar {self.nombre}>'


class LogEntry(db.Model):
    __tablename__ = 'log_entries'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(pytz.timezone('America/Merida')).replace(tzinfo=None),
        nullable=False
    )
    user = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(32), nullable=False)
    action = db.Column(db.String(32), nullable=False)   # e.g. 'crear', 'editar', 'eliminar', 'login'
    entity = db.Column(db.String(32), nullable=False)   # e.g. 'Familia', 'EventoQR', 'Admin'
    details = db.Column(db.Text, nullable=True)         # Descripción detallada

    def __repr__(self):
        ts = self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        return f'<Log {ts} | {self.user} [{self.role}] {self.action} {self.entity}>'
