import os
import sys
import sqlite3
import datetime
from pathlib import Path
import pandas as pd

# Configuracion de conexion a Base de Datos
DB_TYPE = os.getenv("DB_TYPE", "mysql") # "mysql" o "sqlite"
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Claro2026")
DB_NAME = os.getenv("DB_NAME", "calidad_visitas")

SQLITE_PATH = Path(__file__).resolve().parent / "calidad_visitas.db"

_CURRENT_ENGINE = None

def now_colombia_str():
    """Retorna la fecha y hora actual de Colombia (UTC-5) en formato YYYY-MM-DD HH:MM:SS."""
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')

def get_connection():
    global _CURRENT_ENGINE
    if DB_TYPE.lower() == "mysql" and _CURRENT_ENGINE != "sqlite":
        try:
            import pymysql
            # Primero intentar conectar a la base de datos
            try:
                conn = pymysql.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    charset="utf8mb4",
                    autocommit=True,
                    connect_timeout=2,
                    cursorclass=pymysql.cursors.DictCursor
                )
                _CURRENT_ENGINE = "mysql"
                return conn, "mysql"
            except pymysql.err.OperationalError as oe:
                # Si el error es que la base de datos no existe (1049), crearla
                if oe.args[0] == 1049:
                    root_conn = pymysql.connect(
                        host=DB_HOST,
                        port=DB_PORT,
                        user=DB_USER,
                        password=DB_PASSWORD,
                        charset="utf8mb4",
                        autocommit=True
                    )
                    with root_conn.cursor() as cur:
                        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                    root_conn.close()
                    # Reintentar conexión con la base creada
                    conn = pymysql.connect(
                        host=DB_HOST,
                        port=DB_PORT,
                        user=DB_USER,
                        password=DB_PASSWORD,
                        database=DB_NAME,
                        charset="utf8mb4",
                        autocommit=True,
                        connect_timeout=2,
                        cursorclass=pymysql.cursors.DictCursor
                    )
                    _CURRENT_ENGINE = "mysql"
                    return conn, "mysql"
                raise oe
        except Exception as e:
            if _CURRENT_ENGINE is None:
                print(f"[DB] Modo SQLite activo ({e})")
            _CURRENT_ENGINE = "sqlite"
    
    # SQLite Fallback
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def init_db():
    """Inicializa las tablas si no existen."""
    conn, engine = get_connection()
    try:
        if engine == "mysql":
            schema_file = Path(__file__).resolve().parent / "schema.sql"
            with open(schema_file, "r", encoding="utf-8") as f:
                sql_script = f.read()
            
            with conn.cursor() as cur:
                statements = sql_script.split(";")
                for stmt in statements:
                    stmt = stmt.strip()
                    if stmt and not stmt.upper().startswith("USE "):
                        cur.execute(stmt)
            print("[DB] Tablas MySQL verificadas/creadas correctamente.")
        else:
            with conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS cargues_control (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_archivo TEXT NOT NULL,
                    total_registros INTEGER NOT NULL DEFAULT 0,
                    fecha_cargue TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario_cargue TEXT DEFAULT 'Sistema',
                    activo INTEGER DEFAULT 1
                );
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS visitas_calidad (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cargue_id INTEGER NOT NULL,
                    fecha_cargue TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ot INTEGER,
                    cuenta INTEGER,
                    aliado TEXT,
                    fecha_trabajo_ini TEXT,
                    estado TEXT,
                    trabajo TEXT,
                    tipo TEXT,
                    subtipo TEXT,
                    tecnico TEXT,
                    segmento TEXT,
                    fecha_creacion TEXT,
                    cuenta_matriz TEXT,
                    ubicacion TEXT,
                    red TEXT,
                    region TEXT,
                    area TEXT,
                    distrito TEXT,
                    comunidad TEXT,
                    aliado_zonificado TEXT,
                    proveedor_red TEXT,
                    mes_trabajo TEXT,
                    cantidad_lls INTEGER DEFAULT 0,
                    primera_lls INTEGER,
                    fecha_primera_lls TEXT,
                    primer_dia_arreglo INTEGER DEFAULT 0,
                    rango_primer_arreglo TEXT,
                    tuvo_arreglo_30dias TEXT
                );
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS matriz_causas_subcausas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    causa TEXT NOT NULL,
                    subcausa TEXT NOT NULL,
                    activo INTEGER DEFAULT 1,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS hallazgos_respuestas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_user_id INTEGER NOT NULL,
                    telegram_username TEXT,
                    telegram_nombre TEXT,
                    ot INTEGER,
                    cuenta INTEGER,
                    aliado TEXT,
                    region TEXT,
                    segmento TEXT,
                    red TEXT,
                    comunidad TEXT,
                    primera_lls INTEGER,
                    rango_primer_arreglo TEXT,
                    causa TEXT NOT NULL,
                    subcausa TEXT NOT NULL,
                    observaciones TEXT,
                    estado TEXT DEFAULT 'Completado'
                );
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS validacion_cambio_vias_onnet (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_user_id INTEGER NOT NULL,
                    telegram_username TEXT,
                    telegram_nombre TEXT,
                    region TEXT,
                    red TEXT DEFAULT 'Red Neutra',
                    aliado TEXT,
                    segmento TEXT,
                    comunidad TEXT,
                    cuenta INTEGER,
                    cambio_vias_automatico TEXT,
                    cambio_vias_exitoso TEXT,
                    error_presentado TEXT,
                    tiempo_duracion TEXT,
                    experiencia_tecnico TEXT,
                    observaciones TEXT
                );
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS base_tecnicos_inventario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cedula INTEGER NOT NULL UNIQUE,
                    nombre_tecnico TEXT NOT NULL,
                    fecha_ingreso TEXT,
                    antiguedad TEXT,
                    aliado TEXT,
                    region TEXT,
                    area TEXT,
                    comunidad TEXT,
                    owner TEXT,
                    q30 TEXT,
                    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS inventarios_herramientas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo_auditoria TEXT NOT NULL UNIQUE,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_user_id INTEGER NOT NULL,
                    telegram_username TEXT,
                    telegram_nombre TEXT,
                    cedula_tecnico INTEGER NOT NULL,
                    nombre_tecnico TEXT NOT NULL,
                    aliado TEXT,
                    region TEXT,
                    area TEXT,
                    comunidad TEXT,
                    total_herramientas INTEGER DEFAULT 10,
                    herramientas_ok INTEGER DEFAULT 0,
                    herramientas_novedad INTEGER DEFAULT 0,
                    herramientas_faltantes INTEGER DEFAULT 0,
                    total_evidencias INTEGER DEFAULT 0,
                    foto_general_path TEXT,
                    resumen_novedades TEXT,
                    observaciones TEXT
                );
                """)
                conn.execute("""
                CREATE TABLE IF NOT EXISTS inventarios_herramientas_detalle (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inventario_id INTEGER NOT NULL,
                    codigo_auditoria TEXT NOT NULL,
                    herramienta TEXT NOT NULL,
                    estado TEXT NOT NULL,
                    novedad TEXT,
                    evidencia_path TEXT
                );
                """)
                # Indices en SQLite
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_cargue ON visitas_calidad(cargue_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_filtros ON visitas_calidad(region, red, comunidad, rango_primer_arreglo);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_lls ON visitas_calidad(primera_lls);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vias_fecha ON validacion_cambio_vias_onnet(fecha_registro);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vias_cuenta ON validacion_cambio_vias_onnet(cuenta);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tec_cedula ON base_tecnicos_inventario(cedula);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_inv_codigo ON inventarios_herramientas(codigo_auditoria);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_inv_cedula ON inventarios_herramientas(cedula_tecnico);")
                
                # Migraciones para columnas agregadas posteriormente
                for col in ["region", "proveedor_red"]:
                    try:
                        conn.execute(f"ALTER TABLE hallazgos_respuestas ADD COLUMN {col} TEXT;")
                    except Exception:
                        pass
                try:
                    conn.execute("ALTER TABLE validacion_cambio_vias_onnet ADD COLUMN error_presentado TEXT;")
                except Exception:
                    pass
            print("[DB] Tablas SQLite inicializadas correctamente.")
    finally:
        conn.close()

    # Autocargar Base_Tecnicos_Inventario.xlsx si la tabla está vacía
    try:
        conn2, eng2 = get_connection()
        cur2 = conn2.cursor()
        cur2.execute("SELECT COUNT(*) as cnt FROM base_tecnicos_inventario")
        r2 = cur2.fetchone()
        cnt_tec = r2['cnt'] if eng2 == "mysql" else r2[0]
        conn2.close()
        if cnt_tec == 0:
            local_tec = Path(__file__).resolve().parent / "Base_Tecnicos_Inventario.xlsx"
            alt_tec = Path(r"D:\IM\hallazgos\Base_Tecnicos_Inventario.xlsx")
            if local_tec.exists():
                cargar_tecnicos_inventario_excel(str(local_tec))
            elif alt_tec.exists():
                cargar_tecnicos_inventario_excel(str(alt_tec))
    except Exception as e:
        print(f"[DB] Aviso autocarga técnicos: {e}")

def cargar_matriz_excel(excel_path):
    """Carga la matriz de causas y subcausas desde el archivo Excel."""
    df = pd.read_excel(excel_path)
    df = df.dropna(subset=['Causa', 'Subcausa'])
    
    conn, engine = get_connection()
    try:
        if engine == "mysql":
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE matriz_causas_subcausas;")
                sql = "INSERT INTO matriz_causas_subcausas (causa, subcausa) VALUES (%s, %s)"
                data = [(row['Causa'].strip(), row['Subcausa'].strip()) for _, row in df.iterrows()]
                cur.executemany(sql, data)
        else:
            with conn:
                conn.execute("DELETE FROM matriz_causas_subcausas;")
                data = [(row['Causa'].strip(), row['Subcausa'].strip()) for _, row in df.iterrows()]
                conn.executemany("INSERT INTO matriz_causas_subcausas (causa, subcausa) VALUES (?, ?)", data)
        print(f"[DB] Matriz de Causas y Subcausas cargada ({len(df)} registros).")
        return len(df)
    finally:
        conn.close()

def cargar_visitas_excel(excel_path, usuario="Sistema"):
    """
    Carga el archivo diario Visitas_Calidad.xlsx en la base de datos
    agregando un nuevo lote de control con timestamp.
    """
    print(f"[DB] Leyendo Excel: {excel_path}...")
    df = pd.read_excel(excel_path)
    
    # Limpieza basica y mapeo
    col_map = {
        'OT': 'ot',
        'Cuenta': 'cuenta',
        'Aliado': 'aliado',
        'FechaTrabajoIni': 'fecha_trabajo_ini',
        'Estado': 'estado',
        'Trabajo': 'trabajo',
        'Tipo': 'tipo',
        'Subtipo': 'subtipo',
        'Tecnico': 'tecnico',
        'Segmento': 'segmento',
        'FechaCreacion': 'fecha_creacion',
        'CuentaMatriz': 'cuenta_matriz',
        'Ubicacion': 'ubicacion',
        'Red': 'red',
        'Region': 'region',
        'Area': 'area',
        'Distrito': 'distrito',
        'Comunidad': 'comunidad',
        'AliadoZonificado': 'aliado_zonificado',
        'Proveedor_Red': 'proveedor_red',
        'MesTrabajo': 'mes_trabajo',
        'CantidadLLS': 'cantidad_lls',
        'PrimeraLLS': 'primera_lls',
        'FechaPrimeraLLS': 'fecha_primera_lls',
        'PrimerDiaArreglo': 'primer_dia_arreglo',
        'RangoPrimerArreglo': 'rango_primer_arreglo',
        'TuvoArreglo30Dias': 'tuvo_arreglo_30dias'
    }
    
    # Asegurar que existan las columnas
    available_cols = [c for c in col_map.keys() if c in df.columns]
    df_clean = df[available_cols].copy()
    df_clean.rename(columns=col_map, inplace=True)
    
    # Limpieza de valores nulos o tipos
    df_clean['ot'] = pd.to_numeric(df_clean['ot'], errors='coerce').fillna(0).astype('int64')
    df_clean['cuenta'] = pd.to_numeric(df_clean['cuenta'], errors='coerce').fillna(0).astype('int64')
    df_clean['primera_lls'] = pd.to_numeric(df_clean['primera_lls'], errors='coerce').fillna(0).astype('int64')
    df_clean['cantidad_lls'] = pd.to_numeric(df_clean.get('cantidad_lls', 0), errors='coerce').fillna(0).astype(int)
    df_clean['primer_dia_arreglo'] = pd.to_numeric(df_clean.get('primer_dia_arreglo', 0), errors='coerce').fillna(0).astype(int)
    
    # Limpiar strings
    str_cols = ['aliado', 'estado', 'trabajo', 'tipo', 'subtipo', 'segmento', 'red', 'region', 'area', 'distrito', 'comunidad', 'rango_primer_arreglo', 'aliado_zonificado']
    for c in str_cols:
        if c in df_clean.columns:
            df_clean[c] = df_clean[c].fillna('').astype(str).str.strip()

    # Normalización / Unificación de Aliados
    aliados_unificar = {
        'CICSA COLOMBIA S.A.': 'TABASCO OC, LLC. SUCURSAL COLOMBIA',
        'LPS INGENISIRIA SAS': 'LPS INGENIERIA SAS'
    }
    if 'aliado' in df_clean.columns:
        df_clean['aliado'] = df_clean['aliado'].replace(aliados_unificar)
    if 'aliado_zonificado' in df_clean.columns:
        df_clean['aliado_zonificado'] = df_clean['aliado_zonificado'].replace(aliados_unificar)

    # Formato de fechas
    date_cols = ['fecha_trabajo_ini', 'fecha_primera_lls']
    for c in date_cols:
        if c in df_clean.columns:
            df_clean[c] = pd.to_datetime(df_clean[c], errors='coerce')
            df_clean[c] = df_clean[c].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else None)

    nombre_archivo = Path(excel_path).name
    total_registros = len(df_clean)
    
    conn, engine = get_connection()
    try:
        if engine == "mysql":
            with conn.cursor() as cur:
                # 1. Insertar en cargues_control
                cur.execute(
                    "INSERT INTO cargues_control (nombre_archivo, total_registros, usuario_cargue) VALUES (%s, %s, %s)",
                    (nombre_archivo, total_registros, usuario)
                )
                cargue_id = cur.lastrowid
                
                # 2. Bulk insert en visitas_calidad
                cols = ['cargue_id'] + list(df_clean.columns)
                placeholders = ", ".join(["%s"] * len(cols))
                col_names = ", ".join([f"`{c}`" for c in cols])
                sql = f"INSERT INTO visitas_calidad ({col_names}) VALUES ({placeholders})"
                
                rows_data = []
                for _, row in df_clean.iterrows():
                    row_vals = [cargue_id] + [None if pd.isna(row[c]) or row[c] == '' else row[c] for c in df_clean.columns]
                    rows_data.append(row_vals)
                
                # Insertar en lotes de 1000
                batch_size = 1000
                for i in range(0, len(rows_data), batch_size):
                    cur.executemany(sql, rows_data[i:i + batch_size])
        else:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO cargues_control (nombre_archivo, total_registros, usuario_cargue) VALUES (?, ?, ?)",
                    (nombre_archivo, total_registros, usuario)
                )
                cargue_id = cur.lastrowid
                
                cols = ['cargue_id'] + list(df_clean.columns)
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                sql = f"INSERT INTO visitas_calidad ({col_names}) VALUES ({placeholders})"
                
                rows_data = []
                for _, row in df_clean.iterrows():
                    row_vals = [cargue_id] + [None if pd.isna(row[c]) or row[c] == '' else row[c] for c in df_clean.columns]
                    rows_data.append(row_vals)
                
                cur.executemany(sql, rows_data)

        print(f"[DB] Cargue exitoso: Lote ID {cargue_id} con {total_registros} registros.")
        return cargue_id, total_registros
    finally:
        conn.close()

def get_latest_cargue_id():
    """Retorna el ID del cargue más reciente."""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT id, fecha_cargue, total_registros FROM cargues_control WHERE activo = 1 ORDER BY id DESC LIMIT 1"
        cur.execute(sql)
        row = cur.fetchone()
        if not row:
            return None
        if engine == "mysql":
            return row['id']
        else:
            return row[0]
    finally:
        conn.close()

def get_regiones(cargue_id=None):
    """Obtiene las regiones distintas en el cargue o de la base de técnicos."""
    if not cargue_id:
        cargue_id = get_latest_cargue_id()

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        if cargue_id:
            sql = f"SELECT DISTINCT region FROM visitas_calidad WHERE cargue_id = {placeholder} AND region IS NOT NULL AND region != '' ORDER BY region ASC"
            cur.execute(sql, (cargue_id,))
            rows = cur.fetchall()
            res = [r['region'] for r in rows] if engine == "mysql" else [r[0] for r in rows]
            if res:
                return res
        # Fallback a base_tecnicos_inventario o R1..R5
        cur.execute("SELECT DISTINCT region FROM base_tecnicos_inventario WHERE region IS NOT NULL AND region != '' ORDER BY region ASC")
        rows = cur.fetchall()
        res = [r['region'] for r in rows] if engine == "mysql" else [r[0] for r in rows]
        return res if res else ['R1', 'R2', 'R3', 'R4', 'R5']
    except Exception:
        return ['R1', 'R2', 'R3', 'R4', 'R5']
    finally:
        conn.close()

def get_redes(region, cargue_id=None):
    """Obtiene las redes para una región."""
    if not cargue_id:
        cargue_id = get_latest_cargue_id()
    if not cargue_id:
        return []

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        sql = f"""
            SELECT DISTINCT red FROM visitas_calidad 
            WHERE cargue_id = {placeholder} AND region = {placeholder} AND red IS NOT NULL AND red != '' 
            ORDER BY red ASC
        """
        cur.execute(sql, (cargue_id, region))
        rows = cur.fetchall()
        if engine == "mysql":
            return [r['red'] for r in rows]
        return [r[0] for r in rows]
    finally:
        conn.close()

def get_aliados(region, red, cargue_id=None):
    """Obtiene los aliados con OTs para la región y red."""
    if not cargue_id:
        cargue_id = get_latest_cargue_id()
    if not cargue_id:
        return []

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        sql = f"""
            SELECT DISTINCT aliado FROM visitas_calidad 
            WHERE cargue_id = {placeholder} AND region = {placeholder} AND red = {placeholder} 
              AND aliado IS NOT NULL AND aliado != ''
            ORDER BY aliado ASC
        """
        cur.execute(sql, (cargue_id, region, red))
        rows = cur.fetchall()
        if engine == "mysql":
            return [r['aliado'] for r in rows]
        return [r[0] for r in rows]
    finally:
        conn.close()

def get_segmentos(region, red, aliado, cargue_id=None):
    """Obtiene los segmentos distintos para la región, red y aliado."""
    if not cargue_id:
        cargue_id = get_latest_cargue_id()
    if not cargue_id:
        return ['Masivo', 'Corporativo']

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        sql = f"""
            SELECT DISTINCT segmento FROM visitas_calidad 
            WHERE cargue_id = {placeholder} AND region = {placeholder} AND red = {placeholder} AND aliado = {placeholder}
              AND segmento IS NOT NULL AND segmento != ''
            ORDER BY segmento ASC
        """
        cur.execute(sql, (cargue_id, region, red, aliado))
        rows = cur.fetchall()
        if engine == "mysql":
            res = [r['segmento'] for r in rows]
        else:
            res = [r[0] for r in rows]
        return res if res else ['Masivo', 'Corporativo']
    finally:
        conn.close()

def get_comunidades(region, red=None, aliado=None, segmento=None, cargue_id=None):
    """
    Obtiene todas las ciudades/comunidades del histórico de la base de datos para la región
    (tanto en visitas_calidad como en hallazgos_respuestas), excluyendo aquellas ciudades
    donde solo se tiene red DTH.
    Permite que todas las ciudades históricas con redes fijas/neutras estén disponibles
    para selección e ingreso manual incluso si no tienen llamadas en el lote más reciente cargado.
    """
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        if engine == "mysql":
            sql = f"""
                SELECT DISTINCT comunidad FROM (
                    SELECT comunidad FROM visitas_calidad 
                    WHERE region = {placeholder} AND red != 'DTH' AND red IS NOT NULL AND red != '' AND comunidad IS NOT NULL AND comunidad != ''
                    UNION
                    SELECT comunidad FROM hallazgos_respuestas 
                    WHERE region = {placeholder} AND red != 'DTH' AND red IS NOT NULL AND red != '' AND comunidad IS NOT NULL AND comunidad != ''
                ) t
                ORDER BY comunidad ASC
            """
            cur.execute(sql, (region, region))
            rows = cur.fetchall()
            return [r['comunidad'] for r in rows]
        else:
            cur.execute("PRAGMA table_info(hallazgos_respuestas);")
            cols = [r[1] for r in cur.fetchall()]
            if 'region' in cols:
                sql = """
                    SELECT DISTINCT comunidad FROM (
                        SELECT comunidad FROM visitas_calidad 
                        WHERE region = ? AND red != 'DTH' AND red IS NOT NULL AND red != '' AND comunidad IS NOT NULL AND comunidad != ''
                        UNION
                        SELECT comunidad FROM hallazgos_respuestas 
                        WHERE region = ? AND red != 'DTH' AND red IS NOT NULL AND red != '' AND comunidad IS NOT NULL AND comunidad != ''
                    )
                    ORDER BY comunidad ASC
                """
                cur.execute(sql, (region, region))
            else:
                sql = """
                    SELECT DISTINCT comunidad FROM visitas_calidad 
                    WHERE region = ? AND red != 'DTH' AND red IS NOT NULL AND red != '' AND comunidad IS NOT NULL AND comunidad != ''
                    ORDER BY comunidad ASC
                """
                cur.execute(sql, (region,))
            rows = cur.fetchall()
            return [r[0] for r in rows]
    finally:
        conn.close()

def get_rangos_primer_arreglo(region, red, comunidad, aliado=None, segmento=None, cargue_id=None):
    """Obtiene los rangos de primer arreglo disponibles."""
    if not cargue_id:
        cargue_id = get_latest_cargue_id()
    if not cargue_id:
        return []

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        conditions = [
            f"cargue_id = {placeholder}",
            f"region = {placeholder}",
            f"red = {placeholder}",
            f"comunidad = {placeholder}"
        ]
        params = [cargue_id, region, red, comunidad]
        
        if aliado:
            conditions.append(f"aliado = {placeholder}")
            params.append(aliado)
        if segmento:
            conditions.append(f"segmento = {placeholder}")
            params.append(segmento)
            
        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT DISTINCT rango_primer_arreglo FROM visitas_calidad 
            WHERE {where_clause}
              AND rango_primer_arreglo IS NOT NULL AND rango_primer_arreglo != ''
            ORDER BY rango_primer_arreglo ASC
        """
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        if engine == "mysql":
            return [r['rango_primer_arreglo'] for r in rows]
        return [r[0] for r in rows]
    finally:
        conn.close()

