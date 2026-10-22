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
                    tiempo_duracion TEXT,
                    experiencia_tecnico TEXT,
                    observaciones TEXT
                );
                """)
                # Indices en SQLite
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_cargue ON visitas_calidad(cargue_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_filtros ON visitas_calidad(region, red, comunidad, rango_primer_arreglo);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_lls ON visitas_calidad(primera_lls);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vias_fecha ON validacion_cambio_vias_onnet(fecha_registro);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vias_cuenta ON validacion_cambio_vias_onnet(cuenta);")
                
                # Migraciones para columnas agregadas posteriormente
                for col in ["region", "proveedor_red"]:
                    try:
                        conn.execute(f"ALTER TABLE hallazgos_respuestas ADD COLUMN {col} TEXT;")
                    except Exception:
                        pass
            print("[DB] Tablas SQLite inicializadas correctamente.")
    finally:
        conn.close()

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
    """Obtiene las regiones distintas en el cargue."""
    if not cargue_id:
        cargue_id = get_latest_cargue_id()
    if not cargue_id:
        return []

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        sql = f"SELECT DISTINCT region FROM visitas_calidad WHERE cargue_id = {placeholder} AND region IS NOT NULL AND region != '' ORDER BY region ASC"
        cur.execute(sql, (cargue_id,))
        rows = cur.fetchall()
        if engine == "mysql":
            return [r['region'] for r in rows]
        return [r[0] for r in rows]
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
            'cambio_vias_automatico', 'cambio_vias_exitoso', 'tiempo_duracion',
            'experiencia_tecnico', 'observaciones'
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
    # Retorna las validaciones de cambio de vias registradas
    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        sql = f"SELECT * FROM validacion_cambio_vias_onnet ORDER BY id DESC LIMIT {limit}"
        cur.execute(sql)
        rows = cur.fetchall()
        if engine == "mysql":
            return [dict(r) for r in rows]
        return [dict(r) for r in rows]
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
            'aliados_values': []
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

        return stats
    finally:
        conn.close()

