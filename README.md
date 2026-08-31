# Echando Chal POS

Sistema de punto de venta de escritorio para Echando Chal, desarrollado con
Python, PySide6 y SQLite.

## Requisitos de desarrollo

- Windows 11
- Python 3.13
- 8 GB de RAM o más

## Ejecutar desde el código

Abre PowerShell dentro de la carpeta del proyecto:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

La información se guarda en `data\echandochal.db`. Los respaldos automáticos
se crean en `backups\automaticos` una vez por día al iniciar el sistema.

## Generar el ejecutable de Windows

Desde PowerShell ejecuta:

```powershell
.\build_windows.ps1
```

El resultado queda en:

```text
dist\EchandoChalPOS\EchandoChalPOS.exe
```

Distribuye la carpeta completa `dist\EchandoChalPOS`; el archivo ejecutable no
debe separarse de la carpeta `_internal`.

Al ejecutar la versión compilada, las carpetas `data` y `backups` se crean junto
al ejecutable. Se recomienda instalarla en una carpeta con permisos de escritura,
por ejemplo `C:\EchandoChalPOS`, y no dentro de `Archivos de programa`.

## Escáner de códigos de barras y QR

El lector debe funcionar en modo **USB HID Keyboard**: el escaneo se comporta
como si el usuario escribiera el contenido con el teclado.

Configuración recomendada del lector:

1. Activar lectura de Code 128 y QR.
2. Configurar el sufijo `Enter` después de cada lectura.
3. Mantener desactivados prefijos adicionales.
4. Probar primero en Bloc de notas: debe escribir un solo valor y bajar de línea.

En **Productos** se pueden registrar el código de barras y el QR que ya incluya
el producto. Ambos valores deben ser únicos. Si el producto no tiene códigos,
selecciona el registro y usa **Generar etiqueta**; la aplicación generará Code
128, QR o ambos utilizando el código interno del producto.

En **Nueva venta**, coloca el cursor en el buscador y escanea. El producto se
agrega cuando el lector envía Enter. También puede buscarse manualmente por
código interno, código de barras, QR, nombre o marca.

## Respaldo y recuperación

- **Respaldo automático:** se ejecuta una vez al día al abrir el sistema.
- **Respaldo manual:** Configuración > Crear respaldo.
- **Restauración:** Configuración > Restaurar respaldo.
- Antes de restaurar se genera una copia adicional del estado actual.

No copies la base de datos activa mientras la aplicación esté abierta. Utiliza
siempre las opciones de respaldo del sistema.

## Validación previa a liberar v1.0.0

- Registrar, editar, buscar y desactivar productos y proveedores.
- Registrar compras y confirmar la actualización de existencias.
- Realizar una venta con formas de pago distintas por producto.
- Escanear un código de barras existente, un QR existente y una etiqueta creada
  por Echando Chal POS.
- Generar y revisar el recibo térmico.
- Validar Dashboard, reportes, corte diario y arqueo de efectivo.
- Crear un respaldo y restaurarlo.
- Cerrar y abrir el ejecutable confirmando que conserva la información.
