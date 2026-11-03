# Echando Chal POS 1.0.0

Versión final preparada para Windows.

## Funcionalidades
- Ventas con cobro mixto por operación.
- Recepción rápida y etiquetas Code 128/QR en PDF o Word.
- Eliminación lógica de productos sin alterar sus historiales.
- Categorías y unidades personalizables.
- Interfaz clara/oscura siguiendo la configuración de Windows.
- Dashboard con analítica anual, utilidades acumuladas, top 5 y antigüedad.
- Ordenamiento ascendente/descendente mediante doble clic en encabezados.
- Respaldos diarios y restauración con copia de seguridad previa.

## Reglas para la entrega
- El instalador no debe contener bases de datos ni respaldos.
- Las bases existentes se conservan en carpetas externas independientes de la instalación.
- Si existen datos antiguos dentro de la carpeta del programa, se bloquea la actualización.
- Comprobar el instalador y la base en un entorno de pruebas antes de instalar en producción.

## Artefactos
- `EchandoChalPOS-Setup-1.0.0.exe`
- `EchandoChalPOS-Portable-1.0.0.zip`

Compilación: GitHub Actions, workflow *Construir instalador de Windows*.
