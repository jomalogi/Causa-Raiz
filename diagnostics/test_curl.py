import sys
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('curl -s -L -I "https://docs.google.com/spreadsheets/d/1U_xNMkUFnu-rQpZu7mmbn8sfmbIQIjEO326jghA-U38/export?format=csv&gid=1234840927" | head -n 10')
print("--- CURL GOOGLE SHEETS ---")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

stdin, stdout, stderr = ssh.exec_command('docker exec reicidentes_web python3 -c "import requests; r = requests.get(\'https://docs.google.com/spreadsheets/d/1U_xNMkUFnu-rQpZu7mmbn8sfmbIQIjEO326jghA-U38/export?format=csv&gid=1234840927\', timeout=10); print(\'Status:\', r.status_code, \'Len:\', len(r.text))"')
print("--- INSIDE CONTAINER REQUEST ---")
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
