# Sesiones y credenciales de prueba de SGAP

Esta guía sirve para ejecutar SGAP localmente e iniciar sesión con cada uno de los roles de prueba.

## Preparar el proyecto

Desde PowerShell, dentro de la carpeta del proyecto:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py create_demo_users
python manage.py runserver
```

Abre <http://127.0.0.1:8000/> en el navegador. Si `python` no corresponde a tu instalación de Python, puedes usar `py` en su lugar.

## Cuentas de prueba

Las tres cuentas comparten la contraseña local `demo123`.

| Rol | Correo electrónico | Contraseña |
|---|---|---|
| Solicitante | `solicitante@sgap.local` | `demo123` |
| Aprobador | `aprobador@sgap.local` | `demo123` |
| Administrador | `admin@sgap.local` | `demo123` |

Cada rol tiene su propio panel y permisos. Para pasar a otro rol, usa **Cambiar sesión** en la barra superior; se cierra la sesión actual y puedes iniciar con otra cuenta. **Cerrar sesión** también termina la sesión.

## Áreas y tipos de solicitud disponibles

Con el rol **Solicitante**, selecciona **Nueva solicitud** para pedir autorización en uno de los procedimientos habilitados. La instalación incluye estas opciones:

| Área o procedimiento | Datos que solicita el formulario |
|---|---|
| Compra de materiales | Materiales requeridos y monto estimado |
| Viáticos | Destino, fechas del viaje y monto estimado |
| Permisos | Motivo y fecha(s) solicitada(s), seleccionada(s) en calendario |
| Acceso a áreas restringidas | Área, motivo y fecha y hora, seleccionadas en calendario |

Completa todos los campos para enviar la solicitud. Las fechas y horas se validan en el servidor; las fechas inválidas muestran un error en el formulario. La fecha y hora seleccionadas quedan visibles en el detalle de la solicitud, separadas de la fecha de envío. El **Aprobador** puede revisar las solicitudes pendientes y aprobarlas o rechazarlas; al rechazar, puede escribir un motivo, pero es opcional. Cuando el aprobador resuelve una solicitud, el solicitante recibe un aviso la próxima vez que abra su panel; el aviso aparece una sola vez. El **Administrador** puede habilitar o deshabilitar procedimientos y agregar otros desde **Procedimientos**; solo los habilitados aparecen para los solicitantes.

### Áreas restringidas disponibles

En el procedimiento **Acceso a áreas restringidas**, selecciona el lugar al que necesitas acceder en la lista **Área**:

- Bodega o almacén
- Sala de servidores / TI
- Archivo
- Laboratorio
- Taller
- Oficina de administración
- Sala eléctrica
- Planta de producción

En **Fecha y hora**, usa los selectores de fecha y hora del formulario.

## Cómo se crea una sesión

No es necesario crear la sesión manualmente: Django la inicia cuando una cuenta autenticada accede mediante **Iniciar sesión**. Los botones **Cambiar sesión** y **Cerrar sesión** terminan la sesión actual; **Cambiar sesión** te lleva al formulario para entrar con otra cuenta. La sesión queda asociada al navegador y a la base de datos local `db.sqlite3`.

Para volver a crear las cuentas de prueba, ejecuta:

```powershell
python manage.py create_demo_users
```

El comando puede ejecutarse más de una vez: conserva las cuentas existentes sin cambiar sus contraseñas. Solo funciona cuando `DEBUG` está habilitado.

> **Importante:** `demo123` es una contraseña pública de demostración. Úsala únicamente en desarrollo local; no uses estas cuentas ni esta contraseña en producción.
