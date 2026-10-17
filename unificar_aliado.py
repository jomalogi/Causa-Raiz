import sys
import paramiko
from pathlib import Path
import sqlite3

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

OLD_ALIADO = "LPS INGENISIRIA SAS"
NEW_ALIADO = "LPS INGENIERIA SAS"

def unificar_local():
    print("\n--- Unificando en SQLite Local ---")
    db_file = PROJECT_DIR / "calidad_visitas.db"
    if not db_file.exists():
        print("No se encontró base local.")
        return
    conn = sqlite3.connect(str(db_file))
    with conn:
        c1 = conn.execute("UPDATE visitas_calidad SET aliado = ? WHERE aliado = ?", (NEW_ALIADO, OLD_ALIADO)).rowcount
        c2 = conn.execute("UPDATE visitas_calidad SET aliado_zonificado = ? WHERE aliado_zonificado = ?", (NEW_ALIADO, OLD_ALIADO)).rowcount
        c3 = conn.execute("UPDATE hallazgos_respuestas SET aliado = ? WHERE aliado = ?", (NEW_ALIADO, OLD_ALIADO)).rowcount
    conn.close()
    print(f"SQLite local actualizado: {c1} visitas actualizadas (aliado), {c2} en aliado_zonificado, {c3} hallazgos.")

def unificar_remoto():
    print(f"\n--- Conectando a Servidor Remoto {SERVER_IP}:{SERVER_PORT} ---")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, port=SERVER_PORT, username=SERVER_USER, password=SERVER_PASS, timeout=10)

    # 1. Conteo antes
    sql_check = f"""
    SELECT aliado, COUNT(*) as cant 
    FROM visitas_calidad 
    WHERE aliado IN ('{OLD_ALIADO}', '{NEW_ALIADO}') 
    GROUP BY aliado;
    """
    cmd_check = f"mysql -u root -p{SERVER_PASS} calidad_visitas -e \"{sql_check}\""
    stdin, stdout, stderr = ssh.exec_command(cmd_check)
    print("Conteo antes de la unificación:")
    print(stdout.read().decode())

    # 2. Ejecutar UPDATE
    print("Ejecutando UPDATE en MySQL...")
    sql_update = f"""
    UPDATE visitas_calidad SET aliado = '{NEW_ALIADO}' WHERE aliado = '{OLD_ALIADO}';
    UPDATE visitas_calidad SET aliado_zonificado = '{NEW_ALIADO}' WHERE aliado_zonificado = '{OLD_ALIADO}';
    UPDATE hallazgos_respuestas SET aliado = '{NEW_ALIADO}' WHERE aliado = '{OLD_ALIADO}';
    """
    cmd_update = f"mysql -u root -p{SERVER_PASS} calidad_visitas -e \"{sql_update}\""
    stdin, stdout, stderr = ssh.exec_command(cmd_update)
    err = stderr.read().decode()
    if err and "Warning" not in err:
        print("Error/Aviso:", err)

    # 3. Conteo después
    stdin, stdout, stderr = ssh.exec_command(cmd_check)
    print("Conteo después de la unificación:")
    print(stdout.read().decode())

    # 4. Subir db.py actualizado al servidor
    print("Subiendo db.py con regla de unificación automática al servidor...")
    sftp = ssh.open_sftp()
    sftp.put(str(PROJECT_DIR / "db.py"), "/opt/bot_calidad/db.py")
    sftp.close()

    # 5. Reiniciar servicio
    print("Reiniciando servicio bot-calidad...")
    ssh.exec_command("systemctl restart bot-calidad")
    
    # 6. Ver logs
    stdin, stdout, stderr = ssh.exec_command("sleep 1 && journalctl -u bot-calidad -n 8 --no-pager")
    print("Logs del bot:")
    print(stdout.read().decode())

    ssh.close()
    print("¡Unificación completada exitosamente!")

if __name__ == "__main__":
    unificar_local()
    unificar_remoto()
