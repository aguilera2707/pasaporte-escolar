# crear_db.py
from app import app, db
from app.models import *  # 👈 IMPORTANTE: registra todos los modelos
from sqlalchemy import inspect

with app.app_context():
    db.drop_all()
    db.create_all()

    # Verificación: listar tablas creadas
    insp = inspect(db.engine)
    print("✅ Tablas creadas:", insp.get_table_names())