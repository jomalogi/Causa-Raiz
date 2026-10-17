import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

query = """
SELECT 
    h.id,
    h.fecha_registro,
    h.ot,
    h.cuenta,
    h.aliado,
    h.comunidad AS ciudad,
    h.red AS tipo_red,
    COALESCE(NULLIF(v.proveedor_red, ''), h.red, 'Sin Clasificar') AS proveedor_red,
    COALESCE(v.region, 'Sin Región') AS region,
    COALESCE(h.rango_primer_arreglo, 'N/D') AS rango_primer_arreglo,
    h.causa AS causa_principal,
    h.subcausa,
    h.observaciones,
    h.estado
FROM hallazgos_respuestas h
LEFT JOIN (
    SELECT ot, MAX(region) AS region, MAX(proveedor_red) AS proveedor_red 
    FROM visitas_calidad 
    GROUP BY ot
) v ON h.ot = v.ot
ORDER BY h.fecha_registro DESC;
"""

stdin, stdout, stderr = ssh.exec_command(f'mysql -u root -pClaro2026 calidad_visitas -e "{query}"')
print("Subquery JOIN result:")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
