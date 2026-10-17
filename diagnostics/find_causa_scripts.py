import paramiko
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('grep -rnw "Reporte Causa" /root/ /var/www/ /home/ 2>/dev/null')
print("Search Reporte Causa:")
print(stdout.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('find / -name "*causa*.py" 2>/dev/null')
print("Find *causa*.py:")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
