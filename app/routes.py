from flask import (
    Flask, jsonify, request, render_template,
    redirect, url_for, session, flash, Response, send_file
)
from functools import wraps
from datetime import datetime, timedelta
from io import BytesIO, TextIOWrapper
import os
import csv
import unicodedata
import qrcode
from werkzeug.security import generate_password_hash
from app import app, db
from app.models import (
    Familia, MovimientoPuntos, Transaccion,
    Admin, Beneficio, LugarFrecuente,
    EventoQR, EventoQRRegistro
)

def login_requerido_admin(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorada

@app.route("/admin")
@login_requerido_admin
def panel_admin():
    rol = session.get('rol')
    print(f"[DEBUG] Rol en sesión: {rol}")

    if "admin_id" not in session:
        return redirect(url_for("login"))

    eventos = EventoQR.query.order_by(EventoQR.id.desc()).all()
    familias = Familia.query.all()
    ultimo_evento = eventos[0] if eventos else None
    otros_eventos = eventos[1:] if len(eventos) > 1 else []

    return render_template(
        "admin.html",
        eventos=eventos,
        familias=familias,
        ultimo_evento=ultimo_evento,
        otros_eventos=otros_eventos,
        rol=rol  # IMPORTANTE: pasar el rol
    )

from flask import session, redirect, url_for, flash

# Decorador para roles
def requiere_rol(*roles_permitidos):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'admin_id' not in session:
                return redirect(url_for('login'))
            rol = session.get('rol')
            if rol not in roles_permitidos:
                flash("No tienes permiso para acceder a esta sección", "error")
                return redirect(url_for('panel_admin'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        admin = Admin.query.filter_by(usuario=usuario).first()
        if admin and admin.verificar_password(password):
            session["admin_id"] = admin.id
            session["admin"] = admin.usuario
            session["rol"] = admin.rol
            session["nombre_usuario"] = admin.usuario  # <-- Guardamos el nombre del admin aquí
            print(f"[DEBUG] Login exitoso: {admin.usuario} con rol {admin.rol}")
            entry = LogEntry(
                user=admin.usuario,
                role=admin.rol,
                action="inicio sesión",
                entity="Admin",
                details="Inicio de sesión exitoso"
            )
            db.session.add(entry)
            db.session.commit()
            return redirect(url_for("panel_admin"))
        else:
            flash("Credenciales inválidas para administrador", "error")
            print("[DEBUG] Login fallido o usuario no encontrado")
            return render_template("login_unificado.html", active_tab="admin")

    # Método GET
    return render_template("login_unificado.html", active_tab="admin")


@app.route("/logout")
def logout():
    nombre = session.get("nombre_usuario", "<desconocido>")
    rol = session.get("rol", "Admin")
    session.clear()
    # --- Log de cierre de sesión ---
    entry = LogEntry(
        user=nombre,
        role=rol,
        action="cierre sesión",
        entity="Admin",
        details="El usuario cerró sesión"
    )
    db.session.add(entry)
    db.session.commit()
    return redirect(url_for("login"))


def quitar_acentos(cadena):
    return ''.join(
        c for c in unicodedata.normalize('NFD', cadena)
        if unicodedata.category(c) != 'Mn'
    )


@app.route('/lista_familias', methods=['GET', 'POST'])
def lista_familias():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo = request.form.get('correo')
        password = request.form.get('password')

        if nombre and correo and password:
            # Normalizar el nombre
            nombre_normalizado = quitar_acentos(nombre.strip().lower().replace(" ", ""))
            familias = Familia.query.all()
            for f in familias:
                nombre_existente = quitar_acentos(f.nombre.strip().lower().replace(" ", ""))
                if nombre_existente == nombre_normalizado:
                    flash("Ya existe una familia con ese nombre", "error")
                    return redirect(url_for('lista_familias'))

            # Validar duplicado por correo
            if Familia.query.filter_by(correo=correo).first():
                flash("Ese correo ya está registrado", "error")
                return redirect(url_for('lista_familias'))

            # Crear nueva familia
            nueva_familia = Familia(nombre=nombre, correo=correo, password=password)
            db.session.add(nueva_familia)
            db.session.commit()
            
            

            # Generar QR
            qr_url = url_for('ver_familia', familia_id=nueva_familia.id, _external=True)
            qr = qrcode.make(qr_url)
            qr_folder = os.path.join('app', 'static', 'qr')
            os.makedirs(qr_folder, exist_ok=True)
            qr_path = os.path.join(qr_folder, f'familia_{nueva_familia.id}.png')
            qr.save(qr_path)
            
                    # ➕ Familia creada
            entry = LogEntry(
                timestamp=datetime.utcnow(),
                user=session.get("nombre_usuario"),
                role=session.get("rol"),
                action="crear",
                entity="Familia",
                details=f"id={nueva_familia.id}, nombre={nueva_familia.nombre}"
            )
            db.session.add(entry)
            db.session.commit()

            flash("Familia registrada exitosamente", "success")
            return redirect(url_for('lista_familias'))

    # Búsqueda
    termino_busqueda = request.args.get('buscar', '').strip()
    if termino_busqueda:
        termino_normalizado = quitar_acentos(termino_busqueda.lower())
        familias = Familia.query.all()
        familias = [
            f for f in familias
            if termino_normalizado in quitar_acentos(f.nombre.lower())
        ]
    else:
        familias = Familia.query.all()

    return render_template('lista_familias.html', familias=familias, buscar=termino_busqueda)

@app.route('/')
def index():
    return render_template('login_unificado.html')

from app.routes import quitar_acentos  # asegúrate de importar esta función si no está en el mismo archivo

@app.route("/familias", methods=["POST"])
def crear_familia():
    import qrcode
    import os

    data = request.get_json()
    nombre = data["nombre"]
    correo = data["correo"]
    password = data["password"]

    # ✅ Validar duplicado por nombre (ignorando mayúsculas, espacios y acentos)
    nombre_normalizado = quitar_acentos(nombre.strip().lower().replace(" ", ""))
    familias = Familia.query.all()
    for familia in familias:
        nombre_existente = quitar_acentos(familia.nombre.strip().lower().replace(" ", ""))
        if nombre_existente == nombre_normalizado:
            return jsonify({"error": "Ya existe una familia con ese nombre"}), 400

    # ✅ Validar duplicado por correo
    if Familia.query.filter_by(correo=correo).first():
        return jsonify({"error": "Ese correo ya está registrado"}), 400

    # ✅ Crear nueva familia
    nueva_familia = Familia(nombre=nombre, correo=correo, password=password)
    db.session.add(nueva_familia)
    db.session.commit()

    # ✅ Generar código QR una sola vez
    qr_url = url_for('ver_familia', familia_id=nueva_familia.id, _external=True)
    qr = qrcode.make(qr_url)
    qr_path = os.path.join('app', 'static', 'qr', f'familia_{nueva_familia.id}.png')
    qr.save(qr_path)

    return jsonify({"mensaje": "Familia registrada exitosamente"}), 201



@app.route("/sumar_puntos", methods=["POST"])
def sumar_puntos():
    data = request.get_json()
    familia_id = data.get("familia_id")
    puntos = data.get("puntos")
    motivo = data.get("motivo", "Puntos sumados")

    familia = Familia.query.get(familia_id)
    if not familia:
        return jsonify({"error": "Familia no encontrada"}), 404

    familia.puntos += puntos
    movimiento = MovimientoPuntos(familia_id=familia.id, cambio=puntos, motivo=motivo)
    db.session.add(movimiento)
    db.session.commit()

    return jsonify({"mensaje": "Puntos sumados correctamente", "puntos_actuales": familia.puntos})

@app.route("/restar_puntos", methods=["POST"])
@requiere_rol('admin', 'supervisor')
def restar_puntos():
    data = request.get_json()
    familia_id = data.get("familia_id")
    puntos = data.get("puntos")
    motivo = data.get("motivo", "Puntos restados")

    familia = Familia.query.get(familia_id)
    if not familia:
        return jsonify({"error": "Familia no encontrada"}), 404

    if familia.puntos < puntos:
        return jsonify({"error": "No hay suficientes puntos"}), 400

    familia.puntos -= puntos
    movimiento = MovimientoPuntos(familia_id=familia.id, cambio=-puntos, motivo=motivo)
    db.session.add(movimiento)
    db.session.commit()

    return jsonify({"mensaje": "Puntos restados correctamente", "puntos_actuales": familia.puntos})

@app.route("/historial/<int:familia_id>")
def historial(familia_id):
    movimientos = MovimientoPuntos.query.filter_by(familia_id=familia_id).order_by(MovimientoPuntos.fecha.desc()).all()
    datos = [
        {"cambio": m.cambio, "motivo": m.motivo, "fecha": m.fecha.strftime("%Y-%m-%d %H:%M")}
        for m in movimientos
    ]
    return jsonify(datos)


@app.route('/familias/<int:familia_id>/puntos', methods=['POST'])
def agregar_puntos(familia_id):
    data = request.get_json()

    if not data or 'puntos' not in data:
        return jsonify({'error': 'Se requiere el campo "puntos"'}), 400

    familia = Familia.query.get(familia_id)

    if not familia:
        return jsonify({'error': 'Familia no encontrada'}), 404

    try:
        puntos_a_agregar = int(data['puntos'])
        familia.puntos += puntos_a_agregar
        db.session.commit()
        return jsonify({'mensaje': f'Se han agregado {puntos_a_agregar} puntos a {familia.nombre}', 'puntos_totales': familia.puntos}), 200
    except ValueError:
        return jsonify({'error': 'El valor de "puntos" debe ser un número entero'}), 400
    
@app.route('/familias/<int:familia_id>/canjear', methods=['POST'])
def canjear_puntos(familia_id):
    data = request.get_json()

    if not data or 'puntos' not in data:
        return jsonify({'error': 'Se requiere el campo "puntos"'}), 400

    familia = Familia.query.get(familia_id)

    if not familia:
        return jsonify({'error': 'Familia no encontrada'}), 404

    try:
        puntos_a_restar = int(data['puntos'])

        if puntos_a_restar <= 0:
            return jsonify({'error': 'El número de puntos a canjear debe ser positivo'}), 400

        if familia.puntos < puntos_a_restar:
            return jsonify({'error': 'La familia no tiene suficientes puntos'}), 400

        familia.puntos -= puntos_a_restar
        db.session.commit()
        return jsonify({'mensaje': f'Se han canjeado {puntos_a_restar} puntos de {familia.nombre}', 'puntos_restantes': familia.puntos}), 200
    except ValueError:
        return jsonify({'error': 'El valor de "puntos" debe ser un número entero'}), 400
    
from datetime import datetime
import pytz

@app.route('/transaccion', methods=['POST'])
def registrar_transaccion():
    data = request.get_json()
    familia_id = data.get('familia_id')
    puntos = int(data.get('puntos'))
    tipo = data.get('tipo')
    descripcion = data.get('descripcion', '')

    familia = Familia.query.get(familia_id)
    if not familia:
        return jsonify({'error': 'Familia no encontrada'}), 404

    if tipo == 'suma':
        familia.puntos += puntos
    elif tipo == 'canje':
        if familia.puntos < puntos:
            return jsonify({'error': 'Puntos insuficientes para canjear'}), 400
        familia.puntos -= puntos
    else:
        return jsonify({'error': 'Tipo de transacción inválido'}), 400

    # --- AGREGAR REGISTRO DE HISTORIAL ---
    hora_mexico = datetime.now(pytz.timezone('America/Mexico_City')).replace(tzinfo=None)
    nueva_transaccion = Transaccion(
    familia_id=familia_id,
    tipo=tipo,
    puntos=puntos if tipo == 'suma' else -puntos,
    descripcion=descripcion,
    fecha=hora_mexico
)

    db.session.add(nueva_transaccion)

    db.session.commit()
    return jsonify({'mensaje': 'Transacción registrada con éxito', 'puntos_restantes': familia.puntos}), 200



    
@app.route('/familia/<int:familia_id>/historial', methods=['GET'])
def historial_transacciones(familia_id):
    familia = Familia.query.get(familia_id)
    if not familia:
        return jsonify({'error': 'Familia no encontrada'}), 404

    transacciones = Transaccion.query.filter_by(familia_id=familia_id).order_by(Transaccion.fecha.desc()).all()
    resultado = [
        {
            'id': t.id,
            'tipo': t.tipo,
            'puntos': t.puntos,
            'descripcion': t.descripcion,
            'fecha': t.fecha.strftime('%Y-%m-%d %H:%M:%S')
        }
        for t in transacciones
    ]

    return jsonify({'historial': resultado})

@app.route("/familias", methods=["GET"])
def obtener_familias():
    familias = Familia.query.all()
    resultado = []
    for familia in familias:
        resultado.append({
            "id": familia.id,
            "nombre": familia.nombre,
            "correo": familia.correo,
            "puntos": familia.puntos,
            "password": familia.password  
        })
    return jsonify(resultado)

from flask import render_template

@app.route('/familia/<int:familia_id>/ver')
def ver_familia(familia_id):
    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    # Obtener filtros desde la URL
    tipo = request.args.get('tipo')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')

    # Base de la consulta
    query = Transaccion.query.filter_by(familia_id=familia_id)

    # Filtro por tipo
    if tipo in ['suma', 'canje']:
        query = query.filter_by(tipo=tipo)

    # Filtro por fechas
    if fecha_inicio:
        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            query = query.filter(Transaccion.fecha >= fecha_inicio_dt)
        except ValueError:
            pass  # Ignora fechas inválidas

    if fecha_fin:
        try:
            fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
            fecha_fin_dt = fecha_fin_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Transaccion.fecha <= fecha_fin_dt)
        except ValueError:
            pass

    transacciones = query.order_by(Transaccion.fecha.desc()).all()

    # PASAR EL ROL ACTUAL A LA PLANTILLA
    rol_actual = session.get('rol', None)

    return render_template('familia.html', familia=familia, transacciones=transacciones, rol=rol_actual)


@app.route('/familia/<int:familia_id>/transaccion', methods=['POST'])
def registrar_transaccion_web(familia_id):
    data = request.get_json()
    tipo = data.get("tipo")
    try:
        puntos = int(data.get("puntos"))
    except (TypeError, ValueError):
        return jsonify({"error": "Puntos inválidos"}), 400

    descripcion = data.get("descripcion")
    familia = Familia.query.get(familia_id)
    if not familia:
        return jsonify({"error": "Familia no encontrada"}), 404

    if tipo not in ['suma', 'canje']:
        return jsonify({"error": "Tipo de transacción no válido"}), 400

    if tipo == 'canje' and puntos > familia.puntos:
        return jsonify({"error": "No tienes suficientes puntos"}), 400

    puntos_finales = puntos if tipo == 'suma' else -abs(puntos)

    hora_mexico = datetime.now(pytz.timezone('America/Mexico_City')).replace(tzinfo=None)
    transaccion = Transaccion(
    familia_id=familia_id,
    tipo=tipo,
    puntos=puntos_finales,
    descripcion=descripcion,
    fecha=hora_mexico
)

    # **Este es el punto clave: ACTUALIZA EL CAMPO DE PUNTOS**
    familia.puntos += puntos_finales

    db.session.add(transaccion)
    db.session.commit()

    return jsonify({"mensaje": "Transacción registrada con éxito"})




@app.route('/familia/<int:familia_id>/exportar')
def exportar_transacciones(familia_id):
    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    transacciones = Transaccion.query.filter_by(familia_id=familia_id).order_by(Transaccion.fecha.desc()).all()

    # Crear archivo CSV con codificación UTF-8 con BOM
    buffer = BytesIO()
    wrapper = TextIOWrapper(buffer, encoding='utf-8-sig', newline='')
    writer = csv.writer(wrapper)

    # Encabezados con columna de familia
    writer.writerow(['Familia', 'Fecha', 'Tipo', 'Puntos', 'Descripción'])

    for t in transacciones:
        writer.writerow([
            familia.nombre,
            t.fecha.strftime('%Y-%m-%d %H:%M'),
            'Acreditación' if t.tipo == 'suma' else 'Canje',
            t.puntos,
            t.descripcion or 'Sin descripción'
        ])

    wrapper.flush()
    buffer.seek(0)

    return Response(
        buffer.read(),
        mimetype='text/csv',
        headers={
            "Content-Disposition": f"attachment; filename=transacciones_{familia.nombre}.csv"
        }
    )
    
@app.route('/crear_admin', methods=['GET', 'POST'])
def crear_admin():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')
        rol = request.form.get('rol')

        if not usuario or not password or not rol:
            flash("Todos los campos son obligatorios", "error")
            return render_template("crear_admin.html")

        if Admin.query.filter_by(usuario=usuario).first():
            flash("Ese usuario ya existe", "error")
            return render_template("crear_admin.html")

        nuevo_admin = Admin(usuario=usuario, rol=rol)
        nuevo_admin.set_password(password)  # ← Usa el método para guardar el hash

        db.session.add(nuevo_admin)
        db.session.commit()

        flash("Usuario creado con éxito", "success")
        return redirect(url_for('crear_admin'))

    return render_template("crear_admin.html")



@app.route('/admin/usuarios')
@requiere_rol('admin')
def lista_administradores():
    if 'admin_id' not in session:
        return redirect(url_for('login'))   
    administradores = Admin.query.all()
    return render_template('lista_administradores.html', administradores=administradores) 

@app.route('/admin/usuarios/eliminar/<int:admin_id>', methods=['POST'])
@requiere_rol('admin')
def eliminar_administrador(admin_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    admin = Admin.query.get(admin_id)
    print("Intentando eliminar:", admin.usuario if admin else None)
    print("Logueado como:", session.get('admin'))

    # Validación 1: El usuario 'admin' no se puede eliminar nunca
    if not admin:
        flash("Administrador no encontrado", "error")
    elif admin.usuario.lower() == 'admin':
        flash("El usuario principal 'admin' no puede ser eliminado.", "error")
    # Validación 2: El admin logueado no puede eliminarse a sí mismo
    elif admin.usuario == session.get('admin'):
        flash("No puedes eliminar el usuario con el que estás logueado.", "error")
    else:
        db.session.delete(admin)
        db.session.commit()
        
        # 🗑 Admin eliminado
    entry = LogEntry(
        timestamp=datetime.utcnow(),
        user=session.get("nombre_usuario"),
        role=session.get("rol"),
        action="eliminar",
        entity="Administrador",
        details=f"id={admin_id}"
    )
    db.session.add(entry)
    db.session.commit()
        
    flash("Administrador eliminado exitosamente", "success")

    return redirect(url_for('lista_administradores'))



@app.route('/escanear')
def escanear_qr():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    return render_template('escanear.html')


@app.route('/familia/<int:familia_id>/qr')
def mostrar_qr_familia(familia_id):
    import qrcode
    import os
    from flask import send_file

    # Generar la URL del perfil
    url = url_for('ver_familia', familia_id=familia_id, _external=True)

    # Generar el QR
    qr = qrcode.make(url)
    ruta_temp = os.path.join('app', 'static', f'qr_familia_{familia_id}.png')
    qr.save(ruta_temp)

    return send_file(ruta_temp, mimetype='image/png')


@app.route("/login_familia", methods=["GET", "POST"])
def login_familia():
    if request.method == "POST":
        correo = request.form["correo"]
        password = request.form["password"]

        familia = Familia.query.filter_by(correo=correo).first()
        if familia and familia.password == password:
            session["familia_id"] = familia.id
            return redirect(url_for("perfil_familia", familia_id=familia.id))
        else:
            flash("Credenciales inválidas para familia", "error")
            return render_template("login_unificado.html", active_tab="familia")
    return render_template("login_unificado.html", active_tab="familia")

@app.route('/logout_familia')
def logout_familia():
    session.pop('familia_id', None)
    return redirect(url_for('login_familia'))

@app.route('/perfil_familia/<int:familia_id>')
def perfil_familia(familia_id):
    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    transacciones = Transaccion.query.filter_by(familia_id=familia_id).order_by(Transaccion.fecha.desc()).all()
    print("TRANSACCIONES ENCONTRADAS:", transacciones)  # <--- AQUÍ
    
    beneficios = Beneficio.query.all()
    ultimo_evento = EventoQR.query.order_by(EventoQR.id.desc()).first()  # 🔹 nuevo
    rol = session.get('rol')  # <--- obtener rol de sesión

    return render_template(
        'perfil_familia.html',
        familia=familia,
        transacciones=transacciones,
        beneficios=beneficios,
        ultimo_evento=ultimo_evento,
        rol=rol  # <--- pasar rol al template
    )




@app.route('/familia/<int:familia_id>/generar_qr', methods=['POST'])
def generar_o_regenerar_qr(familia_id):
    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    # Crear carpeta si no existe
    qr_folder = os.path.join('app', 'static', 'qr')
    os.makedirs(qr_folder, exist_ok=True)

    # Crear ruta de archivo
    qr_path = os.path.join(qr_folder, f'familia_{familia.id}.png')

    # Generar URL y código QR
    qr_data = url_for('ver_familia', familia_id=familia.id, _external=True)
    qr = qrcode.make(qr_data)
    qr.save(qr_path)

    flash("Código QR generado correctamente", "success")
    return redirect(url_for('ver_familia', familia_id=familia.id))


@app.route('/escanear_qr/<int:familia_id>', methods=['GET'])
def escanear_qr_suma(familia_id):
    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    puntos = 5  # Ajusta el número de puntos a sumar por escaneo
    familia.puntos += puntos

    movimiento = MovimientoPuntos(
        familia_id=familia.id,
        cambio=puntos,
        motivo="Puntos por escaneo QR"
    )
    db.session.add(movimiento)
    db.session.commit()

    return f"¡Se sumaron {puntos} puntos a {familia.nombre}!"

from flask import current_app


@app.route('/escanear_evento_directo/<int:evento_id>')
def escanear_evento_qr(evento_id):
    familia_id = session.get('familia_id')
    if not familia_id:
        return redirect(url_for('login_familia'))

    evento = EventoQR.query.get(evento_id)
    if not evento:
        return "Evento no encontrado", 404

    ya_escaneo = EventoQRRegistro.query.filter_by(familia_id=familia_id, evento_id=evento_id).first()
    if ya_escaneo:
        return render_template("asistencia_exitosa.html", evento=evento, familia=Familia.query.get(familia_id), ya_asistio=True)

    familia = Familia.query.get(familia_id)
    familia.puntos += evento.puntos

    db.session.add(EventoQRRegistro(familia_id=familia_id, evento_id=evento_id))
    db.session.add(Transaccion(
        familia_id=familia.id,
        tipo='suma',
        puntos=evento.puntos,
        descripcion=f"Asistencia al evento: {evento.nombre_evento}"
    ))
    db.session.commit()

    return render_template("asistencia_exitosa.html", evento=evento, familia=familia, ya_asistio=False)



@app.route('/admin/crear_beneficio', methods=['GET', 'POST'])
@requiere_rol('admin')
def crear_beneficio():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    # Obtener siempre los beneficios para mostrar la tabla
    beneficios = Beneficio.query.all()

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        puntos_requeridos = request.form.get('puntos_requeridos')

        if not nombre or not puntos_requeridos:
            flash("Todos los campos son obligatorios", "error")
            return render_template('crear_beneficio.html', beneficios=beneficios)

        try:
            puntos_requeridos = int(puntos_requeridos)
        except ValueError:
            flash("Los puntos deben ser un número", "error")
            return render_template('crear_beneficio.html', beneficios=beneficios)

        beneficio = Beneficio(nombre=nombre, puntos_requeridos=puntos_requeridos)
        db.session.add(beneficio)
        db.session.commit()
        
        # 🎁 Beneficio creado
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            user=session.get("nombre_usuario"),
            role=session.get("rol"),
            action="crear",
            entity="Beneficio",
            details=f"id={beneficio.id}, nombre={beneficio.nombre}"
        )
        db.session.add(entry)
        db.session.commit()

        flash("Beneficio creado exitosamente", "success")
        return redirect(url_for('crear_beneficio'))  # Redirige a la misma vista para ver el nuevo canje

    return render_template('crear_beneficio.html', beneficios=beneficios)


@app.route('/escanear_qr_evento/<int:evento_id>/<int:familia_id>')
def escanear_qr_familia_en_evento(evento_id, familia_id):
    evento = EventoQR.query.get(evento_id)
    if not evento:
        return "Evento no encontrado", 404

    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    ya_escaneo = EventoQRRegistro.query.filter_by(familia_id=familia_id, evento_id=evento_id).first()
    if ya_escaneo:
        return "Esta familia ya fue registrada en este evento", 400

    familia.puntos += evento.puntos
    db.session.add(EventoQRRegistro(familia_id=familia_id, evento_id=evento_id))
    db.session.commit()

    return f"Puntos del evento '{evento.nombre_evento}' sumados correctamente a la familia '{familia.nombre}'."


@app.route('/staff/escanear/<int:familia_id>', methods=['GET', 'POST'])
@requiere_rol('admin', 'supervisor')
def escanear_familia_staff(familia_id):
    if 'admin' not in session:
        return redirect(url_for('login'))

    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    eventos = EventoQR.query.all()

    if request.method == 'POST':
        evento_id = int(request.form['evento_id'])

        ya_asistio = EventoQRRegistro.query.filter_by(familia_id=familia_id, evento_id=evento_id).first()
        if ya_asistio:
            flash("Esta familia ya recibió puntos por este evento", "error")
        else:
            evento = EventoQR.query.get(evento_id)
            familia.puntos += evento.puntos
            registro = EventoQRRegistro(familia_id=familia_id, evento_id=evento_id)
            db.session.add(registro)
            db.session.commit()
            flash(f"{evento.puntos} puntos sumados por el evento '{evento.nombre_evento}'", "success")

        return redirect(url_for('escanear_familia_staff', familia_id=familia_id))

    return render_template('escanear_staff.html', familia=familia, eventos=eventos)

@app.route('/familia/<int:familia_id>/generar_qr_staff', methods=['POST'])
def generar_qr_staff(familia_id):
    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    # Crear carpeta si no existe
    qr_folder = os.path.join('app', 'static', 'qr')
    os.makedirs(qr_folder, exist_ok=True)

    # Crear ruta de archivo
    qr_path = os.path.join(qr_folder, f'familia_{familia.id}.png')

    # ✅ Nueva URL para escaneo de staff
    qr_data = url_for('escanear_familia_staff', familia_id=familia.id, _external=True)
    qr = qrcode.make(qr_data)
    qr.save(qr_path)

    flash("Código QR actualizado para uso del staff", "success")
    return redirect(url_for('ver_familia', familia_id=familia.id))

@app.route('/admin/escanear_evento', methods=['GET'])
def escanear_evento_staff():
    if 'admin' not in session:
        return redirect(url_for('login'))

    eventos = EventoQR.query.order_by(EventoQR.id.desc()).all()
    return render_template('escanear_evento_staff.html', eventos=eventos)

@app.route('/api/escanear_qr_evento', methods=['POST'])
def escanear_qr_evento_api():
    data = request.get_json()
    evento_id = data.get('evento_id')
    familia_id = data.get('familia_id')

    if not evento_id or not familia_id:
        return jsonify({"error": "Faltan datos"}), 400

    evento = EventoQR.query.get(evento_id)
    familia = Familia.query.get(familia_id)

    if not evento:
        return jsonify({"error": "Evento no encontrado"}), 404
    if not familia:
        return jsonify({"error": "Familia no encontrada"}), 404

    # Verificar si ya escaneó este evento
    ya_registrado = EventoQRRegistro.query.filter_by(evento_id=evento_id, familia_id=familia_id).first()
    if ya_registrado:
        return jsonify({"error": "Esta familia ya fue registrada en este evento"}), 409

    # Registrar puntos y guardar asistencia
    familia.puntos += evento.puntos
    db.session.add(EventoQRRegistro(familia_id=familia_id, evento_id=evento_id))
    db.session.add(Transaccion(
        familia_id=familia_id,
        tipo='suma',
        puntos=evento.puntos,
        descripcion=f"Asistencia al evento: {evento.nombre_evento}"
    ))
    db.session.commit()

    return jsonify({
        "mensaje": f"Puntos agregados correctamente por asistir al evento '{evento.nombre_evento}'",
        "puntos_actuales": familia.puntos
    }), 200

@app.route('/api/escanear_qr_evento', methods=['POST'])
def api_escanear_qr_evento():
    if 'admin' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    data = request.get_json()
    familia_id = data.get('familia_id')
    evento_id = data.get('evento_id')

    if not familia_id or not evento_id:
        return jsonify({'error': 'Datos incompletos'}), 400

    familia = Familia.query.get(familia_id)
    evento = EventoQR.query.get(evento_id)

    if not familia or not evento:
        return jsonify({'error': 'Familia o evento no encontrados'}), 404

    ya_escaneo = EventoQRRegistro.query.filter_by(familia_id=familia_id, evento_id=evento_id).first()
    if ya_escaneo:
        return jsonify({'error': 'La familia ya escaneó este evento'}), 409

    familia.puntos += evento.puntos
    db.session.add(EventoQRRegistro(familia_id=familia_id, evento_id=evento_id))
    db.session.add(Transaccion(
        familia_id=familia_id,
        tipo="suma",
        puntos=evento.puntos,
        descripcion=f"Evento: {evento.nombre_evento}"
    ))
    db.session.commit()

    return jsonify({'mensaje': f"{evento.puntos} puntos asignados a {familia.nombre} por {evento.nombre_evento}"}), 200

@app.route("/admin/escaneo_evento/<int:evento_id>")
def vista_escaneo_evento(evento_id):
    evento = EventoQR.query.get_or_404(evento_id)
    return render_template('escaneo_evento.html', evento=evento)


@app.route('/admin/registrar_asistencia_evento', methods=["POST"])
def registrar_asistencia_evento():
    data = request.get_json()
    qr_url = data.get("qr_url")
    evento_id = data.get("evento_id")

    print("🔹 Data recibida:", data)

    if not qr_url or not evento_id:
        return jsonify({"error": "Datos incompletos"}), 400

    from urllib.parse import urlparse
    import re

    parsed_url = urlparse(qr_url)
    match = re.search(r'/familia/(\d+)', parsed_url.path)

    if not match:
        return jsonify({"error": "No se pudo extraer el ID de familia del QR"}), 400

    try:
        familia_id = int(match.group(1))
    except Exception:
        return jsonify({"error": "ID inválido en la URL"}), 400

    evento = EventoQR.query.get(evento_id)
    familia = Familia.query.get(familia_id)

    if not evento or not familia:
        return jsonify({"error": "Evento o familia no encontrada"}), 404

    ya_escaneo = EventoQRRegistro.query.filter_by(evento_id=evento.id, familia_id=familia.id).first()
    if ya_escaneo:
        return jsonify({"error": f"{familia.nombre} ya registró asistencia a {evento.nombre_evento}"}), 400

    familia.puntos += evento.puntos

    db.session.add(EventoQRRegistro(evento_id=evento.id, familia_id=familia.id))

    transaccion = Transaccion(
        familia_id=familia.id,
        tipo='suma',
        puntos=evento.puntos,
        descripcion=f"Asistencia al evento: {evento.nombre_evento}",
        fecha=datetime.now(pytz.timezone('America/Mexico_City')).replace(tzinfo=None) - timedelta(hours=6)
    )
    db.session.add(transaccion)
    db.session.commit()

    return jsonify({"mensaje": f"Asistencia registrada correctamente. Se sumaron {evento.puntos} puntos a {familia.nombre}"}), 200


from app.models import LugarFrecuente  # asegúrate de importarlo

from flask import request, render_template, redirect, url_for, flash, session, jsonify
from datetime import datetime
import pytz, os, qrcode
from geopy.distance import geodesic

from app import app, db
from app.models import EventoQR, EventoQRRegistro, Transaccion, LugarFrecuente, Familia

# --- Crear nuevo evento con QR ---
@app.route('/admin/crear_qr_evento', methods=['GET', 'POST'])
@requiere_rol('admin')
def crear_qr_evento():
    lugares = LugarFrecuente.query.all()
    eventos = EventoQR.query.order_by(EventoQR.id.desc()).all()

    if request.method == 'POST':
        nombre_evento = request.form['nombre_evento']
        puntos        = int(request.form['puntos'])
        latitud       = float(request.form['latitud'])
        longitud      = float(request.form['longitud'])
        requiere_ubic = 'requiere_ubic' in request.form
        valid_from    = request.form.get('valid_from')
        valid_to      = request.form.get('valid_to')

        evento = EventoQR(
            nombre_evento=nombre_evento,
            puntos=puntos,
            latitud=latitud,
            longitud=longitud,
            requiere_ubic=requiere_ubic,
            valid_from=datetime.strptime(valid_from, '%Y-%m-%dT%H:%M') if valid_from else None,
            valid_to=datetime.strptime(valid_to, '%Y-%m-%dT%H:%M')   if valid_to   else None
        )
        db.session.add(evento)
        db.session.flush()  # para obtener evento.id sin commit

        # Generar imagen QR
        qr_url   = url_for('escanear_evento_con_ubicacion', evento_id=evento.id, _external=True)
        qr_img   = qrcode.make(qr_url)
        qr_fname = f"evento_{evento.id}.png"
        qr_path  = os.path.join(app.root_path, 'static', 'qr_eventos', qr_fname)
        os.makedirs(os.path.dirname(qr_path), exist_ok=True)
        qr_img.save(qr_path)

        evento.qr_filename = qr_fname
        db.session.commit()

        flash('🎯 Evento QR creado con éxito.', 'success')
        return redirect(url_for('crear_qr_evento'))

    return render_template('crear_qr_evento.html', lugares=lugares, eventos=eventos)




@app.route('/escanear_evento/<int:evento_id>')
def escanear_evento_con_ubicacion(evento_id):
    evento = EventoQR.query.get_or_404(evento_id)
    return render_template('escanear_evento_con_ubicacion.html', evento=evento)

from geopy.distance import geodesic


from datetime import datetime
import pytz
from geopy.distance import geodesic
from flask import request, jsonify, url_for

# … tus imports y decoradores …

@app.route('/validar_ubicacion_evento', methods=['POST'])
def validar_ubicacion_evento():
    data       = request.get_json()
    lat        = data.get("lat")
    lon        = data.get("lon")
    evento_id  = data.get("evento_id")
    familia_id = session.get("familia_id")

    if not evento_id or not familia_id:
        return jsonify({"error": "Datos incompletos"}), 400

    evento  = EventoQR.query.get(evento_id)
    familia = Familia.query.get(familia_id)
    if not evento or not familia:
        return jsonify({"error": "Evento o familia no encontrada"}), 404

    # --- 1) Validación de rango de fecha/hora en hora local ---
    tz         = pytz.timezone("America/Mexico_City")
    ahora_local = datetime.now(tz)

    if evento.valid_from:
        vf_local = tz.localize(evento.valid_from)
        if ahora_local < vf_local:
            msg = vf_local.strftime('%d/%m/%Y %H:%M')
            return jsonify({
                "error": f"El evento aún no está activo. Disponible desde {msg}",
                "code": "fuera_de_fecha"
            }), 400

    if evento.valid_to:
        vt_local = tz.localize(evento.valid_to)
        if ahora_local > vt_local:
            msg = vt_local.strftime('%d/%m/%Y %H:%M')
            return jsonify({
                "error": f"El evento expiró. Válido hasta {msg}",
                "code": "fuera_de_fecha"
            }), 400

    # --- 2) Validación de ubicación ---
    if evento.requiere_ubic:
        distancia = geodesic((evento.latitud, evento.longitud),
                            (float(lat), float(lon))).meters
        if distancia > 500:
            return jsonify({"redirect": url_for("ubicacion_invalida", evento_id=evento.id)})

    # --- 3) Escaneo duplicado ---
    if EventoQRRegistro.query.filter_by(evento_id=evento.id, familia_id=familia.id).first():
        return jsonify({"redirect": url_for("asistencia_exitosa", evento_id=evento.id, ya_asistio=1)})

    # --- 4) Registro exitoso ---
    familia.puntos += evento.puntos
    db.session.add(EventoQRRegistro(familia_id=familia.id, evento_id=evento.id))
    db.session.add(Transaccion(
        familia_id=familia.id,
        tipo='suma',
        puntos=evento.puntos,
        descripcion=f"Asistencia al evento: {evento.nombre_evento}"
    ))
    db.session.commit()

    return jsonify({"redirect": url_for("asistencia_exitosa", evento_id=evento.id)})



@app.route("/asistencia_exitosa/<int:evento_id>")
def asistencia_exitosa(evento_id):
    ya_asistio = request.args.get("ya_asistio", default="0") == "1"
    evento = EventoQR.query.get_or_404(evento_id)
    familia_id = session.get("familia_id")
    familia = Familia.query.get_or_404(familia_id)
    return render_template("asistencia_exitosa.html", evento=evento, familia=familia, ya_asistio=ya_asistio)


@app.route('/ubicacion_invalida/<int:evento_id>')
def ubicacion_invalida(evento_id):
    evento = EventoQR.query.get_or_404(evento_id)
    return render_template('ubicacion_invalida.html', evento=evento)

@app.route('/admin/eliminar_evento/<int:evento_id>', methods=['POST'])
@requiere_rol('admin')
def eliminar_evento(evento_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    evento = EventoQR.query.get_or_404(evento_id)

    # Eliminar imagen QR si existe
    if evento.qr_filename:
        ruta_qr = os.path.join('app', 'static', 'qr_eventos', evento.qr_filename)
        if os.path.exists(ruta_qr):
            os.remove(ruta_qr)

    # Eliminar registros asociados (opcional si usas relaciones)
    registros = EventoQRRegistro.query.filter_by(evento_id=evento.id).all()
    for r in registros:
        db.session.delete(r)

    # Eliminar el evento
    db.session.delete(evento)
    db.session.commit()
    
    # 🗑 Evento eliminado
    entry = LogEntry(
        timestamp=datetime.utcnow(),
        user=session.get("nombre_usuario"),
        role=session.get("rol"),
        action="eliminar",
        entity="Evento",
        details=f"id={evento_id}"
    )
    db.session.add(entry)
    db.session.commit()

    flash("Evento eliminado correctamente", "exito")
    return redirect(url_for('panel_admin'))

from flask import send_from_directory

@app.route('/descargar_qr_evento/<filename>')
def descargar_qr_evento(filename):
    carpeta_qr = os.path.join(app.root_path, 'static', 'qr_eventos')
    return send_from_directory(carpeta_qr, filename, as_attachment=True)

@app.route('/descargar_qr/<int:familia_id>')
def descargar_qr(familia_id):
    ruta = os.path.join(app.root_path, 'static', 'qr', f'familia_{familia_id}.png')
    return send_file(ruta, as_attachment=True)

@app.route('/escanear_evento/<int:evento_id>')
def escanear_evento_directo(evento_id):
    if "familia_id" not in session:
        return redirect(url_for("login_familia"))

    evento = EventoQR.query.get_or_404(evento_id)
    return render_template("escanear_evento.html", evento=evento)

@app.route('/familia/escanear_evento')
def escanear_evento_desde_familia():
    if 'familia_id' not in session:
        return redirect(url_for('login_familia'))
    return render_template('escanear_evento_desde_familia.html')


from datetime import datetime
import pytz
from flask import request, jsonify, url_for, session
from geopy.distance import geodesic
from app import db
from app.models import EventoQR, Familia, EventoQRRegistro, Transaccion

@app.route('/validar_qr_evento', methods=["POST"])
def validar_qr_evento():
    data       = request.get_json()
    evento_id  = data.get("evento_id")
    lat        = data.get("lat")
    lon        = data.get("lon")
    familia_id = session.get("familia_id")

    # 0. Comprobación básica
    if not evento_id or not familia_id:
        return jsonify({"error": "Faltan datos"}), 400

    evento  = EventoQR.query.get(evento_id)
    familia = Familia.query.get(familia_id)
    if not evento or not familia:
        return jsonify({"error": "Evento o familia no encontrada"}), 404

    # 1. Fecha/hora actual en zona local
    tz          = pytz.timezone("America/Mexico_City")
    ahora_local = datetime.now(tz)

    # valid_from
    if evento.valid_from:
        # asumimos que valid_from está guardado en UTC sin tzinfo
        vf_utc   = evento.valid_from.replace(tzinfo=pytz.UTC)
        vf_local = vf_utc.astimezone(tz)
        if ahora_local < vf_local:
            inicio = vf_local.strftime('%d/%m/%Y %H:%M')
            return jsonify({
                "error": f"El evento aún no está activo. Desde {inicio}",
                "code": "fuera_de_fecha"
            }), 400

    # valid_to
    if evento.valid_to:
        vt_utc   = evento.valid_to.replace(tzinfo=pytz.UTC)
        vt_local = vt_utc.astimezone(tz)
        if ahora_local > vt_local:
            fin = vt_local.strftime('%d/%m/%Y %H:%M')
            return jsonify({
                "error": f"El evento expiró. Hasta {fin}",
                "code": "fuera_de_fecha"
            }), 400

    # 2. Validación de ubicación (solo si requiere_ubic=True)
    if evento.requiere_ubic:
        if lat is None or lon is None:
            return jsonify({"error": "No se proporcionaron coordenadas"}), 400
        distancia_m = geodesic(
            (evento.latitud, evento.longitud),
            (float(lat), float(lon))
        ).meters
        if distancia_m > 500:
            return jsonify({
                "redirect": url_for("ubicacion_invalida", evento_id=evento.id)
            })

    # 3. Checar duplicados
    if EventoQRRegistro.query.filter_by(
        evento_id=evento.id,
        familia_id=familia.id
    ).first():
        return jsonify({
            "redirect": url_for(
                "asistencia_exitosa",
                evento_id=evento.id,
                ya_asistio=1
            )
        })

    # 4. Registrar asistencia y sumar puntos
    familia.puntos += evento.puntos
    db.session.add(EventoQRRegistro(
        familia_id=familia.id,
        evento_id=evento.id
    ))
    db.session.add(Transaccion(
        familia_id=familia.id,
        tipo='suma',
        puntos=evento.puntos,
        descripcion=f"Asistencia al evento: {evento.nombre_evento}"
    ))
    db.session.commit()

    return jsonify({
        "redirect": url_for("asistencia_exitosa", evento_id=evento.id)
    })



# Ruta en routes.py
from flask import render_template, request, redirect, url_for, flash
from app.models import Familia
from app import db

@app.route('/familia/<int:familia_id>/editar', methods=['GET', 'POST'])
def editar_familia(familia_id):
    familia = Familia.query.get_or_404(familia_id)
    if request.method == 'POST':
        familia.nombre = request.form['nombre']
        familia.correo = request.form['correo']
        familia.password = request.form['password']
        db.session.commit()

        # 📝 Familia editada
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            user=session.get("nombre_usuario"),
            role=session.get("rol"),
            action="editar",
            entity="Familia",
            details=f"id={familia.id}, nombre={familia.nombre}"
        )
        db.session.add(entry)
        db.session.commit()

        flash('Familia actualizada correctamente', 'success')
        return render_template('editar_familia.html', familia=familia)
    return render_template('editar_familia.html', familia=familia)




@app.route('/admin/crear_lugar', methods=['GET', 'POST'])
def crear_lugar():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        latitud = request.form['latitud']
        longitud = request.form['longitud']
        nuevo_lugar = LugarFrecuente(nombre=nombre, latitud=latitud, longitud=longitud)
        db.session.add(nuevo_lugar)
        db.session.commit()
        flash('Lugar creado con éxito.', 'success')
        return redirect(url_for('crear_lugar'))

    lugares = LugarFrecuente.query.all()
    return render_template('crear_lugar.html', lugares=lugares)

# Eliminar lugar
@app.route('/admin/eliminar_lugar/<int:id>', methods=['POST'])
def eliminar_lugar(id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    lugar = LugarFrecuente.query.get_or_404(id)
    db.session.delete(lugar)
    db.session.commit()
    flash('Lugar eliminado correctamente.', 'success')
    return redirect(url_for('crear_lugar'))

# Editar lugar
@app.route('/admin/editar_lugar/<int:id>', methods=['GET', 'POST'])
def editar_lugar(id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    lugar = LugarFrecuente.query.get_or_404(id)

    if request.method == 'POST':
        lugar.nombre = request.form['nombre']
        lugar.latitud = request.form['latitud']
        lugar.longitud = request.form['longitud']
        db.session.commit()
        flash('Lugar actualizado correctamente.', 'success')
        return redirect(url_for('crear_lugar'))

    return render_template('editar_lugar.html', lugar=lugar)

@app.route('/admin/eliminar_eventos', methods=['POST'])
def eliminar_eventos():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    ids = request.form.getlist('eventos_seleccionados')

    for evento_id in ids:
        # Eliminar registros relacionados
        registros = EventoQRRegistro.query.filter_by(evento_id=evento_id).all()
        for r in registros:
            db.session.delete(r)

        # Eliminar evento
        evento = EventoQR.query.get(evento_id)
        if evento:
            # Borrar el archivo QR si existe
            ruta_qr = os.path.join('app', 'static', 'qr_eventos', evento.qr_filename)
            if os.path.exists(ruta_qr):
                os.remove(ruta_qr)

            db.session.delete(evento)

    db.session.commit()
    flash('Eventos eliminados correctamente', 'success')
    return redirect(url_for('crear_qr_evento'))

from flask import render_template, request, redirect, url_for, flash, session
from app.models import EventoQR, LugarFrecuente, EventoQRRegistro, Transaccion
from app import db
from functools import wraps
from datetime import datetime

# ... tu decorador requiere_rol ...

@app.route('/admin/editar_evento/<int:evento_id>', methods=['GET', 'POST'])
@requiere_rol('admin')
def editar_evento(evento_id):
    evento = EventoQR.query.get_or_404(evento_id)
    lugares = LugarFrecuente.query.all()   # <-- cargamos los lugares frecuentes

    if request.method == 'POST':
        evento.nombre_evento = request.form['nombre_evento']
        evento.puntos         = int(request.form['puntos'])
        evento.latitud        = float(request.form['latitud'])
        evento.longitud       = float(request.form['longitud'])
        evento.requiere_ubic  = 'requiere_ubic' in request.form

        valid_from = request.form.get('valid_from')
        valid_to   = request.form.get('valid_to')

        evento.valid_from = datetime.strptime(valid_from, '%Y-%m-%dT%H:%M') if valid_from else None
        evento.valid_to   = datetime.strptime(valid_to,   '%Y-%m-%dT%H:%M') if valid_to   else None

        db.session.commit()
        flash('Evento actualizado correctamente.', 'success')
        return redirect(url_for('crear_qr_evento'))

    return render_template('editar_evento.html', evento=evento, lugares=lugares)




@app.route('/admin/editar_beneficio/<int:beneficio_id>', methods=['GET', 'POST'])
def editar_beneficio(beneficio_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    beneficio = Beneficio.query.get_or_404(beneficio_id)

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        puntos_requeridos = request.form.get('puntos_requeridos')

        if not nombre or not puntos_requeridos:
            flash("Todos los campos son obligatorios", "error")
            return redirect(url_for('editar_beneficio', beneficio_id=beneficio.id))

        try:
            puntos_requeridos = int(puntos_requeridos)
        except ValueError:
            flash("Los puntos deben ser un número", "error")
            return redirect(url_for('editar_beneficio', beneficio_id=beneficio.id))

        beneficio.nombre = nombre
        beneficio.puntos_requeridos = puntos_requeridos
        db.session.commit()
        flash("Beneficio actualizado exitosamente", "success")
        return redirect(url_for('crear_beneficio'))

    return render_template('editar_beneficio.html', beneficio=beneficio)

@app.route('/admin/eliminar_beneficio/<int:beneficio_id>', methods=['POST'])
@requiere_rol('admin')
def eliminar_beneficio(beneficio_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    beneficio = Beneficio.query.get_or_404(beneficio_id)
    db.session.delete(beneficio)
    db.session.commit()
    
        # 🗑 Beneficio eliminado
    entry = LogEntry(
        timestamp=datetime.utcnow(),
        user=session.get("nombre_usuario"),
        role=session.get("rol"),
        action="eliminar",
        entity="Beneficio",
        details=f"id={beneficio_id}"
    )
    db.session.add(entry)
    db.session.commit()
    flash("Beneficio eliminado exitosamente", "success")
    return redirect(url_for('crear_beneficio'))

from flask import send_file
import csv
from io import BytesIO, TextIOWrapper

# Vista para mostrar historial de escaneos de un evento
@app.route('/admin/evento/<int:evento_id>/historial')
def historial_escaneos_evento(evento_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    evento = EventoQR.query.get_or_404(evento_id)
    registros = EventoQRRegistro.query.filter_by(evento_id=evento_id).order_by(EventoQRRegistro.id.desc()).all()
    # Cargar familia con .familia gracias a la relación
    return render_template('historial_escaneos_evento.html', evento=evento, registros=registros)

@app.route('/admin/evento/<int:evento_id>/exportar')
def exportar_historial_escaneos_evento(evento_id):
    evento = EventoQR.query.get_or_404(evento_id)
    registros = EventoQRRegistro.query.filter_by(evento_id=evento_id).order_by(EventoQRRegistro.fecha.desc()).all()

    buffer = BytesIO()
    # Envolvemos el buffer para escribir texto
    wrapper = TextIOWrapper(buffer, encoding='utf-8-sig', newline='', write_through=True)
    writer = csv.writer(wrapper)

    writer.writerow(['ID Familia', 'Nombre Familia', 'Fecha de escaneo'])

    for r in registros:
        nombre_familia = r.familia.nombre if r.familia else "-"
        fecha_local = (r.fecha - timedelta(hours=6)).strftime('%Y-%m-%d %H:%M')
        writer.writerow([r.familia_id, nombre_familia, fecha_local])

    # No cerramos wrapper, solo hacemos flush
    wrapper.flush()
    buffer.seek(0)  # Volvemos al inicio para leer todo el contenido

    return Response(
        buffer.read(),
        mimetype='text/csv',
        headers={
            "Content-Disposition": f"attachment; filename=historial_escaneos_evento_{evento.id}.csv"
        }
    )


#GENERACION DE PDF CON QR

from io import BytesIO
from flask import make_response
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import qrcode
import os

@app.route('/familia/<int:familia_id>/descargar_pdf_qr')
def descargar_pdf_qr_familia(familia_id):
    familia = Familia.query.get_or_404(familia_id)

    # Generar URL que irá en el QR
    url = url_for('ver_familia', familia_id=familia.id, _external=True)

    # Crear QR
    qr_img = qrcode.make(url)
    qr_bytes = BytesIO()
    qr_img.save(qr_bytes)
    qr_bytes.seek(0)

    # Crear PDF en memoria
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Título: Nombre de la familia
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(4.25 * inch, 10 * inch, f"QR de la familia: {familia.nombre}")

    # Insertar QR en PDF
    qr_temp_path = os.path.join('app', 'static', f'temp_qr_{familia.id}.png')
    qr_img.save(qr_temp_path)
    c.drawImage(qr_temp_path, 2.5 * inch, 6 * inch, width=3*inch, height=3*inch)

    # Finalizar PDF
    c.showPage()
    c.save()
    buffer.seek(0)

    # Eliminar archivo temporal QR
    os.remove(qr_temp_path)

    # Preparar respuesta con PDF
    response = make_response(buffer.getvalue())
    response.headers.set('Content-Type', 'application/pdf')
    response.headers.set('Content-Disposition', 'attachment', filename=f'qr_familia_{familia.id}.pdf')

    return response

from app.models import EventoQR  # Asegúrate de importar tu modelo

@app.route('/evento/<int:evento_id>/descargar_pdf_qr')
def descargar_pdf_qr_evento(evento_id):
    evento = EventoQR.query.get(evento_id)
    if not evento:
        abort(404, description="Evento no encontrado")

    # Ruta completa del QR guardado en static
    qr_path = os.path.join('app', 'static', 'qr_eventos', evento.qr_filename)

    if not os.path.exists(qr_path):
        abort(404, description="QR no encontrado")

    # Crear PDF en memoria
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Título
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 100, evento.nombre_evento)

    # Insertar imagen QR (centrada)
    qr_size = 200
    c.drawImage(qr_path, (width - qr_size) / 2, height - 350, qr_size, qr_size)

    c.showPage()
    c.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{evento.nombre_evento}_QR.pdf", mimetype='application/pdf')

@app.route('/puntos-masivos', methods=['GET', 'POST'])
def puntos_masivos():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    rol = session.get('rol')
    if rol != 'admin':
        flash('No tienes permisos para acceder a esta página', 'error')
        return redirect(url_for('panel_admin'))

    familias = Familia.query.all()

    if request.method == 'POST':
        ids_seleccionados = request.form.getlist('familia_ids')  # lista de ids seleccionados
        tipo = request.form.get('tipo')  # 'suma' o 'canje'
        puntos = request.form.get('puntos')
        descripcion = request.form.get('descripcion')

        if not ids_seleccionados or not puntos or not tipo or not descripcion:
            flash('Completa todos los campos y selecciona al menos una familia', 'error')
            return redirect(url_for('puntos_masivos'))

        try:
            puntos = int(puntos)
            if puntos <= 0:
                flash('Los puntos deben ser un número positivo', 'error')
                return redirect(url_for('puntos_masivos'))
        except ValueError:
            flash('Los puntos deben ser un número válido', 'error')
            return redirect(url_for('puntos_masivos'))

        # Procesar cada familia seleccionada
        for fid in ids_seleccionados:
            familia = Familia.query.get(int(fid))
            if familia:
                if tipo == 'suma':
                    familia.puntos += puntos
                elif tipo == 'canje':
                    familia.puntos -= puntos
                    if familia.puntos < 0:
                        familia.puntos = 0
                # Registrar transacción
                nueva_transaccion = Transaccion(
                    familia_id=familia.id,
                    tipo=tipo,
                    puntos=puntos,
                    descripcion=descripcion,
                    fecha=datetime.now(pytz.timezone('America/Mexico_City')).replace(tzinfo=None)
                )
                db.session.add(nueva_transaccion)

        db.session.commit()
        
        
            # 🔢 Puntos masivos
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            user=session.get("nombre_usuario"),
            role=session.get("rol"),
            action="masivo_" + tipo,
            entity="Familia",
            details=f"{len(ids_seleccionados)} familias, pts={puntos}"
        )
        db.session.add(entry)
        db.session.commit()
        
        flash(f'Se han actualizado los puntos de {len(ids_seleccionados)} familias.', 'success')
        return redirect(url_for('puntos_masivos'))

    return render_template('puntos_masivos.html', familias=familias)

from app import app, db
from flask import render_template, redirect, url_for, request, flash, session
from app.models import Familia, Transaccion, MovimientoPuntos  # ajusta nombres

# Borrar una sola familia
@app.route('/familia/<int:familia_id>/eliminar', methods=['POST'])
def eliminar_familia(familia_id):
    familia = Familia.query.get_or_404(familia_id)
    Transaccion.query.filter_by(familia_id=familia_id).delete()
    MovimientoPuntos.query.filter_by(familia_id=familia_id).delete()
    db.session.delete(familia)
    db.session.commit()

    # 🗑 Familia eliminada
    entry = LogEntry(
        timestamp=datetime.utcnow(),
        user=session.get("nombre_usuario"),
        role=session.get("rol"),
        action="eliminar",
        entity="Familia",
        details=f"id={familia_id}"
    )
    db.session.add(entry)
    db.session.commit()

    flash('Familia eliminada correctamente', 'success')
    return redirect(url_for('lista_familias_eliminar'))


# Borrado masivo
@app.route('/familias/eliminar_masivo', methods=['POST'])
def eliminar_familias_masivo():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    ids = request.form.getlist('familias_seleccionadas')
    if ids:
        # Borra todo de una sola pasada
        Transaccion.query.filter(Transaccion.familia_id.in_(ids)).delete(synchronize_session=False)
        MovimientoPuntos.query.filter(MovimientoPuntos.familia_id.in_(ids)).delete(synchronize_session=False)
        Familia.query.filter(Familia.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        flash(f'Se eliminaron {len(ids)} familias', 'success')
    else:
        flash('No se seleccionó ninguna familia', 'error')

    return redirect(url_for('lista_familias_eliminar'))


# Listar en la nueva plantilla
@app.route('/admin/familias/eliminar')
def lista_familias_eliminar():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    familias = Familia.query.all()
    return render_template('lista_familias_eliminar.html', familias=familias)



#LOG__________________________________________________

from flask import request, render_template
from app.models import LogEntry
from app import db
from datetime import datetime, timedelta
import pytz

from flask import request, render_template
from app.models import LogEntry
from app import db
import pytz
from datetime import datetime, timedelta

@app.route("/admin/log")
@login_requerido_admin
def log():
    # Parámetros de filtro opcionales
    usuario     = request.args.get("usuario", "")
    accion      = request.args.get("accion", "")
    entidad     = request.args.get("entidad", "")
    fecha_desde = request.args.get("desde", "")
    fecha_hasta = request.args.get("hasta", "")

    q = LogEntry.query

    if usuario:
        q = q.filter(LogEntry.user.ilike(f"%{usuario}%"))
    if accion:
        q = q.filter(LogEntry.action == accion)
    if entidad:
        q = q.filter(LogEntry.entity == entidad)

    # filtro de fechas UTC
    if fecha_desde:
        dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
        q = q.filter(LogEntry.timestamp >= dt)
    if fecha_hasta:
        dt = datetime.strptime(fecha_hasta, "%Y-%m-%d") + timedelta(hours=23, minutes=59, seconds=59)
        q = q.filter(LogEntry.timestamp <= dt)

    entries = q.order_by(LogEntry.timestamp.desc()).all()

    # Convertimos UTC → hora local
    # Cambia "America/Mexico_City" por tu zona si es distinto
    local_tz = pytz.timezone("America/Mexico_City")
    for e in entries:
        # e.timestamp es datetime UTC; hacemos astimezone
        e.local_ts = e.timestamp.replace(tzinfo=pytz.utc).astimezone(local_tz)

    return render_template("log.html", entries=entries)

from datetime import datetime, timedelta, timezone

@app.before_request
def refrescar_timeout():
    if "admin_id" in session:
        # Creamos now como naive UTC
        now = datetime.utcnow()
        # Recuperamos el último timestamp (o now por defecto)
        last = session.get("last_activity", now)

        # Si last viene con tzinfo, lo convertimos a naive UTC
        if hasattr(last, "tzinfo") and last.tzinfo is not None:
            last = last.astimezone(timezone.utc).replace(tzinfo=None)

        # Comparamos
        if now - last > timedelta(minutes=30):  # tu inactividad límite
            # registrar timeout en log
            entry = LogEntry(
                user=session.get("nombre_usuario"),
                role=session.get("rol"),
                action="timeout sesión",
                entity="Admin",
                details="Cierre de sesión por inactividad"
            )
            db.session.add(entry)
            db.session.commit()
            session.clear()
            return redirect(url_for("login"))

        # si no ha expirado, refrescamos la marca de actividad
        session["last_activity"] = now
from flask import send_file
import zipfile
import io
import os
import csv
from werkzeug.security import check_password_hash  # por si no estaba importado

@app.route("/resetear_base_datos", methods=["POST"])
@login_requerido_admin
def resetear_base_datos():
    if session.get("rol") != "admin":
        return "No autorizado", 403

    data = request.get_json()
    password = data.get("password", "")
    admin_id = session.get("admin_id")
    admin = Admin.query.get(admin_id)

    if not admin or not admin.verificar_password(password):
        return "Contraseña incorrecta", 401

    os.makedirs("respaldo", exist_ok=True)

    # Crear ZIP en memoria
    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
        def agregar_csv(nombre, query, campos):
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(campos)
            for item in query:
                writer.writerow([getattr(item, campo) for campo in campos])
            zipf.writestr(f"{nombre}.csv", output.getvalue())

        agregar_csv("familias", Familia.query.all(), ["id", "nombre", "correo", "puntos"])
        agregar_csv("transacciones", Transaccion.query.all(), ["id", "familia_id", "tipo", "puntos", "descripcion", "fecha"])
        agregar_csv("movimientos", MovimientoPuntos.query.all(), ["id", "familia_id", "cambio", "motivo", "fecha"])
        agregar_csv("beneficios", Beneficio.query.all(), ["id", "nombre", "puntos_requeridos"])
        agregar_csv("eventos_qr", EventoQR.query.all(), ["id", "nombre_evento", "puntos", "qr_filename", "latitud", "longitud", "requiere_ubic", "valid_from", "valid_to"])
        agregar_csv("eventos_registrados", EventoQRRegistro.query.all(), ["id", "familia_id", "evento_id", "fecha"])

    zip_stream.seek(0)
    zip_filename = f"respaldo_cuponera_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    with open(os.path.join("respaldo", zip_filename), "wb") as f:
        f.write(zip_stream.getvalue())

    # Borrar registros (excepto Admins)
    db.session.query(EventoQRRegistro).delete()
    db.session.query(EventoQR).delete()
    db.session.query(MovimientoPuntos).delete()
    db.session.query(Transaccion).delete()
    db.session.query(Beneficio).delete()
    db.session.query(Familia).delete()
    db.session.commit()

    # Guardar en el log
    nuevo_log = LogEntry(
        timestamp=datetime.utcnow(),
        user=admin.usuario,
        role=admin.rol,
        action="eliminar",
        entity="Base de datos",
        details="El administrador ejecutó un reseteo completo de la base de datos al inicio del ciclo escolar."
    )
    db.session.add(nuevo_log)
    db.session.commit()

    return send_file(
        zip_stream,
        as_attachment=True,
        download_name=zip_filename,
        mimetype="application/zip"
    )

from openpyxl import load_workbook
from werkzeug.utils import secure_filename

@app.route("/importar_excel_familias", methods=["POST"])
@login_requerido_admin
def importar_excel_familias():
    archivo = request.files.get("excelFile")
    if not archivo or not archivo.filename.endswith(".xlsx"):
        flash("❌ Formato no válido. Asegúrate de subir un archivo .xlsx", "error")
        return redirect(url_for("panel_admin"))

    try:
        wb = load_workbook(filename=archivo)
        hoja = wb.active

        filas_insertadas = 0
        for fila in hoja.iter_rows(min_row=2, values_only=True):
            nombre, correo, password, puntos = fila

            if not nombre or not correo or not password:
                continue  # ignora filas incompletas

            # Verifica que no exista ya
            existente = Familia.query.filter_by(correo=correo).first()
            if existente:
                continue

            nueva_familia = Familia(
                nombre=nombre,
                correo=correo,
                password=password,
                puntos=int(puntos) if puntos else 0
            )
            db.session.add(nueva_familia)
            filas_insertadas += 1

        db.session.commit()
        flash(f"✅ Se importaron {filas_insertadas} familias correctamente.", "success")
        return redirect(url_for("panel_admin"))

    except Exception as e:
        print(f"[ERROR] Al importar Excel: {e}")
        flash("❌ Hubo un error al procesar el archivo.", "error")
        return redirect(url_for("panel_admin"))
