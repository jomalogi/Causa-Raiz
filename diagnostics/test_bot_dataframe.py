import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

test_py = """
import mysql.connector
import pandas as pd

conn = mysql.connector.connect(
    host='172.20.0.1',
    port=3306,
    user='calidad_user',
    password='Claro2026',
    database='calidad_visitas'
)

query = '''
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
'''

df = pd.read_sql(query, conn)
conn.close()

print('DataFrame loaded successfully from MySQL!')
print('Shape:', df.shape)
print('Columns:', df.columns.tolist())
print(df.head())
"""

stdin, stdout, stderr = ssh.exec_command(f'docker exec reicidentes_web python3 -c "{test_py}"')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
