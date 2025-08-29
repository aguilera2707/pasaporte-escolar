from app import app, db
from app.models import Admin

def reset_admin(usuario="admin", password="Test1234", rol="admin"):
    with app.app_context():
        # Borrar todos los admins
        db.session.query(Admin).delete()
        db.session.commit()
        print("❌ Todos los admins borrados")

        # Crear nuevo admin
        nuevo = Admin(usuario=usuario, rol=rol)
        nuevo.set_password(password)
        db.session.add(nuevo)
        db.session.commit()
        print(f"✅ Admin recreado: usuario={usuario} / contraseña={password} / rol={rol}")

if __name__ == "__main__":
    # Aquí defines las credenciales que quieras
    reset_admin(usuario="admin", password="ModernoIMA2025@", rol="admin")
