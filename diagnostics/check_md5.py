import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('md5sum /root/reicidentes_app/app.py')
print("Server /root/reicidentes_app/app.py md5:", stdout.read().decode().strip())

stdin, stdout, stderr = ssh.exec_command('docker exec reicidentes_web md5sum /app/app.py')
print("Inside reicidentes_web /app/app.py md5:", stdout.read().decode().strip())

ssh.close()

import hashlib
with open(r"D:\IM\Reicidentes_IM\reicidentes_app\app.py", "rb") as f:
    print("Local D:\\IM\\...\\app.py md5:", hashlib.md5(f.read()).hexdigest())
