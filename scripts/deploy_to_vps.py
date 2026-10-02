import os
import sys
import time
import paramiko

password = 'vgbNEgmyMy4D'
host = '107.150.5.175'
user = 'root'
port = 22
remote_base = '/opt/moyu'

print(f"Connecting to {host}:{port} as {user}...")
t = paramiko.Transport((host, port))
t.connect()
t.auth_password(user, password)
sftp = paramiko.SFTPClient.from_transport(t)

def sftp_mkdir_p(sftp, remote_dir):
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except Exception:
                pass

def upload_dir(local_dir, remote_dir):
    sftp_mkdir_p(sftp, remote_dir)
    for root, dirs, files in os.walk(local_dir):
        if "__pycache__" in root or ".pytest_cache" in root:
            continue
        rel = os.path.relpath(root, local_dir)
        target_dir = remote_dir if rel == "." else os.path.join(remote_dir, rel).replace("\\", "/")
        sftp_mkdir_p(sftp, target_dir)

        for f in files:
            if f.endswith((".pyc", ".tmp", ".bak")):
                continue
            local_file = os.path.join(root, f)
            remote_file = os.path.join(target_dir, f).replace("\\", "/")
            try:
                sftp.put(local_file, remote_file)
            except Exception as e:
                print(f"Failed to upload {remote_file}: {e}")

print("=== 1. Uploading app/ directory ===")
upload_dir("app", f"{remote_base}/app")

print("=== 2. Uploading static/ directory ===")
upload_dir("static", f"{remote_base}/static")

print("=== 3. Uploading root files ===")
for root_f in ["run.py", "requirements.txt", "README.md"]:
    if os.path.exists(root_f):
        rf = f"{remote_base}/{root_f}"
        sftp.put(root_f, rf)

sftp.close()

def run_cmd(cmd):
    s = t.open_session()
    s.exec_command(cmd)
    out = b""
    while True:
        c = s.recv(4096)
        if not c: break
        out += c
    return out.decode("utf-8", errors="ignore")

print("=== 4. Restarting moyu.service ===")
run_cmd("systemctl restart moyu")
time.sleep(2)

print("=== 5. Checking service status ===")
status_out = run_cmd("systemctl status moyu --no-pager | head -n 15")
print(status_out.strip())

print("=== 6. Checking remote /api/announcements/manifest ===")
manifest_out = run_cmd("curl -s http://127.0.0.1:8321/api/announcements/manifest")
print("Manifest check:", manifest_out.strip())

t.close()
print("=== VPS Deployment finished successfully! ===")