def get_llamadas_servicio(region, red, comunidad, rango, aliado=None, segmento=None, cargue_id=None, limit=300):
    """
    Lista las llamadas de servicio en orden descendente del campo PrimeraLLS.
    Excluye automáticamente las OTs/llamadas que ya hayan sido diligenciadas
    en hallazgos_respuestas. Si un registro se elimina de hallazgos_respuestas,
    vuelve a estar disponible inmediatamente.
    """
    if not cargue_id:
        cargue_id = get_latest_cargue_id()
    if not cargue_id:
        return []

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        conditions = [
            f"v.cargue_id = {placeholder}",
            f"v.region = {placeholder}",
            f"v.red = {placeholder}",
            f"v.comunidad = {placeholder}",
            f"v.rango_primer_arreglo = {placeholder}",
            "v.primera_lls IS NOT NULL",
            "v.primera_lls > 0"
        ]
        params = [cargue_id, region, red, comunidad, rango]
        
        if aliado:
            conditions.append(f"v.aliado = {placeholder}")
            params.append(aliado)
        if segmento:
            conditions.append(f"v.segmento = {placeholder}")
            params.append(segmento)
            
        where_clause = " AND ".join(conditions)
        
        sql = f"""
            SELECT v.id, v.ot, v.cuenta, v.aliado, v.segmento, v.red, v.comunidad, v.primera_lls, v.rango_primer_arreglo
            FROM visitas_calidad v
            WHERE {where_clause}
              AND NOT EXISTS (
                  SELECT 1 FROM hallazgos_respuestas h 
                  WHERE (h.ot = v.ot AND h.ot IS NOT NULL AND h.ot > 0)
                     OR (h.primera_lls = v.primera_lls AND h.primera_lls IS NOT NULL AND h.primera_lls > 0)
              )
            ORDER BY v.primera_lls DESC
            LIMIT {limit}
        """
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        
        result = []
        for r in rows:
            if engine == "mysql":
                result.append(dict(r))
            else:
                result.append({
                    'id': r['id'],
                    'ot': r['ot'],
                    'cuenta': r['cuenta'],
                    'aliado': r['aliado'],
                    'segmento': r['segmento'],
                    'red': r['red'],
                    'comunidad': r['comunidad'],
                    'primera_lls': r['primera_lls'],
                    'rango_primer_arreglo': r['rango_primer_arreglo']
                })
        return result
    finally:
        conn.close()

