# Echando Chal POS 1.1.0 | Parche de actualización de producción

**Tipo:** instalador de actualización sobre la aplicación existente (no instalación desde cero).
**Código:** rama `release/1.1.0`, congelada desde las mejoras validadas de `fix/checkout-amount-fields`.
**Compatibilidad:** Windows x64; mismo AppId Inno Setup que la versión de producción.
**Datos:** el instalador nunca incluye una base de datos, respaldos, pruebas ni configuración operativa.

## Contenido de la actualización

- Nueva Venta: cantidades finales por renglón, descuento sin flechas y con limpieza de captura; retirada de Venta voluminosa; búsqueda predictiva con código, nombre, marca, categoría, color y unidad.
- Nueva Venta: solicitud rápida para imprimir u omitir recibo al registrar el cobro, con Enter/I para imprimir y C/Esc/cerrar para omitir.
- Historial de ventas: visor de ticket PDF integrado, con impresión desde la aplicación.
- Productos: sugerencias a partir de un nombre existente para categoría, marca, unidad, costo, precio, mínimo y proveedor; campos numéricos de captura directa y prevención de duplicados por nombre + categoría + marca + color + unidad.
- Nueva Compra: coincidencias de búsqueda con código, nombre, marca, categoría, color y unidad.
- Se conservan todas las funcionalidades previas de compras, ventas, reportes, respaldos y cortes.

**Validación pendiente:** la impresión física inmediatamente después de confirmar una venta aún no ha sido probada por el usuario. El cobro queda registrado independientemente de esa impresión. Verificarla antes de utilizarla de forma rutinaria.

## Antes de instalar: respaldo obligatorio

1. Cerrar Echando Chal POS después de crear un **respaldo desde Configuración**. Guardarlo fuera de la carpeta del programa, por ejemplo en una memoria USB o carpeta permanente independiente.
2. Verificar que el respaldo no esté vacío y que pueda consultarse o validarse; conservar una copia adicional.
3. Confirmar cuál es la **base de producción real**; no usar la base ni el perfil aislado de pruebas.
4. Cerrar todas las ventanas de Echando Chal POS antes de ejecutar el instalador.

## ¿Dónde están los datos?

- Instalación estándar: `%LOCALAPPDATA%\Programs\EchandoChalPOS`
- Configuración persistente: `%LOCALAPPDATA%\EchandoChalPOS\data-location.json`
- Base antigua (si aún no se migró): `%LOCALAPPDATA%\Programs\EchandoChalPOS\data\echandochal.db`
- Base nueva: `echandochal.db` en la carpeta externa indicada dentro de `data-location.json`.

**Caso A: ya existe `data-location.json` con una carpeta externa válida.** Comprueba la ruta y que corresponde a la base que usas en producción. Tras hacer el respaldo, puedes ejecutar el instalador de actualización.

**Caso B: la base de producción todavía está dentro de la instalación y NO existe `data-location.json`.** El instalador se detiene para proteger la información. No borres ni muevas la base. Antes de instalar:

1. Extrae `EchandoChalPOS-Portable-1.1.0.zip` en una carpeta diferente de la instalación, por ejemplo `D:\EchandoChalPOS_Migracion`.
2. Abre el ejecutable portable **sin cambiar `LOCALAPPDATA`**. En el asistente de ubicación de datos, selecciona «Conservar y migrar la base de datos existente», busca el `echandochal.db` de la instalación anterior y elige una carpeta de datos permanente externa, por ejemplo `D:\DatosEchandoChal`.
3. La migración hace una copia coherente con SQLite, verifica la integridad y la cantidad de productos, ventas y compras, y escribe `data-location.json`. **No borra la base anterior.**
4. Verifica que abre el catálogo real y los historiales. Cierra la aplicación portable y ejecuta el instalador. La base anterior se conserva como copia de seguridad adicional, sin ser utilizada por la nueva versión.

Si ya existe un archivo de configuración pero su ruta es incorrecta, detén la actualización hasta corregirla. La nueva aplicación **no crea una base vacía por accidente** cuando la ruta configurada falta.

## Instalación

1. Descarga el artefacto del flujo `Construir instalador de Windows` de la rama `release/1.1.0`.
2. Extrae el ZIP del artefacto. Comprueba la suma SHA-256 con `SHA256SUMS.txt`.
3. Ejecuta `EchandoChalPOS-Setup-1.1.0.exe` con la aplicación cerrada.
4. El mismo AppId de Inno Setup actualiza el programa y mantiene los accesos directos. No desinstales la versión anterior ni elimines datos.
5. Abre la aplicación y comprueba que se conservan productos, existencias, ventas, compras, cortes, reportes, y la configuración de ticket.
6. Realiza las pruebas de caja y de impresión en una operación controlada.

## Archivos de entrega

- `EchandoChalPOS-Setup-1.1.0.exe` (actualización sobre producción).
- `EchandoChalPOS-Portable-1.1.0.zip` (ensayos o migración asistida).
- `SHA256SUMS.txt` (integridad del instalador).
- `INSTRUCCIONES_ACTUALIZACION.md` (este documento).

## Restricciones y recuperación

No reemplazar, limpiar, restaurar ni crear bases de producción como parte de la instalación. Los scripts de reinicio de la base de pruebas **no forman parte del instalador**. No ejecutar el instalador si el respaldo o la ubicación de los datos son dudosos.

Si hubiera un problema, cerrar la aplicación y conservar tanto la base externa como el respaldo anterior. No instalar una versión antigua sobre una base migrada ni restaurar sin revisar compatibilidad; validar primero la recuperación sobre una copia.
