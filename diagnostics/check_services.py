import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('systemctl status bot-calidad --no-pager | head -n 12')
print("--- bot-calidad service ---")
print(stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('curl -s -I http://localhost:8505/ | head -n 5')
print("--- web admin 8505 ---")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
