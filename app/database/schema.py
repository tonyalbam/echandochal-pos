from .connection import Database


def create_database(db: Database) -> None:
    cursor = db.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            correo TEXT,
            notas TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            codigo_barras TEXT UNIQUE,
            nombre TEXT NOT NULL,
            categoria_id INTEGER,
            marca TEXT,
            color TEXT,
            unidad TEXT NOT NULL DEFAULT 'pieza',
            costo REAL NOT NULL DEFAULT 0,
            precio REAL NOT NULL DEFAULT 0,
            existencia REAL NOT NULL DEFAULT 0,
            stock_minimo REAL NOT NULL DEFAULT 0,
            proveedor_id INTEGER,
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (categoria_id)
                REFERENCES categorias(id),

            FOREIGN KEY (proveedor_id)
                REFERENCES proveedores(id)
        );

        CREATE TABLE IF NOT EXISTS historial_precios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            precio_compra REAL NOT NULL,
            precio_venta REAL NOT NULL,
            fecha_inicio TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_fin TEXT,

            FOREIGN KEY (producto_id)
                REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT NOT NULL UNIQUE,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            subtotal REAL NOT NULL DEFAULT 0,
            descuento REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            metodo_pago TEXT NOT NULL,
            porcentaje_comision REAL NOT NULL DEFAULT 0,
            monto_comision REAL NOT NULL DEFAULT 0,
            total_neto REAL NOT NULL DEFAULT 0,
            usuario_id INTEGER,
            cancelada INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY (usuario_id)
                REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS detalle_venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            precio_unitario REAL NOT NULL,
            costo_unitario REAL NOT NULL DEFAULT 0,
            descuento REAL NOT NULL DEFAULT 0,
            subtotal REAL NOT NULL,

            FOREIGN KEY (venta_id)
                REFERENCES ventas(id),

            FOREIGN KEY (producto_id)
                REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS movimientos_inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            existencia_anterior REAL NOT NULL,
            existencia_nueva REAL NOT NULL,
            referencia TEXT,
            fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            usuario_id INTEGER,

            FOREIGN KEY (producto_id)
                REFERENCES productos(id),

            FOREIGN KEY (usuario_id)
                REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT NOT NULL UNIQUE,
            proveedor_id INTEGER,
            fecha TEXT NOT NULL,
            subtotal REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            notas TEXT,
            usuario_id INTEGER,

            FOREIGN KEY (proveedor_id)
                REFERENCES proveedores(id),

            FOREIGN KEY (usuario_id)
                REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS detalle_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            costo_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,

            FOREIGN KEY (compra_id)
                REFERENCES compras(id),

            FOREIGN KEY (producto_id)
                REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            accion TEXT NOT NULL,
            modulo TEXT NOT NULL,
            referencia TEXT,
            detalles TEXT,
            fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (usuario_id)
                REFERENCES usuarios(id)
        );

        CREATE INDEX IF NOT EXISTS idx_productos_codigo_barras
            ON productos(codigo_barras);

        CREATE INDEX IF NOT EXISTS idx_productos_nombre
            ON productos(nombre);

        CREATE INDEX IF NOT EXISTS idx_ventas_fecha
            ON ventas(fecha);

        CREATE INDEX IF NOT EXISTS idx_movimientos_producto
            ON movimientos_inventario(producto_id);

        CREATE INDEX IF NOT EXISTS idx_auditoria_fecha
            ON auditoria(fecha);
        """
    )

    _insertar_configuracion_inicial(db)
    # -------------------------------------------------
    # Migración: agregar costo_unitario a detalle_venta
    # -------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(detalle_venta)"
    )

    columnas = [
        columna[1]
        for columna in cursor.fetchall()
    ]

    if "costo_unitario" not in columnas:
        cursor.execute(
            """
            ALTER TABLE detalle_venta
            ADD COLUMN costo_unitario
            REAL NOT NULL DEFAULT 0
            """
        )
    _insertar_configuracion_inicial(db)

    db.commit()


def _insertar_configuracion_inicial(db: Database) -> None:
    configuracion = {
        "nombre_negocio": "Echando Chal",
        "comision_mercado_libre": "4.00",
        "moneda": "MXN",
    }

    cursor = db.cursor()

    for clave, valor in configuracion.items():
        cursor.execute(
            """
            INSERT OR IGNORE INTO configuracion (clave, valor)
            VALUES (?, ?)
            """,
            (clave, valor),
        )
