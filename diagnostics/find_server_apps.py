import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.108.34.74", port=822, username="root", password="Claro2026", timeout=5)

cmd = "ps -ef | grep streamlit"
_, out, _ = ssh.exec_command(cmd)
print("--- Streamlit processes on server ---")
print(out.read().decode())

cmd = "ls -la /root; ls -la /var/www; ls -la /opt"
_, out, _ = ssh.exec_command(cmd)
print("--- Directories ---")
print(out.read().decode())

ssh.close()
