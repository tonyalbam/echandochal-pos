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
            direccion TEXT,
            telefono TEXT,
            correo TEXT,
            notas TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            codigo_barras TEXT UNIQUE,
            codigo_qr TEXT UNIQUE,
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
            metodo_pago TEXT,
            porcentaje_comision REAL,
            monto_comision REAL,
            total_neto REAL,

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

    # Catálogo configurable de unidades; conserva los textos ya utilizados.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)
    for name in (
        "pieza", "madeja", "ovillo", "metro", "gramo", "kilogramo", "paquete"
    ):
        cursor.execute(
            "INSERT OR IGNORE INTO unidades (nombre) VALUES (?)", (name,)
        )
    cursor.execute("""
        INSERT OR IGNORE INTO unidades (nombre)
        SELECT DISTINCT TRIM(unidad) FROM productos
        WHERE unidad IS NOT NULL AND TRIM(unidad) <> ''
    """)

    # Los pagos nuevos pertenecen a la venta completa; las partidas anteriores
    # se conservan intactas para consultas y reportes históricos.
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS pagos_venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            metodo_pago TEXT NOT NULL CHECK (
                metodo_pago IN ('Efectivo', 'Transferencia', 'Mercado Libre')
            ),
            monto REAL NOT NULL CHECK (monto > 0),
            monto_comision REAL NOT NULL DEFAULT 0 CHECK (monto_comision >= 0),
            FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE RESTRICT,
            UNIQUE (venta_id, metodo_pago)
        );
        CREATE INDEX IF NOT EXISTS idx_pagos_venta_venta ON pagos_venta(venta_id);

        CREATE VIEW IF NOT EXISTS resumen_pagos_venta AS
        SELECT p.venta_id, p.metodo_pago, p.monto AS ventas,
               p.monto_comision AS comisiones
          FROM pagos_venta p
        UNION ALL
        SELECT dv.venta_id,
               COALESCE(dv.metodo_pago, v.metodo_pago) AS metodo_pago,
               CASE WHEN dv.metodo_pago IS NULL AND v.subtotal > 0
                    THEN v.total * dv.subtotal / v.subtotal
                    ELSE dv.subtotal - dv.descuento END AS ventas,
               COALESCE(dv.monto_comision,
                   CASE WHEN v.subtotal > 0
                        THEN v.monto_comision * dv.subtotal / v.subtotal
                        ELSE 0 END) AS comisiones
          FROM detalle_venta dv
          JOIN ventas v ON v.id = dv.venta_id
         WHERE NOT EXISTS (
             SELECT 1 FROM pagos_venta p WHERE p.venta_id = dv.venta_id
         );
    """)

    # Borrado lógico: conserva las relaciones históricas con ventas y compras.
    product_columns = {
        column[1]
        for column in cursor.execute("PRAGMA table_info(productos)").fetchall()
    }
    if "eliminado" not in product_columns:
        cursor.execute(
            "ALTER TABLE productos ADD COLUMN eliminado INTEGER NOT NULL DEFAULT 0"
        )

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

    # Migración: forma de pago y comisión por partida de venta.
    detail_columns = {
        column[1]
        for column in cursor.execute(
            "PRAGMA table_info(detalle_venta)"
        ).fetchall()
    }
    detail_migrations = {
        "metodo_pago": "TEXT",
        "porcentaje_comision": "REAL",
        "monto_comision": "REAL",
        "total_neto": "REAL",
    }
    for column_name, column_type in detail_migrations.items():
        if column_name not in detail_columns:
            cursor.execute(
                f"ALTER TABLE detalle_venta "
                f"ADD COLUMN {column_name} {column_type}"
            )

    supplier_columns = {
        column[1]
        for column in cursor.execute(
            "PRAGMA table_info(proveedores)"
        ).fetchall()
    }
    if "direccion" not in supplier_columns:
        cursor.execute(
            "ALTER TABLE proveedores ADD COLUMN direccion TEXT"
        )

    product_columns = {
        column[1]
        for column in cursor.execute(
            "PRAGMA table_info(productos)"
        ).fetchall()
    }
    if "codigo_qr" not in product_columns:
        cursor.execute(
            "ALTER TABLE productos ADD COLUMN codigo_qr TEXT"
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_productos_codigo_qr
            ON productos(codigo_qr)
            WHERE codigo_qr IS NOT NULL
            """
        )
    _insertar_configuracion_inicial(db)
    _insertar_categorias_iniciales(db)

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


def _insertar_categorias_iniciales(db: Database) -> None:
    categories = (
        "Algodón",
        "Acrílico",
        "Combinado",
        "Clases",
        "Mercería",
        "Pedidos personalizados",
        "Talleres",
        "Patrones",
    )
    cursor = db.cursor()
    for category in categories:
        cursor.execute(
            """
            INSERT INTO categorias (nombre, activo)
            VALUES (?, 1)
            ON CONFLICT(nombre) DO NOTHING
            """,
            (category,),
        )
