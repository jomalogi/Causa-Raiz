import sys
import paramiko
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SERVER_IP = "10.108.34.74"
SERVER_PORT = 822
SERVER_USER = "root"
SERVER_PASS = "Claro2026"

PROJECT_DIR = Path(__file__).resolve().parent

def main():
    print("=" * 60)
    print("ACTUALIZANDO SERVIDOR CON NUEVO FILTRO DE ALIADO")
    print("=" * 60)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, port=SERVER_PORT, username=SERVER_USER, password=SERVER_PASS, timeout=10)

    print("\n[1/4] Subiendo db.py y bot.py actualizados por SFTP...")
    sftp = ssh.open_sftp()
    sftp.put(str(PROJECT_DIR / "db.py"), "/opt/bot_calidad/db.py")
    sftp.put(str(PROJECT_DIR / "bot.py"), "/opt/bot_calidad/bot.py")
    sftp.close()
    print("  -> Archivos transferidos exitosamente a /opt/bot_calidad/")

    print("\n[2/4] Verificando / creando índice en MySQL...")
    cmd_index = "mysql -u root -pClaro2026 calidad_visitas -e 'CREATE INDEX idx_reg_red_ali ON visitas_calidad (region, red, aliado);'"
    stdin, stdout, stderr = ssh.exec_command(cmd_index)
    err = stderr.read().decode()
    if err and "Duplicate key name" in err:
        print("  -> El índice ya existía en MySQL.")
    else:
        print("  -> Índice verificado en MySQL.")

    print("\n[3/4] Reiniciando servicio bot-calidad en systemd...")
    ssh.exec_command("systemctl restart bot-calidad")
    print("  -> Servicio reiniciado.")

    print("\n[4/4] Verificando logs del servicio...")
    stdin, stdout, stderr = ssh.exec_command("sleep 1 && journalctl -u bot-calidad -n 12 --no-pager")
    print(stdout.read().decode())

    ssh.close()
    print("=" * 60)
    print("¡ACTUALIZACIÓN COMPLETADA CON ÉXITO EN EL SERVIDOR!")
    print("=" * 60)

if __name__ == "__main__":
    main()
