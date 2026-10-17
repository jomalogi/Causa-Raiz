import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('docker exec reicidentes_web python3 -c "import app; df = app.fetch_bot_causa_data(); print(\'Bot data rows:\', len(df)); print(df[[\'supervisor\', \'ot\', \'causa_principal\', \'subcausa\']])"')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
