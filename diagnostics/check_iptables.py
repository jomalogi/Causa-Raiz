import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('10.108.34.74', port=822, username='root', password='Claro2026', timeout=10)

stdin, stdout, stderr = ssh.exec_command('iptables -S')
print("--- iptables rules ---")
rules = stdout.read().decode('utf-8', errors='replace')
for line in rules.split("\n"):
    if "3306" in line or "DROP" in line or "REJECT" in line or "INPUT" in line:
        print(line)

ssh.close()