def is_ot_diligenciada(ot, primera_lls=None):
    """
    Verifica si una OT o Primera LLS ya fue diligenciada en hallazgos_respuestas.
    Retorna los datos del hallazgo si existe, o None si no ha sido diligenciada.
    """
    if not ot and not primera_lls:
        return None
        
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        if ot and primera_lls:
            sql = f"""
                SELECT id, fecha_registro, telegram_nombre FROM hallazgos_respuestas
                WHERE (ot = {placeholder} AND ot IS NOT NULL AND ot > 0)
                   OR (primera_lls = {placeholder} AND primera_lls IS NOT NULL AND primera_lls > 0)
                ORDER BY id DESC LIMIT 1
            """
            cur.execute(sql, (ot, primera_lls))
        elif ot:
            sql = f"""
                SELECT id, fecha_registro, telegram_nombre FROM hallazgos_respuestas
                WHERE ot = {placeholder} AND ot IS NOT NULL AND ot > 0
                ORDER BY id DESC LIMIT 1
            """
            cur.execute(sql, (ot,))
        else:
            sql = f"""
                SELECT id, fecha_registro, telegram_nombre FROM hallazgos_respuestas
                WHERE primera_lls = {placeholder} AND primera_lls IS NOT NULL AND primera_lls > 0
                ORDER BY id DESC LIMIT 1
            """
            cur.execute(sql, (primera_lls,))
            
        row = cur.fetchone()
        if not row:
            return None
        if engine == "mysql":
            return dict(row)
        return {'id': row[0], 'fecha_registro': row[1], 'telegram_nombre': row[2]}
    finally:
        conn.close()

def get_proveedor_red_neutra_ciudad(comunidad):
    """Retorna el proveedor dominante de Red Neutra para una comunidad (OnNet o Atp)."""
    if not comunidad:
        return 'OnNet'
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        sql = f"""
            SELECT proveedor_red, COUNT(*) as cnt
            FROM visitas_calidad
            WHERE red = 'Red Neutra' AND comunidad = {placeholder} AND proveedor_red IN ('OnNet', 'Atp')
            GROUP BY proveedor_red
            ORDER BY cnt DESC LIMIT 1
        """
        cur.execute(sql, (comunidad,))
        row = cur.fetchone()
        if row:
            return row['proveedor_red'] if engine == "mysql" else row[0]
        atp_cities = ['Armenia', 'Bogota, D.C.', 'Cali', 'Envigado', 'Facatativa', 'Funza', 'Itagui', 'La Estrella', 'Madrid', 'Medellin', 'Mosquera', 'Palmira', 'Sabaneta']
        return 'Atp' if comunidad in atp_cities else 'OnNet'
    except Exception:
        return 'OnNet'
    finally:
        conn.close()

