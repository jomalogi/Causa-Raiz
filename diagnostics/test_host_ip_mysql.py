import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('python3 -c "import socket; s = socket.socket(); print(\'Connect to 10.108.34.74:3306:\', s.connect_ex((\'10.108.34.74\', 3306)))"')
print(stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('ip a | grep "inet "')
print("Host IPs:")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
