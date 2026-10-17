import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

query = """
SELECT 
    h.id,
    h.fecha_registro,
    h.telegram_nombre AS supervisor,
    h.ot,
    h.cuenta,
    h.aliado,
    h.comunidad AS ciudad,
    h.red,
    COALESCE(v.proveedor_red, h.red, 'N/D') AS proveedor_red,
    v.region,
    h.rango_primer_arreglo,
    h.causa AS causa_principal,
    h.subcausa
FROM hallazgos_respuestas h
LEFT JOIN visitas_calidad v ON h.ot = v.ot;
"""
stdin, stdout, stderr = ssh.exec_command(f'mysql -u root -pClaro2026 calidad_visitas -e "{query}"')
print("Joined query sample:")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
