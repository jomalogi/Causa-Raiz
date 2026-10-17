import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('mysql -u root -pClaro2026 calidad_visitas -e "SELECT DISTINCT region FROM visitas_calidad; SELECT h.id, h.ot, v.region FROM hallazgos_respuestas h LEFT JOIN visitas_calidad v ON h.ot = v.ot;"')
print("Regions in DB:")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
