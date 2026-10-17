import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('docker exec reicidentes_web python3 -c "import socket; s = socket.socket(); print(\'host 172.17.0.1:3306:\', s.connect_ex((\'172.17.0.1\', 3306)))"')
print("Can container connect to host MySQL 3306:")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
