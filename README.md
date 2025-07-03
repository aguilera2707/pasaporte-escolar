# Cuponera Escolar

Este proyecto es una aplicación Flask para administrar familias, eventos con QR y beneficios canjeables. Incluye roles de administrador y supervisor para gestionar las principales funcionalidades.

## Requisitos

- Python 3
- Dependencias listadas en `requirements.txt`:

```
flask
flask_sqlalchemy
flask_cors
python-dotenv
```

## Instalación

1. Crear un entorno virtual y activarlo:

```bash
python -m venv venv
source venv/bin/activate
```

2. Instalar las dependencias:

```bash
pip install -r requirements.txt
```

## Inicializar la base de datos

Antes de ejecutar la aplicación es necesario crear las tablas ejecutando las migraciones:

```bash
flask db upgrade
```

## Ejecución

Para iniciar el servidor Flask ejecute `main.py`:

```bash
python main.py
```

La aplicación quedará disponible en `http://localhost:5000` en modo desarrollo.

## Funcionalidades

- **Gestión de familias**: registro, listado y manejo de puntos por transacciones.
- **Eventos con códigos QR**: creación de eventos y registro de asistencia mediante QR generados para cada evento.
- **Beneficios**: listado de recompensas que pueden canjearse con puntos acumulados.
- **Roles de administrador**: usuarios con rol de administrador o supervisor que acceden a secciones protegidas para administrar familias, eventos y beneficios.