def get_detalle_visita(primera_lls, cargue_id=None):
    """Obtiene los campos informativos de una llamada específica."""
    if not cargue_id:
        cargue_id = get_latest_cargue_id()

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        extra_cargue = f"AND cargue_id = {placeholder}" if cargue_id else ""
        sql = f"""
            SELECT ot, cuenta, aliado, region, segmento, red, proveedor_red, comunidad, primera_lls, rango_primer_arreglo, estado, trabajo, fecha_trabajo_ini
            FROM visitas_calidad 
            WHERE primera_lls = {placeholder} {extra_cargue}
            ORDER BY id DESC LIMIT 1
        """
        params = (primera_lls, cargue_id) if cargue_id else (primera_lls,)
        cur.execute(sql, params)
        row = cur.fetchone()
        if not row:
            return None
        if engine == "mysql":
            return dict(row)
        return {
            'ot': row['ot'],
            'cuenta': row['cuenta'],
            'aliado': row['aliado'],
            'region': row['region'],
            'segmento': row['segmento'],
            'red': row['red'],
            'proveedor_red': row['proveedor_red'],
            'comunidad': row['comunidad'],
            'primera_lls': row['primera_lls'],
            'rango_primer_arreglo': row['rango_primer_arreglo'],
            'estado': row['estado'],
            'trabajo': row['trabajo'],
            'fecha_trabajo_ini': row['fecha_trabajo_ini']
        }
    finally:
        conn.close()

def get_info_by_ot_or_lls(val):
    """Busca los datos territoriales y de red por OT o Primera LLS si existe en visitas_calidad."""
    if not val:
        return None
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        sql = f"""
            SELECT region, aliado, red, proveedor_red, comunidad, segmento
            FROM visitas_calidad
            WHERE ot = {placeholder} OR primera_lls = {placeholder}
            ORDER BY id DESC LIMIT 1
        """
        cur.execute(sql, (val, val))
        row = cur.fetchone()
        if not row:
            return None
        if engine == "mysql":
            return dict(row)
        return {
            'region': row['region'],
            'aliado': row['aliado'],
            'red': row['red'],
            'proveedor_red': row['proveedor_red'],
            'comunidad': row['comunidad'],
            'segmento': row['segmento']
        }
    finally:
        conn.close()

def get_causas():
    """Retorna las causas unicas de la matriz."""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        sql = "SELECT DISTINCT causa FROM matriz_causas_subcausas WHERE activo = 1 ORDER BY causa ASC"
        cur.execute(sql)
        rows = cur.fetchall()
        if engine == "mysql":
            return [r['causa'] for r in rows]
        return [r[0] for r in rows]
    finally:
        conn.close()

def get_subcausas(causa):
    """Retorna las subcausas asociadas a una causa seleccionada."""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        sql = f"SELECT subcausa FROM matriz_causas_subcausas WHERE causa = {placeholder} AND activo = 1 ORDER BY subcausa ASC"
        cur.execute(sql, (causa,))
        rows = cur.fetchall()
        if engine == "mysql":
            return [r['subcausa'] for r in rows]
        return [r[0] for r in rows]
    finally:
        conn.close()

def guardar_hallazgo(datos):
    """
    Guarda la respuesta de causa raíz en la tabla hallazgos_respuestas.
    datos = {
        'telegram_user_id': ...,
        'telegram_username': ...,
        'telegram_nombre': ...,
        'ot': ...,
        'cuenta': ...,
        'aliado': ...,
        'region': ...,
        'segmento': ...,
        'red': ...,
        'proveedor_red': ...,
        'comunidad': ...,
        'primera_lls': ...,
        'rango_primer_arreglo': ...,
        'causa': ...,
        'subcausa': ...,
        'observaciones': ...
    }
    """
    conn, engine = get_connection()
    try:
        # Asegurar proveedor_red válido ('Claro', 'OnNet', 'Atp')
        if not datos.get('proveedor_red'):
            red_val = str(datos.get('red', '')).strip().upper()
            com_val = str(datos.get('comunidad', '')).strip()
            if 'NEUTRA' in red_val:
                datos['proveedor_red'] = get_proveedor_red_neutra_ciudad(com_val)
            else:
                datos['proveedor_red'] = 'Claro'
        else:
            p = str(datos['proveedor_red']).strip().upper()
            if 'ONNET' in p or 'ON NET' in p:
                datos['proveedor_red'] = 'OnNet'
            elif 'ATP' in p:
                datos['proveedor_red'] = 'Atp'
            else:
                datos['proveedor_red'] = 'Claro'

        cols = [
            'telegram_user_id', 'telegram_username', 'telegram_nombre',
            'ot', 'cuenta', 'aliado', 'region', 'segmento', 'red', 'proveedor_red', 'comunidad',
            'primera_lls', 'rango_primer_arreglo', 'causa', 'subcausa', 'observaciones'
        ]
        vals = [datos.get(c) for c in cols]
        
        if engine == "mysql":
            with conn.cursor() as cur:
                placeholders = ", ".join(["%s"] * len(cols))
                col_names = ", ".join([f"`{c}`" for c in cols])
                sql = f"INSERT INTO hallazgos_respuestas ({col_names}) VALUES ({placeholders})"
                cur.execute(sql, vals)
                hallazgo_id = cur.lastrowid
        else:
            with conn:
                cur = conn.cursor()
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                sql = f"INSERT INTO hallazgos_respuestas ({col_names}) VALUES ({placeholders})"
                cur.execute(sql, vals)
                hallazgo_id = cur.lastrowid

        print(f"[DB] Hallazgo guardado ID #{hallazgo_id} por {datos.get('telegram_username')}")
        return hallazgo_id
    finally:
        conn.close()

