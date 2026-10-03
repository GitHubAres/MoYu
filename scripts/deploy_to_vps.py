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

def upload_changed_files():
    # Only upload app/ and static/js/ which were modified, plus version/doc files
    for root, dirs, files in os.walk("app"):
        if "__pycache__" in root: continue
        rel = os.path.relpath(root, ".")
        target_dir = os.path.join(remote_base, rel).replace("\\", "/")
        sftp_mkdir_p(sftp, target_dir)
        for f in files:
            if f.endswith((".pyc", ".tmp")): continue
            local_file = os.path.join(root, f)
            remote_file = os.path.join(target_dir, f).replace("\\", "/")
            sftp.put(local_file, remote_file)
            print(f"Uploaded: {remote_file}")

    for root, dirs, files in os.walk("static/js"):
        rel = os.path.relpath(root, ".")
        target_dir = os.path.join(remote_base, rel).replace("\\", "/")
        sftp_mkdir_p(sftp, target_dir)
        for f in files:
            local_file = os.path.join(root, f)
            remote_file = os.path.join(target_dir, f).replace("\\", "/")
            sftp.put(local_file, remote_file)
            print(f"Uploaded: {remote_file}")

    # Root files
    for rf in ["run.py", "requirements.txt"]:
        if os.path.exists(rf):
            sftp.put(rf, f"{remote_base}/{rf}")

upload_changed_files()
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

print("Restarting service...")
run_cmd("systemctl restart moyu")
time.sleep(2)
print("Service status:")
print(run_cmd("systemctl status moyu --no-pager | head -n 12"))

print("Checking remote version:")
print(run_cmd("python3 -c 'import sys; sys.path.insert(0, \"/opt/moyu\"); import app.version; print(\"Remote version:\", app.version.APP_VERSION)'"))

t.close()
print("Incremental VPS deployment finished!")
