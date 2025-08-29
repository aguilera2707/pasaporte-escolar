from flask_mail import Mail
from flask_login import LoginManager

mail = Mail()
login_manager = LoginManager()
login_manager.login_view = "login_familia"  # aquí debe coincidir con tu ruta de login