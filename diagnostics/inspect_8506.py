import sys
import paramiko

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.108.34.74", port=822, username="root", password="Claro2026", timeout=5)

cmd = "docker exec reicidentes_web head -n 30 /app/app.py"
_, out, err = ssh.exec_command(cmd)
print("--- Inside Container /app/app.py (Head) ---")
print(out.read().decode("utf-8", errors="replace")[:500])

cmd = "docker exec reicidentes_web tail -n 40 /app/app.py"
_, out, err = ssh.exec_command(cmd)
print("--- Inside Container /app/app.py (Tail) ---")
print(out.read().decode("utf-8", errors="replace"))

ssh.close()
