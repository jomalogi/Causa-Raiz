import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

sftp = ssh.open_sftp()
sftp.put(r"D:\potenciales\bot_calidad\test_calidad_engine.py", "/tmp/test_calidad_engine.py")
sftp.close()

stdin, stdout, stderr = ssh.exec_command('docker cp /tmp/test_calidad_engine.py reicidentes_web:/app/test_calidad_engine.py && docker exec reicidentes_web python3 /app/test_calidad_engine.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
