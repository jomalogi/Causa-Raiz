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
    print("ACTUALIZANDO SERVIDOR CON SISTEMA DE INVENTARIO DE HERRAMIENTAS")
    print("=" * 60)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, port=SERVER_PORT, username=SERVER_USER, password=SERVER_PASS, timeout=15)

    print("\n[1/5] Creando carpeta de evidencias en el servidor...")
    ssh.exec_command("mkdir -p /opt/bot_calidad/uploads/evidencias")

    print("\n[2/5] Subiendo archivos actualizados por SFTP...")
    sftp = ssh.open_sftp()
    sftp.put(str(PROJECT_DIR / "db.py"), "/opt/bot_calidad/db.py")
    sftp.put(str(PROJECT_DIR / "bot.py"), "/opt/bot_calidad/bot.py")
    sftp.put(str(PROJECT_DIR / "web_app.py"), "/opt/bot_calidad/web_app.py")
    sftp.put(str(PROJECT_DIR / "schema.sql"), "/opt/bot_calidad/schema.sql")
    excel_inv = PROJECT_DIR / "Base_Tecnicos_Inventario.xlsx"
    if excel_inv.exists():
        print("  -> Subiendo Base_Tecnicos_Inventario.xlsx...")
        sftp.put(str(excel_inv), "/opt/bot_calidad/Base_Tecnicos_Inventario.xlsx")
    sftp.close()
    print("  -> Archivos transferidos exitosamente a /opt/bot_calidad/")

    print("\n[3/5] Inicializando nuevas tablas y cargando Base Nacional de Técnicos en MySQL...")
    cmd_init = "cd /opt/bot_calidad && /opt/bot_calidad/venv/bin/python -c 'import db; db.init_db(); db.cargar_tecnicos_inventario_excel(\"Base_Tecnicos_Inventario.xlsx\"); print(\"Total tecnicos en MySQL:\", db.get_estadisticas_inventario()[\"total_tecnicos_base\"])'"
    stdin, stdout, stderr = ssh.exec_command(cmd_init)
    out_init = stdout.read().decode()
    err_init = stderr.read().decode()
    if out_init:
        print("  ->", out_init.strip())
    if err_init:
        print("  -> STDERR:", err_init.strip())

    print("\n[4/5] Reiniciando servicio bot-calidad en systemd...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart bot-calidad")
    stdout.read()
    print("  -> Servicio reiniciado.")

    print("\n[5/5] Verificando logs del servicio y endpoint HTTP...")
    stdin, stdout, stderr = ssh.exec_command("sleep 2 && journalctl -u bot-calidad -n 15 --no-pager && curl -s http://127.0.0.1:8505/api/status")
    print(stdout.read().decode())

    ssh.close()
    print("=" * 60)
    print("¡ACTUALIZACIÓN COMPLETADA CON ÉXITO EN EL SERVIDOR!")
    print("=" * 60)

if __name__ == "__main__":
    main()
