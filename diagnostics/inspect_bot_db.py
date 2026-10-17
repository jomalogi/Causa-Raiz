import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('mysql -u root -pClaro2026 calidad_visitas -e "DESCRIBE hallazgos_respuestas;"')
print("--- DESCRIBE hallazgos_respuestas ---")
print(stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('mysql -u root -pClaro2026 calidad_visitas -e "SELECT * FROM hallazgos_respuestas LIMIT 5;"')
print("--- SAMPLE hallazgos_respuestas ---")
print(stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('mysql -u root -pClaro2026 calidad_visitas -e "DESCRIBE visitas_calidad;"')
print("--- DESCRIBE visitas_calidad ---")
print(stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('mysql -u root -pClaro2026 calidad_visitas -e "SELECT COUNT(*) FROM visitas_calidad;"')
print("--- COUNT visitas_calidad ---")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
