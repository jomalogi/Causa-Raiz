import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('docker exec reicidentes_web python3 -c "import app; df = app.fetch_gsheet_df(\'https://docs.google.com/spreadsheets/d/1U_xNMkUFnu-rQpZu7mmbn8sfmbIQIjEO326jghA-U38/export?format=csv&gid=1234840927\'); print(\'Any mojibake in Causas:\', any(\'Ã\' in str(x) for x in df[\'Causa Principal\'].dropna())); print(\'Any mojibake in Subcausas:\', any(\'Ã\' in str(x) for x in df[\'Subcausa\'].dropna()))"')
print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
