import os
import sys
import time
import socket
from pathlib import Path
import paramiko

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
REMOTE_DIR = "/root/bot_calidad"

PROJECT_DIR = Path(__file__).resolve().parent

FILES_TO_DEPLOY = [
    "app.py",
    "bot.py",
    "db.py",
    "web_app.py",
    "cargar_base.py",
    "schema.sql",
    "instalar_servidor.sh",
    "Matriz_Causas_Subcausas.xlsx",
    "Visitas_Calidad.xlsx"
]

def check_connection(host, port, timeout=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        res = s.connect_ex((host, port))
        return res == 0
    except Exception:
        return False
    finally:
        s.close()

def main():
    print("=" * 70)
    print("DESPLIEGUE AUTOMÁTICO EN EL SERVIDOR CLARO")
    print(f"Destino: {SERVER_USER}@{SERVER_IP}:{SERVER_PORT}")
    print("=" * 70)

    print(f"\n[1/4] Verificando conectividad con {SERVER_IP}:{SERVER_PORT}...")
    if not check_connection(SERVER_IP, SERVER_PORT, timeout=4):
        print("\n❌ AVISO DE CONECTIVIDAD:")
        print(f"No se pudo alcanzar {SERVER_IP} en el puerto {SERVER_PORT}.")
        print("Causa más probable: Este equipo no tiene activa la VPN de Claro (FortiClient) o el cable de red corporativo.")
        print("Por favor:")
        print("  1. Conéctate a FortiClient VPN (CLARO IT 2FA) o a la red corporativa.")
        print("  2. Vuelve a ejecutar este script: python desplegar_remoto.py\n")
        print("Nota: También puedes transferir la carpeta manualmente vía WinSCP o FileZilla.")
        sys.exit(1)

    print("✅ Conexión TCP exitosa!")

    print(f"\n[2/4] Conectando vía SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            SERVER_IP,
            port=SERVER_PORT,
            username=SERVER_USER,
            password=SERVER_PASS,
            timeout=15
        )
        print("✅ Autenticado como root correctamente!")
    except Exception as e:
        print(f"❌ Error al autenticar por SSH: {e}")
        sys.exit(1)

    print(f"\n[3/4] Transfiriendo archivos del proyecto vía SFTP...")
    ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
    sftp = ssh.open_sftp()

    for fname in FILES_TO_DEPLOY:
        local_path = PROJECT_DIR / fname
        if not local_path.exists():
            print(f"  ⚠️ Archivo local no encontrado: {fname}")
            continue

        remote_path = f"{REMOTE_DIR}/{fname}"
        file_size_mb = local_path.stat().st_size / (1024 * 1024)
        print(f"  -> Subiendo {fname} ({file_size_mb:.2f} MB)...", end="", flush=True)
        sftp.put(str(local_path), remote_path)
        print(" OK!")

    sftp.close()

    print(f"\n[4/4] Ejecutando script de instalación en el servidor...")
    cmd = f"cd {REMOTE_DIR} && chmod +x instalar_servidor.sh && bash instalar_servidor.sh"
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)

    for line in iter(stdout.readline, ""):
        print(line, end="")

    status = stdout.channel.recv_exit_status()
    ssh.close()

    if status == 0:
        print("\n🎉 ¡DESPLIEGUE FINALIZADO CON ÉXITO!")
        print(f"Panel Web: http://{SERVER_IP}:8505/")
        print("Bot Telegram: @causaraiz_bot")
    else:
        print(f"\n⚠️ El instalador finalizó con código de salida: {status}")

if __name__ == "__main__":
    main()
