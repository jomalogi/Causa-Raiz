import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('netstat -tlpn | grep 3306')
print("Host MySQL listening on:")
print(stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('docker inspect reicidentes_web | grep Gateway')
print("Docker Gateway:")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
