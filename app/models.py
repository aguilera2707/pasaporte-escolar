from app import db
from datetime import datetime


class Familia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    puntos = db.Column(db.Integer, default=0)

def __repr__(self):
    return f'<Familia {self.nombre} - {self.puntos} puntos>'
    
class MovimientoPuntos(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familia.id'), nullable=False)
    cambio = db.Column(db.Integer, nullable=False)  # Positivo para sumar, negativo para restar
    motivo = db.Column(db.String(200))  # Ej: "Llegó tarde", "Asistió a evento"
    fecha = db.Column(db.DateTime, server_default=db.func.now())

familia = db.relationship('Familia', backref=db.backref('movimientos', lazy=True))

def __repr__(self):
    return f'<Movimiento {self.cambio} puntos - {self.motivo}>'
    
class Transaccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familia.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # "suma" o "canje"
    puntos = db.Column(db.Integer, nullable=False)
    descripcion = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    familia = db.relationship('Familia', backref=db.backref('transacciones', lazy=True))

def __repr__(self):
    return f'<Transacción {self.tipo} - {self.puntos} puntos>'

    
from werkzeug.security import generate_password_hash, check_password_hash

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verificar_password(self, password):
        return check_password_hash(self.password_hash, password)
    
        

class EventoQRRegistro(db.Model):
    __tablename__ = 'evento_qr_registro'
    id = db.Column(db.Integer, primary_key=True)
    familia_id = db.Column(db.Integer, db.ForeignKey('familia.id'), nullable=False)
    evento_id = db.Column(db.Integer, db.ForeignKey('evento_qr.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    familia = db.relationship('Familia', backref='eventos_escaneados')
    evento = db.relationship('EventoQR', backref='registros')
    
class Beneficio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    puntos_requeridos = db.Column(db.Integer, nullable=False)
    
class EventoQR(db.Model):
    __tablename__ = 'evento_qr'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    nombre_evento = db.Column(db.String(100), nullable=False)
    puntos = db.Column(db.Integer, nullable=False)
    qr_filename = db.Column(db.String(200), nullable=True)  # ← CAMBIAR a True
    latitud = db.Column(db.Float)  # ← Nuevo campo
    longitud = db.Column(db.Float)  # ← Nuevo campo
    
class LugarFrecuente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    latitud = db.Column(db.String(50), nullable=False)
    longitud = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Lugar {self.nombre}>'  