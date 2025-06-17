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
def panel_admin():
    if "admin_id" not in session:
        return redirect(url_for("login"))

    eventos = EventoQR.query.order_by(EventoQR.id.desc()).all()
    familias = Familia.query.all()  # ← ESTO ES CLAVE
    ultimo_evento = eventos[0] if eventos else None
    otros_eventos = eventos[1:] if len(eventos) > 1 else []

    return render_template(
        "admin.html",
        eventos=eventos,
        familias=familias,
        ultimo_evento=ultimo_evento,
        otros_eventos=otros_eventos
    )



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        admin = Admin.query.filter_by(usuario=usuario).first()
        if admin and admin.verificar_password(password):
            session["admin_id"] = admin.id
            return redirect(url_for("panel_admin"))
        else:
            flash("Credenciales inválidas para administrador", "error")
            return render_template("login_unificado.html", active_tab="admin")
    return render_template("login_unificado.html", active_tab="admin")



@app.route('/logout')
def logout():
    session.pop('admin', None)
    return render_template('login_unificado.html')


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
    
@app.route('/transaccion', methods=['POST'])
def registrar_transaccion():
    data = request.get_json()
    familia_id = data.get('familia_id')
    puntos = data.get('puntos')
    tipo = data.get('tipo')
    descripcion = data.get('descripcion')

    # Obtener la familia
    familia = Familia.query.get(familia_id)
    if not familia:
        return jsonify({'error': 'Familia no encontrada'}), 404

    # Validar tipo
    if tipo not in ['suma', 'canje']:
        return jsonify({'error': 'Tipo inválido. Usa "suma" o "canje"'}), 400

    # Validar puntos para canje
    if tipo == 'canje' and familia.puntos < puntos:
        return jsonify({'error': 'Puntos insuficientes'}), 400

    # Crear y guardar la transacción
    transaccion = Transaccion(
        familia_id=familia_id,
        tipo=tipo,
        puntos=puntos,
        descripcion=descripcion
    )
    db.session.add(transaccion)

    # Actualizar puntos de la familia
    if tipo == "suma":
        familia.puntos += puntos
    elif tipo == "canje":
        familia.puntos -= puntos

    db.session.commit()

    return jsonify({
        'mensaje': 'Transacción registrada correctamente',
        'puntos_actuales': familia.puntos
    }), 200
    
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

    # Ejecutar consulta y ordenar por fecha descendente
    transacciones = query.order_by(Transaccion.fecha.desc()).all()

    return render_template('familia.html', familia=familia, transacciones=transacciones)



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

    transaccion = Transaccion(
        familia_id=familia_id,
        tipo=tipo,
        puntos=puntos_finales,
        descripcion=descripcion,
        fecha=datetime.utcnow() - timedelta(hours=6)
    )

    familia.puntos += puntos_finales
    db.session.add(transaccion)
    db.session.commit()

    return jsonify({"mensaje": "Transacción registrada correctamente"}), 200



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

        if not usuario or not password:
            flash("Todos los campos son obligatorios", "error")
            return render_template("crear_admin.html")

        if Admin.query.filter_by(usuario=usuario).first():
            flash("Ese usuario ya existe", "error")
            return render_template("crear_admin.html")

        nuevo_admin = Admin(usuario=usuario)
        nuevo_admin.set_password(password)
        db.session.add(nuevo_admin)
        db.session.commit()

        flash("Administrador creado correctamente", "exito")
        return redirect(url_for('crear_admin'))

    return render_template("crear_admin.html")

@app.route('/admin/usuarios')
def lista_administradores():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    
    administradores = Admin.query.all()
    return render_template('lista_administradores.html', administradores=administradores) 

