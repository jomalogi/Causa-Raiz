from sqlalchemy import create_engine, text
import pandas as pd
import os

CALIDAD_DB_CONFIG = {
    'host': os.environ.get('CALIDAD_DB_HOST', '172.20.0.1'),
    'port': int(os.environ.get('CALIDAD_DB_PORT', 3306)),
    'database': os.environ.get('CALIDAD_DB_NAME', 'calidad_visitas'),
    'user': os.environ.get('CALIDAD_DB_USER', 'calidad_user'),
    'password': os.environ.get('CALIDAD_DB_PASSWORD', 'Claro2026'),
}

def get_calidad_engine():
    hosts = [CALIDAD_DB_CONFIG['host'], 'host.docker.internal', '172.20.0.1', '172.17.0.1', '127.0.0.1', 'localhost']
    hosts_to_try = []
    for h in hosts:
        if h and h not in hosts_to_try:
            hosts_to_try.append(h)
    for h in hosts_to_try:
        try:
            url = f"mysql+mysqlconnector://{CALIDAD_DB_CONFIG['user']}:{CALIDAD_DB_CONFIG['password']}@{h}:{CALIDAD_DB_CONFIG['port']}/{CALIDAD_DB_CONFIG['database']}?charset=utf8mb4"
            eng = create_engine(url, pool_pre_ping=True, pool_recycle=3600, connect_args={'connect_timeout': 3})
            with eng.connect() as conn:
                conn.execute(text('SELECT 1'))
            return eng
        except Exception:
            continue
    return None

eng = get_calidad_engine()
print("Connected:", eng is not None)
if eng:
    query = """
    SELECT 
        h.id,
        h.fecha_registro,
        COALESCE(NULLIF(h.telegram_nombre, ''), CONCAT('ID ', h.telegram_user_id)) AS supervisor,
        h.telegram_username,
        h.ot,
        h.cuenta,
        h.aliado,
        h.comunidad AS ciudad,
        h.red AS tipo_red,
        COALESCE(NULLIF(v.proveedor_red, ''), h.red, 'Sin Clasificar') AS proveedor_red,
        COALESCE(v.region, 'N/D') AS region,
        COALESCE(h.rango_primer_arreglo, 'N/D') AS rango_primer_arreglo,
        h.causa AS causa_principal,
        h.subcausa,
        h.observaciones,
        h.estado
    FROM hallazgos_respuestas h
    LEFT JOIN visitas_calidad v ON h.ot = v.ot
    ORDER BY h.fecha_registro DESC;
    """
    df = pd.read_sql(query, eng)
    print("DataFrame shape:", df.shape)
    print("Records:\n", df[['supervisor', 'ot', 'aliado', 'ciudad', 'proveedor_red', 'causa_principal', 'subcausa']])
