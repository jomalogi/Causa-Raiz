import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('docker restart reicidentes_web')
print("Restart output:", stdout.read().decode())

stdin, stdout, stderr = ssh.exec_command('docker exec reicidentes_web grep -n "Causa Raiz Nacional" /app/app.py')
print("Grep inside container:\n", stdout.read().decode())

stdin, stdout, stderr = ssh.exec_command('docker exec reicidentes_web grep -n "Reporte Causa Raíz - Nacional" /app/app.py')
print("Header inside container:\n", stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('docker exec reicidentes_web grep -n "fig_dona_region" /app/app.py')
print("Donut region inside container:\n", stdout.read().decode('utf-8', errors='replace'))

ssh.close()