@app.route('/admin/usuarios/eliminar/<int:admin_id>', methods=['POST'])
def eliminar_administrador(admin_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    admin = Admin.query.get(admin_id)

    if not admin:
        flash("Administrador no encontrado", "error")
    elif admin.usuario == session['admin']:
        flash("No puedes eliminar tu propia cuenta", "error")
    else:
        db.session.delete(admin)
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
    beneficios = Beneficio.query.all()
    ultimo_evento = EventoQR.query.order_by(EventoQR.id.desc()).first()  # 🔹 nuevo

    return render_template(
        'perfil_familia.html',
        familia=familia,
        transacciones=transacciones,
        beneficios=beneficios,
        ultimo_evento=ultimo_evento  # 🔹 nuevo
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
        fecha=datetime.utcnow() - timedelta(hours=6)
    )
    db.session.add(transaccion)
    db.session.commit()

    return jsonify({"mensaje": f"Asistencia registrada correctamente. Se sumaron {evento.puntos} puntos a {familia.nombre}"}), 200


from app.models import LugarFrecuente  # asegúrate de importarlo

@app.route('/admin/crear_qr_evento', methods=['GET', 'POST'])
def crear_qr_evento():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    lugares = LugarFrecuente.query.all()
    eventos = EventoQR.query.order_by(EventoQR.id.desc()).all()

    if request.method == 'POST':
        nombre_evento = request.form['nombre_evento']
        puntos = int(request.form['puntos'])
        latitud = float(request.form['latitud'])
        longitud = float(request.form['longitud'])

        evento = EventoQR(
            nombre_evento=nombre_evento,
            puntos=puntos,
            latitud=latitud,
            longitud=longitud
        )

        db.session.add(evento)
        db.session.flush()  # Para obtener el ID sin hacer commit

        qr_data = url_for('escanear_evento_con_ubicacion', evento_id=evento.id, _external=True)
        qr_img = qrcode.make(qr_data)

        qr_filename = f"evento_{evento.id}.png"
        qr_path = os.path.join('app', 'static', 'qr_eventos', qr_filename)
        os.makedirs(os.path.dirname(qr_path), exist_ok=True)
        qr_img.save(qr_path)

        evento.qr_filename = qr_filename
        db.session.commit()

        flash('Evento QR creado con éxito.', 'success')
        return redirect(url_for('crear_qr_evento'))

    return render_template('crear_qr_evento.html', lugares=lugares, eventos=eventos)



@app.route('/escanear_evento/<int:evento_id>')
def escanear_evento_con_ubicacion(evento_id):
    evento = EventoQR.query.get_or_404(evento_id)
    return render_template('escanear_evento_con_ubicacion.html', evento=evento)

from geopy.distance import geodesic


@app.route('/validar_ubicacion_evento', methods=["POST"])
def validar_ubicacion_evento():
    print("🔍 Recibiendo petición de validación de ubicación")
    data = request.get_json()
    lat = data.get("lat")
    lon = data.get("lon")
    evento_id = data.get("evento_id")
    familia_id = session.get("familia_id")

    if not lat or not lon or not familia_id:
        return jsonify({"error": "Faltan datos o no estás logueado"}), 400

    evento = EventoQR.query.get(evento_id)
    familia = Familia.query.get(familia_id)

    if not evento or not familia:
        return jsonify({"error": "Datos inválidos"}), 404

    distancia = geodesic((evento.latitud, evento.longitud), (lat, lon)).meters
    print(f"📍 Distancia calculada: {distancia:.2f} metros")

    if distancia > 500:
        return jsonify({"redirect": url_for("ubicacion_invalida", evento_id=evento.id)})

    ya_registrado = EventoQRRegistro.query.filter_by(evento_id=evento.id, familia_id=familia.id).first()
    if ya_registrado:
        return jsonify({"redirect": url_for("asistencia_exitosa", evento_id=evento.id, ya_asistio=1)})

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

@app.route('/validar_qr_evento', methods=["POST"])
def validar_qr_evento():
    data = request.get_json()
    qr_url = data.get("qr_url")
    familia_id = session.get("familia_id")

    if not qr_url or not familia_id:
        return jsonify({"error": "Faltan datos"}), 400

    # Extraer evento_id desde la URL del QR
    from urllib.parse import urlparse
    import re

    parsed_url = urlparse(qr_url)
    match = re.search(r'/escanear_evento/(\d+)', parsed_url.path)

    if not match:
        return jsonify({"error": "No se pudo extraer el ID del evento"}), 400

    evento_id = int(match.group(1))
    evento = EventoQR.query.get(evento_id)
    familia = Familia.query.get(familia_id)

    if not evento or not familia:
        return jsonify({"error": "Evento o familia no encontrada"}), 404

    ya_registrado = EventoQRRegistro.query.filter_by(evento_id=evento.id, familia_id=familia.id).first()
    if ya_registrado:
        return jsonify({"redirect": url_for("asistencia_exitosa", evento_id=evento.id, ya_asistio=1)})

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

# Ruta en routes.py
from flask import render_template, request, redirect, url_for, flash
from app.models import Familia
from app import db

@app.route('/familia/<int:familia_id>/editar', methods=['GET', 'POST'])
def editar_familia(familia_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    familia = Familia.query.get_or_404(familia_id)

    if request.method == 'POST':
        familia.nombre = request.form['nombre']
        familia.correo = request.form['correo']
        familia.password = request.form['password']  # En producción deberías hashearla

        db.session.commit()
        flash('Familia actualizada correctamente', 'success')
        return redirect(url_for('panel_admin'))

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

@app.route('/admin/editar_evento/<int:evento_id>', methods=['GET', 'POST'])
def editar_evento(evento_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    evento = EventoQR.query.get_or_404(evento_id)

    if request.method == 'POST':
        evento.nombre_evento = request.form['nombre_evento']
        evento.puntos = int(request.form['puntos'])
        evento.latitud = float(request.form['latitud'])
        evento.longitud = float(request.form['longitud'])

        db.session.commit()
        flash('Evento actualizado correctamente.', 'success')
        return redirect(url_for('crear_qr_evento'))

    return render_template('editar_evento.html', evento=evento)

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
def eliminar_beneficio(beneficio_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    beneficio = Beneficio.query.get_or_404(beneficio_id)
    db.session.delete(beneficio)
    db.session.commit()
    flash("Beneficio eliminado exitosamente", "success")
    return redirect(url_for('crear_beneficio'))
