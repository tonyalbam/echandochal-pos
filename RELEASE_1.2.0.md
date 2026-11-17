# Echando Chal POS v1.2.0 | Parche de actualización de producción

**Entrega:** `EchandoChalPOS-Setup-1.2.0.exe` (Windows x64).  
**Origen:** mejoras verificadas en `feature/servicios-sin-inventario`.  
**Rama del paquete:** `release/1.2.0`.  
**Tipo:** instalación encima de Echando Chal POS v1.1.0, sin desinstalar ni crear una base vacía.

## Novedades de v1.2.0

- **Productos y servicios:** altas de Clases, Talleres, Costura y Otros servicios, sin existencias, unidad, color ni proveedor. Cada servicio tiene precio al cliente y utilidad bruta configurables.
- **Venta mixta:** productos físicos y servicios se pueden cobrar juntos. Los servicios no consumen inventario; las cancelaciones de ventas mixtas solo devuelven mercancía física.
- **Conversión opcional de «Clase»:** desde Productos > Editar, cambiar Tipo a Servicio > Clases, confirmar la reclasificación y conservar el historial y código. No se convierte ningún registro automáticamente.
- **Alta de productos:** sugerencias de marcas previamente registradas conforme se teclea.
- **Stock bajo / agotado:** amarillo cuando la existencia es positiva y está en o debajo del mínimo; marrón cuando es cero.
- **Identidad gráfica:** ícono de Echando Chal en el ejecutable, los accesos directos y la ventana.
- **Interfaz:** ventana principal maximizada al iniciar y versión `v1.2.0` visible en la esquina inferior izquierda.

Se conservan las funcionalidades ya disponibles en v1.1.0, incluidas las ventas, compras, descuentos, reportes y tickets.

## Antes de instalar (obligatorio)

1. En la **aplicación de producción**, haz un respaldo con Configuración y guárdalo **fuera** de la carpeta de instalación. Conserva una segunda copia independiente.
2. Verifica que puedes localizar y abrir el archivo de respaldo. No utilices un perfil o base de pruebas como origen del respaldo productivo.
3. Comprueba que el archivo de configuración `%LOCALAPPDATA%\EchandoChalPOS\data-location.json` existe y apunta a una carpeta externa **con la base de datos de producción real** (`echandochal.db`). No alteres ni borres ese archivo.
4. Cierra por completo Echando Chal POS y otras instancias que pudieran tener abierta la base.

**Protección para instalaciones anteriores:** si el instalador detecta bases o respaldos dentro de la carpeta anterior del programa y no existe una configuración de datos externa, **se detendrá sin actualizar**. Si ocurre, conserva los datos originales y sigue el procedimiento de migración de `RELEASE_1.1.0.md` antes de reintentar. No desinstales la aplicación ni elimines manualmente el archivo `echandochal.db`.

## Instalación sobre v1.1.0

1. Abre el enlace de **GitHub Actions** proporcionado con el parche. Dentro de **Artifacts**, descarga `EchandoChalPOS-v1.2.0-Windows`. GitHub puede requerir iniciar sesión.
2. Extrae el ZIP descargado. En su interior encontrarás:
   - `EchandoChalPOS-Setup-1.2.0.exe`: instalador de actualización.
   - `EchandoChalPOS-Portable-1.2.0.zip`: ejecutable portable de apoyo, no debe colocarse dentro de la instalación existente.
   - `SHA256SUMS.txt`: huella digital para comprobar la descarga del instalador.
   - `INSTRUCCIONES_ACTUALIZACION.md`: estas instrucciones.
3. Opcional, para verificar integridad: abre PowerShell en la carpeta de los archivos y ejecuta `Get-FileHash .\EchandoChalPOS-Setup-1.2.0.exe -Algorithm SHA256`. Compara el resultado con `SHA256SUMS.txt`.
4. Ejecuta `EchandoChalPOS-Setup-1.2.0.exe` **con el programa cerrado**. Usa la carpeta de instalación existente y completa el asistente. El instalador conserva el mismo **AppId** de producción para actualizar en el mismo lugar.
5. No borres datos, no restaures un respaldo y no inicialices una base nueva como parte de la actualización.

## Verificación después de instalar

1. Confirma que abre **maximizado**, muestra el nuevo **ícono** y la etiqueta **v1.2.0** abajo a la izquierda.
2. Comprueba que siguen presentes los productos, proveedores, existencias, compras, ventas, cortes, configuración e informes anteriores.
3. Verifica el valor de inventario y las alertas de stock bajo. No reclasifiques un artículo histórico hasta tener confirmado el respaldo.
4. Si existe el antiguo producto «Clase», conviértelo explícitamente en **Servicio > Clases** desde Editar y confirma el cambio de existencias. Este ajuste reduce el inventario ficticio **sin borrar ventas históricas**. Comprueba de nuevo el valor del inventario.
5. Registra y revisa una operación controlada con un servicio y un producto físico para verificar totales, utilidad y existencias.
6. La **impresión física inmediata después del cobro** debe verificarse en la impresora de la tienda si todavía no se había probado con la versión anterior.

## Seguridad y recuperación

El paquete **no incluye bases de datos, respaldos ni registros de prueba**. La configuración de datos y la base productiva viven en una ubicación externa a la carpeta del programa. La migración del esquema SQLite es automática al abrir la nueva versión, por lo que es importante conservar el respaldo previo.

Si algo no funciona, cierra la aplicación y conserva la base y sus copias. No instales una versión anterior sobre una base ya migrada ni restaures en producción antes de verificar una recuperación sobre una **copia aislada**.

**Importante:** crear este instalador en GitHub no instala ni modifica nada en tu equipo. La instalación solo ocurre cuando tú ejecutas el archivo `.exe`.
