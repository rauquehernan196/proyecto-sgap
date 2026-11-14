# SGAP en Django

Aplicación web para gestionar solicitudes y autorizaciones de permisos. Incluye inicio de sesión por correo, perfiles de solicitante/aprobador/administrador, procedimientos configurables, historial auditable y exportación CSV.

## Requisitos

- Python 3.10 o posterior
- Django, instalado desde `requirements.txt`

## Instalación y ejecución en Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abre <http://127.0.0.1:8000/>. Inicia sesión con el correo y la contraseña del superusuario. Para agregar cuentas de cada rol y administrar procedimientos, usa las secciones del panel.

La base de datos local es `db.sqlite3`. No se crean cuentas ni contraseñas de demostración automáticamente. Para producción, configura `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` y `DJANGO_ALLOWED_HOSTS` (dominios separados por comas), y utiliza HTTPS y un servidor de base de datos adecuado.

## Cuentas de prueba locales

Con `DEBUG` habilitado, crea las cuentas de prueba ejecutando:

```powershell
python manage.py create_demo_users
```

| Rol | Correo | Contraseña local |
|---|---|---|
| Solicitante | `solicitante@sgap.local` | `demo123` |
| Aprobador | `aprobador@sgap.local` | `demo123` |
| Administrador | `admin@sgap.local` | `demo123` |

El comando es seguro de repetir y no cambia contraseñas ni modifica usuarios que ya existan. Se niega a crear estas cuentas cuando `DEBUG` está deshabilitado. Son credenciales públicas de demostración: no las uses en producción.

## Pruebas

```powershell
python manage.py test
```
