import paramiko
import socket

# Test SSH connection
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect("10.108.34.74", port=822, username="root", password="Claro2026", timeout=5)
    print("SSH Connection to 10.108.34.74:822: SUCCESS")
    client.close()
except Exception as e:
    print("SSH Connection failed:", e)
