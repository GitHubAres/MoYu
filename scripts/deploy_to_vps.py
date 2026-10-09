import os
import sys
import time
import socket
import subprocess
import re
import tarfile
import paramiko

password = 'vgbNEgmyMy4D'
host = '107.150.5.175'
user = 'root'
port = 22
remote_base = '/opt/moyu'

def create_raw_socket(target_host, target_port):
    cand_ips = []
    try:
        output = subprocess.check_output('ipconfig', text=True, errors='ignore')
        for line in output.splitlines():
            m = re.search(r':\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', line)
            if m:
                cand_ips.append(m.group(1))
    except Exception:
        pass

    cand_ips = [ip for ip in cand_ips if not ip.startswith(('127.', '28.', '169.254.'))]
    cand_ips.sort(key=lambda x: (not x.startswith('192.168.'), not x.startswith('10.')))

    for ip in cand_ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((ip, 0))
            s.settimeout(4)
            s.connect((target_host, target_port))
            banner = s.recv(1024)
            if banner.startswith(b'SSH'):
                s.close()
                s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s2.bind((ip, 0))
                s2.settimeout(30)
                s2.connect((target_host, target_port))
                print(f"Direct connection established via local physical IP: {ip}", flush=True)
                return s2
        except Exception:
            continue
    return None

print(f"Connecting to {host}:{port} as {user}...", flush=True)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

connected = False
for attempt in range(1, 5):
    try:
        raw_sock = create_raw_socket(host, port)
        if raw_sock:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                sock=raw_sock,
                timeout=30,
                banner_timeout=60,
                auth_timeout=30,
            )
        else:
            client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                timeout=30,
                banner_timeout=60,
                auth_timeout=30,
            )
        print("Connected successfully!", flush=True)
        connected = True
        break
    except Exception as e:
        print(f"Attempt {attempt} failed: {e}", flush=True)
        if attempt == 4: raise
        time.sleep(3)

if not connected:
    sys.exit(1)

# 创建快速部署归档包
tar_filename = "deploy_update.tar.gz"
print("Packaging app and static/js for fast upload...", flush=True)

def tar_filter(tarinfo):
    if "__pycache__" in tarinfo.name or tarinfo.name.endswith((".pyc", ".tmp")):
        return None
    return tarinfo

with tarfile.open(tar_filename, "w:gz") as tar:
    if os.path.exists("app"):
        tar.add("app", filter=tar_filter)
    if os.path.exists("static/js"):
        tar.add("static/js", filter=tar_filter)
    for rf in ["run.py", "requirements.txt", "static/index.html"]:
        if os.path.exists(rf):
            tar.add(rf)

print(f"Archive created ({os.path.getsize(tar_filename)} bytes). Uploading via SFTP...", flush=True)
sftp = client.open_sftp()
remote_tar = f"/tmp/{tar_filename}"
sftp.put(tar_filename, remote_tar)
sftp.close()
if os.path.exists(tar_filename):
    os.remove(tar_filename)
print("Uploaded archive successfully!", flush=True)

def run_cmd(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    return out + err

print("Extracting archive on remote host...", flush=True)
run_cmd(f"tar -xzf {remote_tar} -C {remote_base} && rm -f {remote_tar}")

print("Cleaning remote notes.py...", flush=True)
run_cmd("rm -f /opt/moyu/app/api/notes.py")

print("Restarting service...", flush=True)
run_cmd("systemctl restart moyu")
time.sleep(2)

print("Service status:", flush=True)
print(run_cmd("systemctl status moyu --no-pager | head -n 12"), flush=True)

print("Checking remote version:", flush=True)
print(run_cmd("python3 -c 'import sys; sys.path.insert(0, \"/opt/moyu\"); import app.version; print(\"Remote version:\", app.version.APP_VERSION)'"), flush=True)

client.close()
print("Incremental VPS deployment finished successfully!", flush=True)
