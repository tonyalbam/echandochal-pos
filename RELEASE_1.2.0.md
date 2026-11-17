# Echando Chal POS v1.2.0 | Actualización candidata

**Estado:** rama de desarrollo y pruebas `feature/servicios-sin-inventario`; no desplegada en producción.

Esta versión incorpora los cambios de la v1.1.0 más las siguientes mejoras:

- Productos físicos y servicios diferenciados. Servicios como Clases, Talleres, Costura y Otros no usan inventario, color, unidad ni proveedor; admiten precio al cliente y utilidad bruta.
- Posibilidad de vender servicios junto con productos físicos y cancelar ventas mixtas sin añadir existencias de servicios.
- Conversión manual de productos anteriores a servicios con historial conservado.
- Sugerencias predictivas de marcas registradas en Nuevos Productos.
- Colores de inventario: stock bajo amarillo y agotado marrón.
- Ícono Echando Chal 3D con transparencia en ejecutable, accesos directos y ventana.
- Ventana principal maximizada desde el inicio.
- Pie de página con la versión real `v1.2.0`.

## Requisitos antes de actualizar

1. Respaldar y verificar la base de datos de producción fuera de la carpeta del programa.
2. Verificar la ubicación de datos externa `%LOCALAPPDATA%\\EchandoChalPOS\\data-location.json`.
3. No instalar sobre la base de pruebas. Cerrar el programa antes de instalar.
4. Confirmar que se conserva el historial y que los servicios no aparecen en el valor de inventario.
5. Probar en el entorno aislado y validar las funciones de impresión física antes de usar en caja.

La compilación deberá usar `APP_VERSION` en `app/version.py` para mostrar y etiquetar la misma versión en el programa e instalador. El archivo ejecutable y el paquete de instalación no incluyen bases de datos.
