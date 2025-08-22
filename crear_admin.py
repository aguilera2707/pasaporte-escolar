from app import db, app
from app.models import Admin

def crear_admin():
    with app.app_context():
        # Verificar si ya existe
        existente = Admin.query.filter_by(usuario="admin").first()
        if existente:
            print("⚠️ El admin ya existe")
            return
        
        # Crear nuevo admin
        admin = Admin(
            usuario="admin",
            rol="admin"
        )
        admin.set_password("ModernoIMA2025@")  # aquí se encripta
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin creado con éxito")

if __name__ == "__main__":
    crear_admin()
