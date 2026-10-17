import sys
import paramiko
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=15)
sftp = ssh.open_sftp()

print("1. Subiendo app.py y database.py a /root/reicidentes_app/...")
sftp.put(r"D:\IM\Reicidentes_IM\reicidentes_app\app.py", "/root/reicidentes_app/app.py")
sftp.put(r"D:\IM\Reicidentes_IM\reicidentes_app\database.py", "/root/reicidentes_app/database.py")
print("   Archivos subidos exitosamente.")

print("2. Verificando docker-compose.yml para montar database.py...")
stdin, stdout, stderr = ssh.exec_command("cat /root/reicidentes_app/docker-compose.yml")
compose_content = stdout.read().decode('utf-8')

if "./database.py:/app/database.py" not in compose_content:
    compose_content = compose_content.replace("- ./app.py:/app/app.py", "- ./app.py:/app/app.py\n      - ./database.py:/app/database.py")
    with sftp.file("/root/reicidentes_app/docker-compose.yml", "w") as f:
        f.write(compose_content)
    print("   docker-compose.yml actualizado con volumen database.py.")
else:
    print("   docker-compose.yml ya tiene montado database.py.")

sftp.close()

print("3. Copiando archivos dentro del contenedor...")
stdin, stdout, stderr = ssh.exec_command("docker cp /root/reicidentes_app/app.py reicidentes_web:/app/app.py && docker cp /root/reicidentes_app/database.py reicidentes_web:/app/database.py")
print(stdout.read().decode(), stderr.read().decode())

print("4. Reiniciando contenedor reicidentes_web...")
stdin, stdout, stderr = ssh.exec_command("cd /root/reicidentes_app && docker compose up -d")
print(stdout.read().decode(), stderr.read().decode())

time.sleep(3)

print("5. Verificando estado del contenedor...")
stdin, stdout, stderr = ssh.exec_command("docker ps | grep reicidentes_web")
print(stdout.read().decode())

print("6. Logs recientes:")
stdin, stdout, stderr = ssh.exec_command("docker logs --tail 25 reicidentes_web")
print(stdout.read().decode('utf-8', errors='replace'))

print("7. Verificando respuesta HTTP en http://localhost:8506...")
stdin, stdout, stderr = ssh.exec_command("curl -s -I http://localhost:8506/ | head -n 10")
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
print("¡Despliegue completado con éxito!")
