# Auditoría de seguridad — Cuponera Escolar

## Hallazgo principal corregido

La aplicación sufría una referencia directa insegura a objetos (IDOR/BOLA). La ruta
`/familia/<familia_id>/ver` aceptaba cualquier ID y consultaba directamente esa familia
sin exigir autenticación ni comprobar que la sesión fuera su propietaria. Cambiar el
número de la URL exponía nombre, puntos e historial de otra familia.

Se añadió una política central: el personal autorizado puede consultar familias para
realizar su trabajo; una cuenta familiar únicamente puede acceder al ID guardado en su
propia sesión. Una sesión de otra familia recibe HTTP 403 y una persona sin sesión es
enviada al inicio de sesión.

## Riesgos adicionales corregidos

- Los historiales JSON y CSV, la página familiar y sus QR tenían el mismo IDOR.
- Varias rutas públicas permitían sumar, canjear o penalizar puntos.
- Una ruta pública permitía registrar asistencia indicando evento y familia.
- Las operaciones de creación, edición y eliminación no aplicaban roles uniformes.
- `GET /familias` entregaba la contraseña de cada familia junto con sus datos.
- Los QR familiares se guardaban bajo `/static/qr`, con nombres enumerables.
- Existían valores secretos predeterminados dentro del código fuente.
- Las cookies de sesión no declaraban explícitamente `HttpOnly`, `SameSite` y `Secure`.

## Controles implementados

- Decoradores reutilizables para familia propietaria, administrador y supervisor.
- Autorización aplicada tanto a páginas como a APIs, exportaciones y mutaciones.
- Separación limpia de sesiones al iniciar sesión como administrador o familia.
- Las contraseñas familiares permanecen visibles y recuperables por correo por decisión
  operativa del colegio. Esta excepción no permite consultarlas mediante APIs públicas.
- QR familiares en `instance/private_qr`, servidos solo tras autorización.
- Bloqueo explícito de las URLs antiguas `/static/qr/...`.
- `SECRET_KEY` obligatoria mediante variable de entorno y contraseña SMTP sin fallback.
- Pruebas de regresión de propiedad, roles, mutaciones, exposición de contraseñas y QR.

## Configuración necesaria al desplegar

Render debe conservar `SECRET_KEY` y `MAIL_PASSWORD` como variables de entorno. Para
producción HTTPS, deja `SESSION_COOKIE_SECURE=true` (valor predeterminado). En desarrollo
local por HTTP puede usarse `SESSION_COOKIE_SECURE=false`.

Después de desplegar, usa “Generar QR pendientes” una vez si necesitas reconstruir los
PNG privados. Los QR existentes siguen apuntando a las mismas rutas y versiones; el
flujo operativo no cambia.

## Verificación

La aplicación importa correctamente y registra 76 rutas. La suite incluida en
`tests/test_security_access.py` valida seis escenarios críticos de autorización.
