from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash, Response
from app import app, db
from app.models import Familia, MovimientoPuntos, Transaccion, Admin, Beneficio
from datetime import datetime
import csv, unicodedata
from io import BytesIO, TextIOWrapper
from werkzeug.security import check_password_hash
from flask import send_file, url_for
import qrcode
import os
from flask import send_file
from app.models import EventoQR, EventoQRRegistro


@app.route('/admin')
def panel_admin():
    if 'admin' not in session:
        return redirect(url_for('login'))

    familias = Familia.query.all()
    eventos = EventoQR.query.all()  # 👈 agregar esta línea
    return render_template('admin.html', familias=familias, eventos=eventos)  # 👈 pasar eventos


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')

        admin = Admin.query.filter_by(usuario=usuario).first()
        if admin and admin.verificar_password(password):
            session['admin'] = admin.usuario  # Guardamos la sesión
            return redirect(url_for('panel_admin'))
        else:
            return render_template('login.html', error="Usuario o contraseña incorrectos")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))


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
    return render_template('index.html')

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
    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    tipo = request.form.get('tipo')
    puntos = int(request.form.get('puntos'))
    descripcion = request.form.get('descripcion')

    if tipo not in ['suma', 'canje']:
        return "Tipo de transacción no válido", 400

    if tipo == 'canje':
        puntos = -abs(puntos)  # Asegura que sea negativo

    transaccion = Transaccion(
        familia_id=familia_id,
        tipo=tipo,
        puntos=puntos,
        descripcion=descripcion
    )

    familia.puntos += puntos
    db.session.add(transaccion)
    db.session.commit()

    return redirect(url_for('ver_familia', familia_id=familia_id))


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
    if 'admin' not in session:
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
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    administradores = Admin.query.all()
    return render_template('lista_administradores.html', administradores=administradores) 

@app.route('/admin/usuarios/eliminar/<int:admin_id>', methods=['POST'])
def eliminar_administrador(admin_id):
    if 'admin' not in session:
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
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template('escanear.html')



@app.route('/familia/<int:familia_id>/qr')
def generar_qr(familia_id):
    familia = Familia.query.get(familia_id)
    if not familia:
        return "Familia no encontrada", 404

    # URL que irá dentro del QR
    data = url_for('ver_familia', familia_id=familia_id, _external=True)

    # Generar QR
    qr = qrcode.make(data)

    # Ruta absoluta al directorio raíz del proyecto
    root_path = os.path.abspath(os.path.dirname(__file__))  # app/
    project_root = os.path.abspath(os.path.join(root_path, '..'))
    temp_folder = os.path.join(project_root, 'temp')
    os.makedirs(temp_folder, exist_ok=True)

    filename = f'temp_qr_familia_{familia_id}.png'
    filepath = os.path.join(temp_folder, filename)

    qr.save(filepath)

    return send_file(filepath, mimetype='image/png')

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

@app.route('/login_familia', methods=['GET', 'POST'])
def login_familia():
    if request.method == 'POST':
        correo = request.form.get('correo')
        password = request.form.get('password')

        familia = Familia.query.filter_by(correo=correo).first()
        if familia and familia.password == password:
            session['familia_id'] = familia.id
            return redirect(url_for('perfil_familia', familia_id=familia.id))
        else:
            return render_template('login_familia.html', error="Credenciales incorrectas")

    return render_template('login_familia.html')


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

    return render_template('perfil_familia.html', familia=familia, transacciones=transacciones, beneficios=beneficios)


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

@app.route('/generar_qr_prueba/<int:familia_id>')
def generar_qr_prueba(familia_id):
    import qrcode
    import os

    # Ruta a la carpeta qr dentro de static
    qr_folder = os.path.join(current_app.root_path, 'static', 'qr')
    os.makedirs(qr_folder, exist_ok=True)

    # URL que irá en el QR
    data = url_for('escanear_qr_suma', familia_id=familia_id, _external=True)

    # Crear el código QR
    qr_img = qrcode.make(data)
    qr_filename = f'qr_prueba_familia_{familia_id}.png'
    qr_path = os.path.join(qr_folder, qr_filename)

    qr_img.save(qr_path)

    return send_file(qr_path, mimetype='image/png')

@app.route('/admin/crear_qr_evento', methods=['GET', 'POST'])
def crear_qr_evento():
    if 'admin' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre = request.form['nombre_evento']
        puntos = int(request.form['puntos'])

        evento = EventoQR(nombre_evento=nombre, puntos=puntos, qr_filename="temporal.png")
        db.session.add(evento)
        db.session.commit()

# Luego generar el QR con el ID del evento (que ya tienes porque hiciste commit)
        qr_filename = f"qr_evento_{evento.id}.png"
        evento.qr_filename = qr_filename
        db.session.commit()
        # Crear QR con URL para escaneo
        url_qr = url_for('escanear_evento_qr', evento_id=evento.id, _external=True)
        qr = qrcode.make(url_qr)

        ruta_qr = os.path.join('app', 'static', 'qr_eventos')
        os.makedirs(ruta_qr, exist_ok=True)
        filename = f'evento_{evento.id}.png'
        path_completo = os.path.join(ruta_qr, filename)
        qr.save(path_completo)

        evento.qr_filename = filename
        db.session.commit()

        flash('Código QR de evento creado', 'exito')
        return redirect(url_for('panel_admin'))

    return render_template('crear_qr_evento.html')

@app.route('/escanear_evento/<int:evento_id>')
def escanear_evento_qr(evento_id):
    familia_id = session.get('familia_id')
    if not familia_id:
        return redirect(url_for('login_familia'))

    evento = EventoQR.query.get(evento_id)
    if not evento:
        return "Evento no encontrado", 404

    ya_escaneo = EventoQRRegistro.query.filter_by(familia_id=familia_id, evento_id=evento_id).first()
    if ya_escaneo:
        return "Ya escaneaste este evento", 400

    familia = Familia.query.get(familia_id)
    familia.puntos += evento.puntos
    db.session.add(EventoQRRegistro(familia_id=familia_id, evento_id=evento_id))
    db.session.commit()

    return f"¡Has ganado {evento.puntos} puntos por el evento {evento.nombre_evento}!"

@app.route('/admin/crear_beneficio', methods=['GET', 'POST'])
def crear_beneficio():
    if 'admin' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        puntos = request.form.get('puntos')

        if not nombre or not puntos:
            flash("Todos los campos son obligatorios", "error")
            return redirect(url_for('crear_beneficio'))

        beneficio = Beneficio(nombre=nombre, puntos_requeridos=int(puntos))
        db.session.add(beneficio)
        db.session.commit()
        flash("Beneficio creado correctamente", "success")
        return redirect(url_for('panel_admin'))

    return render_template('crear_beneficio.html')