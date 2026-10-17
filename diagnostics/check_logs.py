import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

time.sleep(2)
stdin, stdout, stderr = ssh.exec_command("docker logs --tail 40 reicidentes_web")
print("Docker logs:")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
