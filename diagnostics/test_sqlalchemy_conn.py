import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

test_py = """
from sqlalchemy import create_engine, text
import pandas as pd

def get_calidad_engine():
    hosts = ['host.docker.internal', '172.20.0.1', '172.17.0.1', '127.0.0.1']
    for h in hosts:
        try:
            eng = create_engine(f'mysql+mysqlconnector://calidad_user:Claro2026@{h}:3306/calidad_visitas', pool_pre_ping=True)
            with eng.connect() as c:
                c.execute(text('SELECT 1'))
            return eng
        except Exception:
            continue
    return None

eng = get_calidad_engine()
if eng:
    print('Engine connected successfully!')
    df = pd.read_sql('SELECT COUNT(*) as total FROM hallazgos_respuestas', eng)
    print(df)
else:
    print('Failed to connect to any host')
"""

stdin, stdout, stderr = ssh.exec_command(f'docker exec reicidentes_web python3 -c "{test_py}"')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))

ssh.close()