def get_estadisticas():
    """Retorna estadisticas globales para el dashboard web."""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        stats = {}
        
        # Total visitas
        cur.execute("SELECT COUNT(*) FROM visitas_calidad")
        stats['total_visitas'] = cur.fetchone()[0] if engine == "sqlite" else list(cur.fetchone().values())[0]
        
        # Total hallazgos
        cur.execute("SELECT COUNT(*) FROM hallazgos_respuestas")
        stats['total_hallazgos'] = cur.fetchone()[0] if engine == "sqlite" else list(cur.fetchone().values())[0]
        
        # Ultimo cargue
        cur.execute("SELECT id, nombre_archivo, total_registros, fecha_cargue FROM cargues_control ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            if engine == "mysql":
                stats['ultimo_cargue'] = dict(row)
            else:
                stats['ultimo_cargue'] = {
                    'id': row['id'],
                    'nombre_archivo': row['nombre_archivo'],
                    'total_registros': row['total_registros'],
                    'fecha_cargue': row['fecha_cargue']
                }
        else:
            stats['ultimo_cargue'] = None
            
        return stats
    finally:
        conn.close()

def get_ultimos_hallazgos(limit=50):
    """Retorna los ultimos hallazgos registrados."""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        sql = f"SELECT * FROM hallazgos_respuestas ORDER BY id DESC LIMIT {limit}"
        cur.execute(sql)
        rows = cur.fetchall()
        if engine == "mysql":
            return [dict(r) for r in rows]
        return [dict(r) for r in rows]
    finally:
        conn.close()

def guardar_validacion_vias(datos):
    # Guarda la respuesta de Validacion Cambio Vias Onnet en validacion_cambio_vias_onnet
    conn, engine = get_connection()
    try:
        cols = [
            'telegram_user_id', 'telegram_username', 'telegram_nombre',
            'region', 'red', 'aliado', 'segmento', 'comunidad', 'cuenta',
            'cambio_vias_automatico', 'cambio_vias_exitoso', 'error_presentado',
            'tiempo_duracion', 'experiencia_tecnico', 'observaciones'
        ]
        vals = [datos.get(c) for c in cols]
        
        if engine == "mysql":
            with conn.cursor() as cur:
                placeholders = ", ".join(["%s"] * len(cols))
                col_names = ", ".join([f"`{c}`" for c in cols])
                sql = f"INSERT INTO validacion_cambio_vias_onnet ({col_names}) VALUES ({placeholders})"
                cur.execute(sql, vals)
                registro_id = cur.lastrowid
        else:
            with conn:
                cur = conn.cursor()
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                sql = f"INSERT INTO validacion_cambio_vias_onnet ({col_names}) VALUES ({placeholders})"
                cur.execute(sql, vals)
                registro_id = cur.lastrowid

        print(f"[DB] Validacion Cambio Vias guardada ID #{registro_id} por {datos.get('telegram_username')}")
        return registro_id
    finally:
        conn.close()

def get_validaciones_vias(limit=1000):
    # Retorna las validaciones de cambio de vias registradas enriquecidas con area (Zona)
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        # Mapa rapido de comunidad -> area
        area_map = {}
        try:
            cur.execute("SELECT DISTINCT comunidad, area FROM base_tecnicos_inventario WHERE comunidad IS NOT NULL AND comunidad != '' AND area IS NOT NULL AND area != ''")
            for r in cur.fetchall():
                c_val = (r['comunidad'] if engine == "mysql" else r[0]).strip().upper()
                a_val = (r['area'] if engine == "mysql" else r[1]).strip()
                if c_val and a_val:
                    area_map[c_val] = a_val
            cur.execute("SELECT DISTINCT comunidad, area FROM visitas_calidad WHERE comunidad IS NOT NULL AND comunidad != '' AND area IS NOT NULL AND area != ''")
            for r in cur.fetchall():
                c_val = (r['comunidad'] if engine == "mysql" else r[0]).strip().upper()
                a_val = (r['area'] if engine == "mysql" else r[1]).strip()
                if c_val and a_val and c_val not in area_map:
                    area_map[c_val] = a_val
        except Exception:
            pass

        sql = f"SELECT * FROM validacion_cambio_vias_onnet ORDER BY id DESC LIMIT {limit}"
        cur.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            if r.get('fecha_registro') is not None and not isinstance(r.get('fecha_registro'), str):
                r['fecha_registro'] = str(r['fecha_registro'])
            com_up = (r.get('comunidad') or '').strip().upper()
            r['area'] = r.get('area') or area_map.get(com_up, 'Sin Zona')
        return rows
    finally:
        conn.close()

def get_estadisticas_vias():
    # Retorna metricas y datos para los graficos de barras de Validacion Cambio Vias Onnet.
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        
        # 1. Total
        cur.execute("SELECT COUNT(*) FROM validacion_cambio_vias_onnet")
        total = cur.fetchone()[0] if engine == "sqlite" else list(cur.fetchone().values())[0]
        
        stats = {
            'total': total,
            'pct_auto': 0.0,
            'pct_exito': 0.0,
            'pct_exp_pos': 0.0,
            'auto_labels': ['Sí', 'No'],
            'auto_values': [0, 0],
            'exito_labels': ['Sí', 'No'],
            'exito_values': [0, 0],
            'tiempo_labels': ['1 a 2 Minutos', '2 a 3 Minutos', 'Más de 3 Minutos'],
            'tiempo_values': [0, 0, 0],
            'exp_labels': ['Positiva', 'Negativa'],
            'exp_values': [0, 0],
            'ciudades_labels': [],
            'ciudades_values': [],
            'aliados_labels': [],
            'aliados_values': [],
            'regiones_labels': [],
            'regiones_values': [],
            'errores_labels': [],
            'errores_values': []
        }
        
        if total == 0:
            return stats
            
        def fetch_counts(query):
            cur.execute(query)
            if engine == "mysql":
                return [(r['label'] or 'Sin datos', r['cnt']) for r in cur.fetchall()]
            else:
                return [(r[0] or 'Sin datos', r[1]) for r in cur.fetchall()]

        # 2. Automático
        auto_data = dict(fetch_counts("SELECT cambio_vias_automatico as label, COUNT(*) as cnt FROM validacion_cambio_vias_onnet GROUP BY cambio_vias_automatico"))
        si_auto = auto_data.get('Si', 0) + auto_data.get('SI', 0) + auto_data.get('Sí', 0)
        no_auto = auto_data.get('No', 0) + auto_data.get('NO', 0)
        stats['auto_values'] = [si_auto, no_auto]
        stats['pct_auto'] = round((si_auto / total) * 100, 1) if total > 0 else 0.0

        # 3. Exitoso
        exito_data = dict(fetch_counts("SELECT cambio_vias_exitoso as label, COUNT(*) as cnt FROM validacion_cambio_vias_onnet GROUP BY cambio_vias_exitoso"))
        si_exito = exito_data.get('Si', 0) + exito_data.get('SI', 0) + exito_data.get('Sí', 0)
        no_exito = exito_data.get('No', 0) + exito_data.get('NO', 0)
        stats['exito_values'] = [si_exito, no_exito]
        stats['pct_exito'] = round((si_exito / total) * 100, 1) if total > 0 else 0.0

        # 4. Tiempo
        tiempo_data = dict(fetch_counts("SELECT tiempo_duracion as label, COUNT(*) as cnt FROM validacion_cambio_vias_onnet GROUP BY tiempo_duracion"))
        t1 = tiempo_data.get('1 a 2 Minutos', 0)
        t2 = tiempo_data.get('2 a 3 Minutos', 0)
        t3 = tiempo_data.get('Mas de 3 Minutos', 0) + tiempo_data.get('Más de 3 Minutos', 0)
        stats['tiempo_values'] = [t1, t2, t3]

        # 5. Experiencia
        exp_data = dict(fetch_counts("SELECT experiencia_tecnico as label, COUNT(*) as cnt FROM validacion_cambio_vias_onnet GROUP BY experiencia_tecnico"))
        pos_exp = exp_data.get('Positiva', 0)
        neg_exp = exp_data.get('Negativa', 0)
        stats['exp_values'] = [pos_exp, neg_exp]
        stats['pct_exp_pos'] = round((pos_exp / total) * 100, 1) if total > 0 else 0.0

        # 6. Por Ciudad (top 8)
        ciudades = fetch_counts("SELECT comunidad as label, COUNT(*) as cnt FROM validacion_cambio_vias_onnet WHERE comunidad IS NOT NULL AND comunidad != '' GROUP BY comunidad ORDER BY cnt DESC LIMIT 8")
        stats['ciudades_labels'] = [c[0] for c in ciudades]
        stats['ciudades_values'] = [c[1] for c in ciudades]

        # 7. Por Aliado (top 8)
        aliados = fetch_counts("SELECT aliado as label, COUNT(*) as cnt FROM validacion_cambio_vias_onnet WHERE aliado IS NOT NULL AND aliado != '' GROUP BY aliado ORDER BY cnt DESC LIMIT 8")
        stats['aliados_labels'] = [a[0] for a in aliados]
        stats['aliados_values'] = [a[1] for a in aliados]

        # 8. Por Región
        regiones = fetch_counts("SELECT region as label, COUNT(*) as cnt FROM validacion_cambio_vias_onnet WHERE region IS NOT NULL AND region != '' GROUP BY region ORDER BY cnt DESC")
        stats['regiones_labels'] = [r[0] for r in regiones]
        stats['regiones_values'] = [r[1] for r in regiones]

        # 9. Errores presentados (cuando no fue exitoso)
        errores = fetch_counts("SELECT error_presentado as label, COUNT(*) as cnt FROM validacion_cambio_vias_onnet WHERE error_presentado IS NOT NULL AND error_presentado != '' AND error_presentado != 'N/A' GROUP BY error_presentado ORDER BY cnt DESC")
        stats['errores_labels'] = [e[0] for e in errores]
        stats['errores_values'] = [e[1] for e in errores]

        return stats
    finally:
        conn.close()


# ==============================================================================
# MÓDULO: BASE DE TÉCNICOS E INVENTARIO DE HERRAMIENTAS
# ==============================================================================

def _clean_inv_str(val):
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("", "0", "0.0", "nan", "none", "null", "na", "n/a", "sin datos"):
        return ""
    return s

def _format_inv_ciudad(val):
    s = _clean_inv_str(val)
    if not s:
        return ""
    res = s.title()
    res = res.replace("D.C.", "D.C.").replace("D.c.", "D.C.")
    return res

def cargar_tecnicos_inventario_excel(excel_path):
    """
    Carga o actualiza la tabla base_tecnicos_inventario desde Base_Tecnicos_Inventario.xlsx.
    Unifica CICSA COLOMBIA S.A. -> TABASCO OC, LLC. SUCURSAL COLOMBIA.
    Mapea: Compañia -> aliado, EO Region -> region, Zona -> area, Ciudad -> comunidad.
    """
    print(f"[DB] Cargando Base de Técnicos para Inventario: {excel_path}...")
    df = pd.read_excel(excel_path)

    # Identificar nombres de columnas con tolerancia a acentos/ñ
    col_lookup = {}
    for c in df.columns:
        cl = c.lower().strip()
        if "cedula" in cl or "cédula" in cl:
            col_lookup["cedula"] = c
        elif "nombre" in cl:
            col_lookup["nombre_tecnico"] = c
        elif "ingreso" in cl:
            col_lookup["fecha_ingreso"] = c
        elif "antig" in cl:
            col_lookup["antiguedad"] = c
        elif "compa" in cl or "aliado" in cl:
            col_lookup["aliado"] = c
        elif "region" in cl or "región" in cl:
            col_lookup["region"] = c
        elif "zona" in cl or "area" in cl or "área" in cl:
            col_lookup["area"] = c
        elif "ciudad" in cl or "comunidad" in cl:
            col_lookup["comunidad"] = c
        elif "owner" in cl:
            col_lookup["owner"] = c
        elif "q30" in cl:
            col_lookup["q30"] = c

    aliados_unificar = {
        "CICSA COLOMBIA S.A.": "TABASCO OC, LLC. SUCURSAL COLOMBIA",
        "LPS INGENISIRIA SAS": "LPS INGENIERIA SAS"
    }

    rows_data = []
    for _, row in df.iterrows():
        raw_ced = row.get(col_lookup.get("cedula", "Cedula"))
        try:
            cedula = int(float(raw_ced))
        except Exception:
            continue
        if cedula <= 0:
            continue

        nombre = _clean_inv_str(row.get(col_lookup.get("nombre_tecnico", "NombreTecnico"))).upper()
        if not nombre:
            nombre = f"TECNICO {cedula}"

        raw_fecha = row.get(col_lookup.get("fecha_ingreso", "Fecha Ingreso"))
        if pd.notnull(raw_fecha):
            try:
                fecha_ingreso = pd.to_datetime(raw_fecha).strftime("%Y-%m-%d")
            except Exception:
                fecha_ingreso = _clean_inv_str(raw_fecha)
        else:
            fecha_ingreso = ""

        antiguedad = _clean_inv_str(row.get(col_lookup.get("antiguedad", "")))
        aliado = _clean_inv_str(row.get(col_lookup.get("aliado", ""))).upper()
        aliado = aliados_unificar.get(aliado, aliado)

        region = _clean_inv_str(row.get(col_lookup.get("region", ""))).upper()
        area = _format_inv_ciudad(row.get(col_lookup.get("area", "")))
        comunidad = _format_inv_ciudad(row.get(col_lookup.get("comunidad", "")))
        owner = _clean_inv_str(row.get(col_lookup.get("owner", ""))).upper()
        q30 = _clean_inv_str(row.get(col_lookup.get("q30", "")))

        rows_data.append((
            cedula, nombre, fecha_ingreso, antiguedad,
            aliado, region, area, comunidad, owner, q30
        ))

    conn, engine = get_connection()
    try:
        if engine == "mysql":
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO base_tecnicos_inventario 
                    (cedula, nombre_tecnico, fecha_ingreso, antiguedad, aliado, region, area, comunidad, owner, q30)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        nombre_tecnico = VALUES(nombre_tecnico),
                        fecha_ingreso = VALUES(fecha_ingreso),
                        antiguedad = VALUES(antiguedad),
                        aliado = IF(VALUES(aliado) != '', VALUES(aliado), aliado),
                        region = IF(VALUES(region) != '', VALUES(region), region),
                        area = IF(VALUES(area) != '', VALUES(area), area),
                        comunidad = IF(VALUES(comunidad) != '', VALUES(comunidad), comunidad),
                        owner = VALUES(owner),
                        q30 = VALUES(q30)
                """
                batch_size = 1000
                for i in range(0, len(rows_data), batch_size):
                    cur.executemany(sql, rows_data[i:i + batch_size])
        else:
            with conn:
                cur = conn.cursor()
                sql = """
                    INSERT OR REPLACE INTO base_tecnicos_inventario
                    (cedula, nombre_tecnico, fecha_ingreso, antiguedad, aliado, region, area, comunidad, owner, q30)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                cur.executemany(sql, rows_data)
        print(f"[DB] Base de Técnicos cargada exitosamente: {len(rows_data)} técnicos procesados.")
        return len(rows_data)
    finally:
        conn.close()

def get_tecnico_by_cedula(cedula):
    """Busca un técnico por número de cédula en base_tecnicos_inventario."""
    try:
        cedula_int = int(str(cedula).strip())
    except Exception:
        return None

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        cur.execute(f"SELECT * FROM base_tecnicos_inventario WHERE cedula = {placeholder} LIMIT 1", (cedula_int,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        # Asegurar unificación de aliado por si acaso
        if d.get("aliado") == "CICSA COLOMBIA S.A.":
            d["aliado"] = "TABASCO OC, LLC. SUCURSAL COLOMBIA"
        for k in ("aliado", "region", "area", "comunidad", "nombre_tecnico"):
            d[k] = _clean_inv_str(d.get(k))
        return d
    finally:
        conn.close()

def get_area_por_ciudad(comunidad, region=None):
    """Busca el Área / Zona asociada a una Ciudad (comunidad) en visitas_calidad o base_tecnicos_inventario."""
    if not comunidad:
        return ""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        sql1 = f"SELECT area FROM visitas_calidad WHERE LOWER(comunidad) = LOWER({placeholder}) AND area IS NOT NULL AND area != '' LIMIT 1"
        cur.execute(sql1, (comunidad,))
        r1 = cur.fetchone()
        if r1:
            return r1['area'] if engine == "mysql" else r1[0]
        sql2 = f"SELECT area FROM base_tecnicos_inventario WHERE LOWER(comunidad) = LOWER({placeholder}) AND area IS NOT NULL AND area != '' LIMIT 1"
        cur.execute(sql2, (comunidad,))
        r2 = cur.fetchone()
        if r2:
            return r2['area'] if engine == "mysql" else r2[0]
        return ""
    except Exception:
        return ""
    finally:
        conn.close()

def upsert_tecnico_inventario(cedula_or_dict, nombre_tecnico="", aliado="", region="", area="", comunidad=""):
    """Actualiza o inserta los datos corregidos del técnico en base_tecnicos_inventario."""
    if isinstance(cedula_or_dict, dict):
        d = cedula_or_dict
        cedula = d.get("cedula") or d.get("cedula_tecnico")
        nombre_tecnico = d.get("nombre_tecnico", "")
        aliado = d.get("aliado", "")
        region = d.get("region", "")
        area = d.get("area", "")
        comunidad = d.get("comunidad", "")
    else:
        cedula = cedula_or_dict

    try:
        cedula_int = int(str(cedula).strip())
    except Exception:
        return False

    if aliado == "CICSA COLOMBIA S.A.":
        aliado = "TABASCO OC, LLC. SUCURSAL COLOMBIA"
    if comunidad and not area:
        area = get_area_por_ciudad(comunidad, region)

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        cur.execute(f"SELECT id FROM base_tecnicos_inventario WHERE cedula = {placeholder}", (cedula_int,))
        exists = cur.fetchone()
        if exists:
            sql = f"""
                UPDATE base_tecnicos_inventario
                SET nombre_tecnico = {placeholder},
                    aliado = {placeholder},
                    region = {placeholder},
                    area = {placeholder},
                    comunidad = {placeholder}
                WHERE cedula = {placeholder}
            """
            cur.execute(sql, (nombre_tecnico, aliado, region, area, comunidad, cedula_int))
        else:
            sql = f"""
                INSERT INTO base_tecnicos_inventario (cedula, nombre_tecnico, aliado, region, area, comunidad)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """
            cur.execute(sql, (cedula_int, nombre_tecnico, aliado, region, area, comunidad))
        if engine == "sqlite":
            conn.commit()
        return True
    finally:
        conn.close()

def get_aliados_inventario(region=None):
    """
    Obtiene la lista unificada de Aliados conocidos en la BD (excluyendo solo DTH),
    para permitir corregir o actualizar el Aliado de un técnico.
    """
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        aliados_set = set()
        if region:
            cur.execute(f"SELECT DISTINCT aliado FROM visitas_calidad WHERE region = {placeholder} AND red != 'DTH' AND aliado IS NOT NULL AND aliado != ''", (region,))
            for r in cur.fetchall():
                val = (r['aliado'] if engine == "mysql" else r[0]).strip()
                if val:
                    aliados_set.add(val)
        cur.execute("SELECT DISTINCT aliado FROM visitas_calidad WHERE red != 'DTH' AND aliado IS NOT NULL AND aliado != ''")
        for r in cur.fetchall():
            val = (r['aliado'] if engine == "mysql" else r[0]).strip()
            if val:
                aliados_set.add(val)

        if not aliados_set:
            aliados_set = {
                "CINCO S.A.S.", "CLARO COLOMBIA", "CONECTAR TV S.A.S.",
                "DICO TELECOMUNICACIONES S.A.", "DOMINION", "INMEL INGENIERIA",
                "LPS INGENIERIA SAS", "SICTE LTDA",
                "TABASCO OC, LLC. SUCURSAL COLOMBIA", "TELCOS INGENIERIA S.A."
            }

        res = sorted(list(aliados_set))
        return res
    finally:
        conn.close()

def get_ciudades_inventario(region=None):
    """
    Obtiene todas las ciudades (comunidades) conocidas en la BD para la región seleccionada,
    combinando el histórico de visitas_calidad/hallazgos_respuestas (sin solo DTH) y base_tecnicos_inventario.
    """
    ciudades_base = get_comunidades(region) if region else []
    ciudades_map = {c.upper(): c for c in ciudades_base if c}

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        if region:
            cur.execute(f"SELECT DISTINCT comunidad FROM base_tecnicos_inventario WHERE region = {placeholder} AND comunidad IS NOT NULL AND comunidad != ''", (region,))
        else:
            cur.execute("SELECT DISTINCT comunidad FROM base_tecnicos_inventario WHERE comunidad IS NOT NULL AND comunidad != ''")
        for r in cur.fetchall():
            val = _format_inv_ciudad(r['comunidad'] if engine == "mysql" else r[0])
            if val and val.upper() not in ciudades_map:
                ciudades_map[val.upper()] = val
    finally:
        conn.close()

    return sorted(list(ciudades_map.values()))

def guardar_inventario_herramientas(datos_cabecera, lista_herramientas=None):
    """
    Guarda la auditoría completa de inventario de herramientas en inventarios_herramientas
    y sus 10 ítems en inventarios_herramientas_detalle.
    Retorna un diccionario con codigo_auditoria y conteos.
    """
    if lista_herramientas is None:
        lista_herramientas = datos_cabecera.get('items', [])

    fecha_col = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5))
    fecha_str = fecha_col.strftime('%Y-%m-%d %H:%M:%S')
    ymd = fecha_col.strftime('%Y%m%d')

    # Calcular conteos automáticamente a partir de lista_herramientas
    total_herramientas = len(lista_herramientas) if lista_herramientas else int(datos_cabecera.get('total_herramientas', 10))
    ok_count = 0
    nov_count = 0
    falt_count = 0
    evidencias_count = 1 if datos_cabecera.get('foto_general_path') else 0
    lineas_nov = []

    for item in lista_herramientas:
        st = (item.get('estado') or 'OK').upper()
        f_path = item.get('foto_path') or item.get('evidencia_path') or ''
        if f_path:
            evidencias_count += 1
        if st == 'OK':
            ok_count += 1
        elif st == 'NOVEDAD':
            nov_count += 1
            lineas_nov.append(f"{item.get('herramienta')}: {item.get('novedad')}")
        elif st == 'FALTANTE':
            falt_count += 1
            lineas_nov.append(f"{item.get('herramienta')}: no disponible")

    resumen_novedades = " | ".join(lineas_nov) if lineas_nov else "Sin novedades"

    # Actualizar datos del técnico en base_tecnicos_inventario si fueron completados/corregidos
    upsert_tecnico_inventario({
        'cedula': datos_cabecera.get('cedula_tecnico'),
        'nombre_tecnico': datos_cabecera.get('nombre_tecnico', ''),
        'aliado': datos_cabecera.get('aliado', ''),
        'region': datos_cabecera.get('region', ''),
        'area': datos_cabecera.get('area', ''),
        'comunidad': datos_cabecera.get('comunidad', '')
    })

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) as max_id FROM inventarios_herramientas")
        r_max = cur.fetchone()
        next_seq = (r_max['max_id'] if engine == "mysql" else r_max[0]) + 1
        codigo_auditoria = f"INV-{ymd}-{next_seq:04d}"

        placeholder = "%s" if engine == "mysql" else "?"
        while True:
            cur.execute(f"SELECT id FROM inventarios_herramientas WHERE codigo_auditoria = {placeholder}", (codigo_auditoria,))
            if not cur.fetchone():
                break
            next_seq += 1
            codigo_auditoria = f"INV-{ymd}-{next_seq:04d}"

        cols = [
            'codigo_auditoria', 'fecha_registro', 'telegram_user_id', 'telegram_username',
            'telegram_nombre', 'cedula_tecnico', 'nombre_tecnico', 'aliado', 'region',
            'area', 'comunidad', 'total_herramientas', 'herramientas_ok',
            'herramientas_novedad', 'herramientas_faltantes', 'total_evidencias',
            'foto_general_path', 'resumen_novedades', 'observaciones'
        ]
        vals = [
            codigo_auditoria,
            fecha_str,
            datos_cabecera.get('telegram_user_id'),
            datos_cabecera.get('telegram_username', ''),
            datos_cabecera.get('telegram_nombre', ''),
            int(datos_cabecera.get('cedula_tecnico') or 0),
            datos_cabecera.get('nombre_tecnico', ''),
            datos_cabecera.get('aliado', ''),
            datos_cabecera.get('region', ''),
            datos_cabecera.get('area', ''),
            datos_cabecera.get('comunidad', ''),
            total_herramientas,
            ok_count,
            nov_count,
            falt_count,
            evidencias_count,
            datos_cabecera.get('foto_general_path') or '',
            resumen_novedades,
            datos_cabecera.get('observaciones', '')
        ]

        if engine == "mysql":
            placeholders = ", ".join(["%s"] * len(cols))
            col_names = ", ".join([f"`{c}`" for c in cols])
            sql_hdr = f"INSERT INTO inventarios_herramientas ({col_names}) VALUES ({placeholders})"
            cur.execute(sql_hdr, vals)
            inv_id = cur.lastrowid

            sql_det = """
                INSERT INTO inventarios_herramientas_detalle
                (inventario_id, codigo_auditoria, herramienta, estado, novedad, evidencia_path)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            det_rows = [
                (
                    inv_id,
                    codigo_auditoria,
                    item.get('herramienta', ''),
                    item.get('estado', 'OK'),
                    item.get('novedad') or 'N/A',
                    item.get('foto_path') or item.get('evidencia_path') or ''
                )
                for item in lista_herramientas
            ]
            if det_rows:
                cur.executemany(sql_det, det_rows)
        else:
            with conn:
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                sql_hdr = f"INSERT INTO inventarios_herramientas ({col_names}) VALUES ({placeholders})"
                cur.execute(sql_hdr, vals)
                inv_id = cur.lastrowid

                sql_det = """
                    INSERT INTO inventarios_herramientas_detalle
                    (inventario_id, codigo_auditoria, herramienta, estado, novedad, evidencia_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                det_rows = [
                    (
                        inv_id,
                        codigo_auditoria,
                        item.get('herramienta', ''),
                        item.get('estado', 'OK'),
                        item.get('novedad') or 'N/A',
                        item.get('foto_path') or item.get('evidencia_path') or ''
                    )
                    for item in lista_herramientas
                ]
                if det_rows:
                    cur.executemany(sql_det, det_rows)

        print(f"[DB] Inventario guardado: {codigo_auditoria} (ID #{inv_id}) - Técnico {datos_cabecera.get('cedula_tecnico')}")
        return {
            'id': inv_id,
            'codigo_auditoria': codigo_auditoria,
            'total_herramientas': total_herramientas,
            'herramientas_ok': ok_count,
            'herramientas_novedad': nov_count,
            'herramientas_faltantes': falt_count,
            'evidencias_cargadas': evidencias_count
        }
    finally:
        conn.close()

HERRAMIENTAS_OFICIALES = [
    "Cortadora de precisión",
    "Striper",
    "Kit de limpieza",
    "Lápiz limpiador",
    "Cortacables",
    "Alcohol isopropílico",
    "Toallas limpiadoras",
    "Power Meter",
    "Ponchadora UTP",
    "Probador UTP"
]

def get_inventarios_herramientas(limit=500, region=None, aliado=None, comunidad=None, area=None):
    """Retorna la lista de auditorías de inventario más recientes incluyendo su lista de detalles y enriqueciendo Zona (area)."""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"

        # Mapa de comunidad -> area por si algún registro no tenía área
        area_map = {}
        try:
            cur.execute("SELECT DISTINCT comunidad, area FROM base_tecnicos_inventario WHERE comunidad IS NOT NULL AND comunidad != '' AND area IS NOT NULL AND area != ''")
            for r in cur.fetchall():
                c_val = (r['comunidad'] if engine == "mysql" else r[0]).strip().upper()
                a_val = (r['area'] if engine == "mysql" else r[1]).strip()
                if c_val and a_val:
                    area_map[c_val] = a_val
        except Exception:
            pass

        where_clauses = []
        params = []
        if region:
            where_clauses.append(f"region = {placeholder}")
            params.append(region)
        if aliado:
            where_clauses.append(f"aliado = {placeholder}")
            params.append(aliado)
        if comunidad:
            where_clauses.append(f"LOWER(comunidad) = LOWER({placeholder})")
            params.append(comunidad)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        cur.execute(f"SELECT * FROM inventarios_herramientas {where_sql} ORDER BY id DESC LIMIT {int(limit)}", tuple(params))
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return []

        filtered_rows = []
        for r in rows:
            if r.get('fecha_registro') is not None and not isinstance(r.get('fecha_registro'), str):
                r['fecha_registro'] = str(r['fecha_registro'])
            com_up = (r.get('comunidad') or '').strip().upper()
            if not r.get('area'):
                r['area'] = area_map.get(com_up, '')
            if area and (r.get('area') or '').strip().upper() != area.strip().upper():
                continue

            cur.execute(
                f"SELECT herramienta, estado, novedad, evidencia_path FROM inventarios_herramientas_detalle WHERE inventario_id = {placeholder} ORDER BY id ASC",
                (r['id'],)
            )
            dets = []
            for d in cur.fetchall():
                dd = dict(d)
                dd['foto_path'] = dd.get('evidencia_path') or ''
                dets.append(dd)
            r['detalles'] = dets
            filtered_rows.append(r)
        return filtered_rows
    finally:
        conn.close()

def get_inventarios_detalle_export(limit=20000, region=None, aliado=None, comunidad=None, area=None):
    """Retorna el cruce de inventarios con su detalle por herramienta para exportar a Excel (con filtros opcionales)."""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        where_clauses = []
        params = []
        if region:
            where_clauses.append(f"i.region = {placeholder}")
            params.append(region)
        if aliado:
            where_clauses.append(f"i.aliado = {placeholder}")
            params.append(aliado)
        if comunidad:
            where_clauses.append(f"LOWER(i.comunidad) = LOWER({placeholder})")
            params.append(comunidad)
        if area:
            where_clauses.append(f"LOWER(i.area) = LOWER({placeholder})")
            params.append(area)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"""
            SELECT 
                i.codigo_auditoria,
                i.fecha_registro,
                i.cedula_tecnico,
                i.nombre_tecnico,
                i.aliado,
                i.region,
                i.area as zona,
                i.comunidad as ciudad,
                d.herramienta,
                d.estado,
                d.novedad,
                d.evidencia_path,
                i.foto_general_path,
                i.telegram_nombre as supervisor,
                i.telegram_username
            FROM inventarios_herramientas i
            LEFT JOIN inventarios_herramientas_detalle d ON i.id = d.inventario_id
            {where_sql}
            ORDER BY i.id DESC, d.id ASC
            LIMIT {int(limit)}
        """
        cur.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def get_estadisticas_inventario():
    """Retorna KPIs, catálogos de filtros (Región, Aliado, Ciudad, Zona), distribución territorial y cumplimiento por ítem de herramienta."""
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM base_tecnicos_inventario")
        r_tec = cur.fetchone()
        total_tecnicos_base = r_tec['cnt'] if engine == "mysql" else r_tec[0]

        cur.execute("SELECT COUNT(*) as cnt FROM inventarios_herramientas")
        r_inv = cur.fetchone()
        total_inventarios = r_inv['cnt'] if engine == "mysql" else r_inv[0]

        # Agrupación territorial de técnicos para filtrado dinámico en el frontend
        cur.execute("""
            SELECT 
                COALESCE(region, '') as region,
                COALESCE(area, '') as area,
                COALESCE(aliado, '') as aliado,
                COALESCE(comunidad, '') as comunidad,
                COUNT(*) as cnt
            FROM base_tecnicos_inventario
            GROUP BY region, area, aliado, comunidad
        """)
        tecnicos_territorial = []
        regiones_set = {'R1', 'R2', 'R3', 'R4', 'R5'}
        zonas_set = set()
        aliados_set = set()
        ciudades_set = set()

        for row in cur.fetchall():
            if engine == "mysql":
                reg_v = (row['region'] or '').strip()
                are_v = (row['area'] or '').strip()
                ali_v = (row['aliado'] or '').strip()
                com_v = (row['comunidad'] or '').strip()
                cnt_v = int(row['cnt'] or 0)
            else:
                reg_v = (row[0] or '').strip()
                are_v = (row[1] or '').strip()
                ali_v = (row[2] or '').strip()
                com_v = (row[3] or '').strip()
                cnt_v = int(row[4] or 0)

            if reg_v:
                regiones_set.add(reg_v)
            if are_v:
                zonas_set.add(are_v)
            if ali_v:
                aliados_set.add(ali_v)
            if com_v:
                ciudades_set.add(com_v)

            tecnicos_territorial.append({
                'region': reg_v,
                'zona': are_v,
                'aliado': ali_v,
                'ciudad': com_v,
                'cnt': cnt_v
            })

        # También agregar cualquier valor presente en inventarios_herramientas o validaciones_vias
        try:
            cur.execute("SELECT DISTINCT region, area, aliado, comunidad FROM inventarios_herramientas")
            for row in cur.fetchall():
                vals = [row['region'], row['area'], row['aliado'], row['comunidad']] if engine == "mysql" else [row[0], row[1], row[2], row[3]]
                if vals[0]: regiones_set.add(vals[0].strip())
                if vals[1]: zonas_set.add(vals[1].strip())
                if vals[2]: aliados_set.add(vals[2].strip())
                if vals[3]: ciudades_set.add(vals[3].strip())
        except Exception:
            pass

        stats = {
            'total_tecnicos_base': total_tecnicos_base,
            'total_inventarios': total_inventarios,
            'total_herramientas_eval': 0,
            'total_ok': 0,
            'total_novedad': 0,
            'total_faltante': 0,
            'total_faltantes': 0,
            'total_evidencias': 0,
            'pct_ok': 0.0,
            'estado_labels': ['Herramientas OK', 'Con Novedad', 'Faltantes'],
            'estado_values': [0, 0, 0],
            'novedades_labels': ['No funciona', 'Funciona parcialmente', 'Deterioro físico', 'Falta accesorio'],
            'novedades_values': [0, 0, 0, 0],
            'herramientas_labels': list(HERRAMIENTAS_OFICIALES),
            'herramientas_ok_values': [0] * len(HERRAMIENTAS_OFICIALES),
            'herramientas_nov_values': [0] * len(HERRAMIENTAS_OFICIALES),
            'herramientas_falt_values': [0] * len(HERRAMIENTAS_OFICIALES),
            'herramientas_pct_cumplimiento': [0.0] * len(HERRAMIENTAS_OFICIALES),
            'top_tools_labels': [],
            'top_tools_values': [],
            'herramientas_nov_labels': [],
            'herramientas_nov_values': [],
            'regiones_labels': [],
            'regiones_values': [],
            'zonas_labels': [],
            'zonas_values': [],
            'aliados_labels': [],
            'aliados_values': [],
            'filtros': {
                'regiones': sorted(list(regiones_set)),
                'zonas': sorted(list(zonas_set)),
                'aliados': sorted(list(aliados_set)),
                'ciudades': sorted(list(ciudades_set))
            },
            'tecnicos_territorial': tecnicos_territorial
        }

        if total_inventarios == 0:
            return stats

        cur.execute("""
            SELECT 
                COALESCE(SUM(herramientas_ok), 0) as sum_ok,
                COALESCE(SUM(herramientas_novedad), 0) as sum_nov,
                COALESCE(SUM(herramientas_faltantes), 0) as sum_fal,
                COALESCE(SUM(total_evidencias), 0) as sum_evi,
                COALESCE(SUM(total_herramientas), 0) as sum_tot
            FROM inventarios_herramientas
        """)
        row_sums = cur.fetchone()
        if engine == "mysql":
            sum_ok = int(row_sums['sum_ok'])
            sum_nov = int(row_sums['sum_nov'])
            sum_fal = int(row_sums['sum_fal'])
            sum_evi = int(row_sums['sum_evi'])
            sum_tot = int(row_sums['sum_tot'])
        else:
            sum_ok, sum_nov, sum_fal, sum_evi, sum_tot = [int(x or 0) for x in row_sums]

        stats['total_herramientas_eval'] = sum_tot
        stats['total_ok'] = sum_ok
        stats['total_novedad'] = sum_nov
        stats['total_faltante'] = sum_fal
        stats['total_faltantes'] = sum_fal
        stats['total_evidencias'] = sum_evi
        stats['pct_ok'] = round((sum_ok / sum_tot) * 100, 1) if sum_tot > 0 else 0.0
        stats['estado_values'] = [sum_ok, sum_nov, sum_fal]

        # Cumplimiento detallado por cada una de las 10 herramientas
        cur.execute("""
            SELECT herramienta, estado, COUNT(*) as cnt
            FROM inventarios_herramientas_detalle
            GROUP BY herramienta, estado
        """)
        tool_map = {t: {'OK': 0, 'NOVEDAD': 0, 'FALTANTE': 0} for t in HERRAMIENTAS_OFICIALES}
        for r in cur.fetchall():
            h_name = (r['herramienta'] if engine == "mysql" else r[0]) or ''
            st_val = ((r['estado'] if engine == "mysql" else r[1]) or 'OK').upper()
            cnt_val = int((r['cnt'] if engine == "mysql" else r[2]) or 0)
            if h_name not in tool_map:
                tool_map[h_name] = {'OK': 0, 'NOVEDAD': 0, 'FALTANTE': 0}
            if st_val in tool_map[h_name]:
                tool_map[h_name][st_val] += cnt_val

        ok_arr, nov_arr, falt_arr, pct_arr = [], [], [], []
        for t in HERRAMIENTAS_OFICIALES:
            c_ok = tool_map[t]['OK']
            c_nov = tool_map[t]['NOVEDAD']
            c_fal = tool_map[t]['FALTANTE']
            c_tot = c_ok + c_nov + c_fal
            ok_arr.append(c_ok)
            nov_arr.append(c_nov)
            falt_arr.append(c_fal)
            pct_arr.append(round((c_ok / c_tot) * 100, 1) if c_tot > 0 else 0.0)

        stats['herramientas_ok_values'] = ok_arr
        stats['herramientas_nov_values'] = nov_arr
        stats['herramientas_falt_values'] = falt_arr
        stats['herramientas_pct_cumplimiento'] = pct_arr

        def fetch_counts(query):
            cur.execute(query)
            if engine == "mysql":
                return [(r['label'] or 'Sin datos', int(r['cnt'])) for r in cur.fetchall()]
            return [(r[0] or 'Sin datos', int(r[1])) for r in cur.fetchall()]

        # Por Tipo de Novedad
        novs = fetch_counts("""
            SELECT novedad as label, COUNT(*) as cnt 
            FROM inventarios_herramientas_detalle 
            WHERE estado = 'NOVEDAD' AND novedad IS NOT NULL AND novedad != '' AND novedad != 'N/A'
            GROUP BY novedad ORDER BY cnt DESC
        """)
        if novs:
            stats['novedades_labels'] = [n[0] for n in novs]
            stats['novedades_values'] = [n[1] for n in novs]

        # Herramientas con más novedades / faltantes
        herr_nov = fetch_counts("""
            SELECT herramienta as label, COUNT(*) as cnt 
            FROM inventarios_herramientas_detalle 
            WHERE estado != 'OK'
            GROUP BY herramienta ORDER BY cnt DESC LIMIT 10
        """)
        stats['top_tools_labels'] = [h[0] for h in herr_nov]
        stats['top_tools_values'] = [h[1] for h in herr_nov]
        stats['herramientas_nov_labels'] = stats['top_tools_labels']
        stats['herramientas_nov_values'] = stats['top_tools_values']

        # Por Región
        regs = fetch_counts("""
            SELECT region as label, COUNT(*) as cnt 
            FROM inventarios_herramientas 
            WHERE region IS NOT NULL AND region != ''
            GROUP BY region ORDER BY cnt DESC
        """)
        stats['regiones_labels'] = [r[0] for r in regs]
        stats['regiones_values'] = [r[1] for r in regs]

        # Por Zona (Area)
        zons = fetch_counts("""
            SELECT COALESCE(NULLIF(area, ''), 'Sin Zona') as label, COUNT(*) as cnt 
            FROM inventarios_herramientas 
            GROUP BY label ORDER BY cnt DESC LIMIT 10
        """)
        stats['zonas_labels'] = [z[0] for z in zons]
        stats['zonas_values'] = [z[1] for z in zons]

        # Por Aliado
        alis = fetch_counts("""
            SELECT aliado as label, COUNT(*) as cnt 
            FROM inventarios_herramientas 
            WHERE aliado IS NOT NULL AND aliado != ''
            GROUP BY aliado ORDER BY cnt DESC LIMIT 10
        """)
        stats['aliados_labels'] = [a[0] for a in alis]
        stats['aliados_values'] = [a[1] for a in alis]

        return stats
    finally:
        conn.close()


