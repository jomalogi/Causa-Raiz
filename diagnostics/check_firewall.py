import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('ufw status')
print("UFW status:")
print(stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('iptables -L -n | grep 3306')
print("iptables 3306:")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
