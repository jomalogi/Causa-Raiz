import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=15)

# 1. Update bind-address in mysqld.cnf
print("1. Updating bind-address in /etc/mysql/mysql.conf.d/mysqld.cnf...")
stdin, stdout, stderr = ssh.exec_command("sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf && sed -i 's/^mysqlx-bind-address.*/mysqlx-bind-address = 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf")
print(stdout.read().decode(), stderr.read().decode())

print("2. Restarting mysql service...")
stdin, stdout, stderr = ssh.exec_command("systemctl restart mysql")
print(stdout.read().decode(), stderr.read().decode())

print("3. Creating user calidad_user in MySQL...")
sql_cmd = """mysql -u root -pClaro2026 -e "CREATE USER IF NOT EXISTS 'calidad_user'@'%' IDENTIFIED BY 'Claro2026'; GRANT ALL PRIVILEGES ON calidad_visitas.* TO 'calidad_user'@'%'; FLUSH PRIVILEGES;" """
stdin, stdout, stderr = ssh.exec_command(sql_cmd)
print(stdout.read().decode(), stderr.read().decode())

# Check gateway IP of reicidentes_web
stdin, stdout, stderr = ssh.exec_command("docker inspect reicidentes_web --format '{{ .NetworkSettings.Networks.reicidentes_app_default.Gateway }}'")
gateway = stdout.read().decode().strip()
if not gateway:
    stdin, stdout, stderr = ssh.exec_command("docker inspect reicidentes_web --format '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}'")
    gateway = stdout.read().decode().strip()
print("Gateway IP:", gateway)

print(f"4. Testing connection from inside container to {gateway}:3306...")
test_py = f"""
import mysql.connector
try:
    conn = mysql.connector.connect(
        host='{gateway}',
        port=3306,
        user='calidad_user',
        password='Claro2026',
        database='calidad_visitas'
    )
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM hallazgos_respuestas;')
    res = cursor.fetchone()
    print('SUCCESS! hallazgos_respuestas count:', res[0])
    cursor.close()
    conn.close()
except Exception as e:
    print('ERROR:', e)
"""
stdin, stdout, stderr = ssh.exec_command(f'docker exec reicidentes_web python3 -c "{test_py}"')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
