import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

sql = """
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'Claro2026';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
SELECT user, host FROM mysql.user WHERE user IN ('root', 'calidad_user');
"""

stdin, stdout, stderr = ssh.exec_command(f'mysql -u root -pClaro2026 -e "{sql}"')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
