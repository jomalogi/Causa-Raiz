import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

test_py = """
import app
df = app.fetch_bot_causa_data()
print('Total rows:', len(df))
print('Columns:', df.columns.tolist())
print('Region counts:')
print(df['region'].value_counts())
print('Sample:')
print(df[['region', 'aliado', 'ciudad', 'proveedor_red', 'causa_principal', 'subcausa']])
"""

stdin, stdout, stderr = ssh.exec_command(f'docker exec reicidentes_web python3 -c "{test_py}"')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
