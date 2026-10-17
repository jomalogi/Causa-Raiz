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
                # Indices en SQLite
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_cargue ON visitas_calidad(cargue_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_filtros ON visitas_calidad(region, red, comunidad, rango_primer_arreglo);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vis_lls ON visitas_calidad(primera_lls);")
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

def get_comunidades(region, red, aliado=None, segmento=None, cargue_id=None):
    """Obtiene las ciudades/comunidades con OTs para la región, red, aliado y segmento."""
    if not cargue_id:
        cargue_id = get_latest_cargue_id()
    if not cargue_id:
        return []

    conn, engine = get_connection()
    try:
        cur = conn.cursor()
        placeholder = "%s" if engine == "mysql" else "?"
        conditions = [f"cargue_id = {placeholder}", f"region = {placeholder}", f"red = {placeholder}"]
        params = [cargue_id, region, red]
        
        if aliado:
            conditions.append(f"aliado = {placeholder}")
            params.append(aliado)
        if segmento:
            conditions.append(f"segmento = {placeholder}")
            params.append(segmento)
            
        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT DISTINCT comunidad FROM visitas_calidad 
            WHERE {where_clause}
              AND comunidad IS NOT NULL AND comunidad != ''
            ORDER BY comunidad ASC
        """
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        if engine == "mysql":
            return [r['comunidad'] for r in rows]
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
            SELECT ot, cuenta, aliado, segmento, red, comunidad, primera_lls, rango_primer_arreglo, estado, trabajo, fecha_trabajo_ini
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
            'segmento': row['segmento'],
            'red': row['red'],
            'comunidad': row['comunidad'],
            'primera_lls': row['primera_lls'],
            'rango_primer_arreglo': row['rango_primer_arreglo'],
            'estado': row['estado'],
            'trabajo': row['trabajo'],
            'fecha_trabajo_ini': row['fecha_trabajo_ini']
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
        cols = [
            'telegram_user_id', 'telegram_username', 'telegram_nombre',
            'ot', 'cuenta', 'aliado', 'region', 'segmento', 'red', 'comunidad',
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
