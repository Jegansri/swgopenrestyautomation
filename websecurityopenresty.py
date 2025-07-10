#!/usr/bin/env python3
import subprocess
import os
import sys
import json
import shutil

def run(cmd, cwd=None, env=None, use_sudo=False, capture_output=False):
    final_cmd = cmd
    if use_sudo:
        final_cmd = ["sudo"] + cmd
    print(f"\n=== Running: {' '.join(final_cmd)} ===\n")
    if capture_output:
        result = subprocess.run(final_cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"❌ Command failed: {' '.join(final_cmd)}")
            print(result.stdout)
            print(result.stderr)
            sys.exit(1)
        return result.stdout
    else:
        result = subprocess.run(final_cmd, cwd=cwd, env=env)
        if result.returncode != 0:
            print(f"❌ Command failed: {' '.join(final_cmd)}")
            sys.exit(1)

home = os.path.expanduser("~")

# 0. Install ALL dependencies
print("=== [0] Installing all dependencies ===")
run([
    "apt-get", "update"
], use_sudo=True)
run([
    "apt-get", "install", "-y",
    "git", "build-essential", "libtool", "libtool-bin", "automake", "autoconf",
    "libxml2-dev", "libyajl-dev", "pkgconf", "zlib1g-dev",
    "libcurl4-gnutls-dev", "libgeoip-dev", "liblmdb-dev",
    "libpcre2-dev", "libpcre3-dev", "libssl-dev", "liblua5.1-0-dev",
    "software-properties-common", "unzip", "curl"
], use_sudo=True)

# 1. Add OpenResty repo
print("=== [1] Adding OpenResty repository ===")
lsb_codename = os.popen('lsb_release -sc').read().strip()
run([
    "add-apt-repository", "-y",
    f"deb http://openresty.org/package/ubuntu {lsb_codename} main"
], use_sudo=True)
run([
    "apt-key", "adv", "--keyserver", "keyserver.ubuntu.com", "--recv-keys", "97DB7443D5EDEB74"
], use_sudo=True)
run(["apt-get", "update"], use_sudo=True)

# 2. Install OpenResty
print("=== [2] Installing OpenResty ===")
run(["apt-get", "install", "-y", "openresty"], use_sudo=True)
run(["systemctl", "enable", "openresty"], use_sudo=True)
run(["systemctl", "restart", "openresty"], use_sudo=True)
run(["openresty", "-v"])

# 3. Build ModSecurity
print("=== [3] Building ModSecurity ===")
modsec_dir = os.path.join(home, "ModSecurity")
if not os.path.isdir(modsec_dir):
    run(["git", "clone", "https://github.com/SpiderLabs/ModSecurity"], cwd=home)
run(["git", "submodule", "init"], cwd=modsec_dir)
run(["git", "submodule", "update"], cwd=modsec_dir)
run(["./build.sh"], cwd=modsec_dir)
run(["./configure"], cwd=modsec_dir)
run(["make"], cwd=modsec_dir)
run(["make", "install"], cwd=modsec_dir, use_sudo=True)

# 4. Clone ModSecurity NGINX connector
print("=== [4] Cloning ModSecurity NGINX connector ===")
modsec_nginx_dir = os.path.join(home, "ModSecurity-nginx")
if not os.path.isdir(modsec_nginx_dir):
    run(["git", "clone", "--depth", "1", "https://github.com/SpiderLabs/ModSecurity-nginx.git"], cwd=home)

# 5. Download OpenResty source to build dynamic module
print("=== [5] Downloading OpenResty source ===")
openresty_ver = os.popen("openresty -v 2>&1").read().split('/')[1].strip()
if not openresty_ver:
    print("❌ Could not detect OpenResty version. Is OpenResty installed?")
    sys.exit(1)
print(f"Detected OpenResty version: {openresty_ver}")
openresty_src_tar = os.path.join(home, f"openresty-{openresty_ver}.tar.gz")
openresty_src_dir = os.path.join(home, f"openresty-{openresty_ver}")
if not os.path.isdir(openresty_src_dir):
    if not os.path.isfile(openresty_src_tar):
        run(["wget", f"https://openresty.org/download/openresty-{openresty_ver}.tar.gz"], cwd=home)
    run(["tar", "-zxvf", f"openresty-{openresty_ver}.tar.gz"], cwd=home)

# 6. Build dynamic ModSecurity module
print("=== [6] Building dynamic ModSecurity module ===")
run(["./configure", "--with-compat", f"--add-dynamic-module={modsec_nginx_dir}"], cwd=openresty_src_dir)
run(["make"], cwd=openresty_src_dir)
run(["make", "install"], cwd=openresty_src_dir, use_sudo=True)

# 7. Download and configure OWASP CRS
print("=== [7] Downloading OWASP Core Rule Set ===")
crs_dir = os.path.join(home, "modsecurity-crs")
if not os.path.isdir(crs_dir):
    run(["git", "clone", "https://github.com/coreruleset/coreruleset", "modsecurity-crs"], cwd=home)
if not os.path.isfile(os.path.join(crs_dir, "crs-setup.conf")):
    run(["mv", "crs-setup.conf.example", "crs-setup.conf"], cwd=crs_dir)
if not os.path.isfile(os.path.join(crs_dir, "rules", "REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf")):
    run(["mv", "REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf.example", "REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf"], cwd=os.path.join(crs_dir, "rules"))
crs_target_dir = "/usr/local/openresty/nginx/modsecurity-crs"
if not os.path.isdir(crs_target_dir):
    run(["mv", crs_dir, crs_target_dir], use_sudo=True)

# 8. Setup ModSecurity config files
print("=== [8] Setting up ModSecurity configuration ===")
modsec_conf_dir = "/usr/local/openresty/nginx/modsec"
run(["mkdir", "-p", modsec_conf_dir], use_sudo=True)
run(["cp", os.path.join(modsec_dir, "unicode.mapping"), modsec_conf_dir], use_sudo=True)
modsec_conf_file = os.path.join(modsec_conf_dir, "modsecurity.conf")
if not os.path.isfile(modsec_conf_file):
    run(["cp", os.path.join(modsec_dir, "modsecurity.conf-recommended"), modsec_conf_file], use_sudo=True)

# 9. Create main.conf
print("=== [9] Creating main.conf ===")
main_conf = """
Include /usr/local/openresty/nginx/modsec/modsecurity.conf
Include /usr/local/openresty/nginx/modsecurity-crs/crs-setup.conf
Include /usr/local/openresty/nginx/modsecurity-crs/rules/*.conf
"""
with open("/tmp/main.conf", "w") as f:
    f.write(main_conf.strip() + "\n")
run(["mv", "/tmp/main.conf", f"{modsec_conf_dir}/main.conf"], use_sudo=True)

# 10. Download and replace configuration files
print("=== [10] Replacing default configuration files ===")
files_to_replace = [
    (f"{modsec_conf_dir}/modsecurity.conf", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/modsecurity.conf"),
    ("/usr/local/openresty/nginx/modsecurity-crs/crs-setup.conf", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/crs-setup.conf"),
    ("/usr/local/openresty/nginx/modsecurity-crs/rules/REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf"),
    ("/etc/openresty/nginx.conf", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/nginx.conf"),
    ("/etc/openresty/example.conf", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/example.conf"),
    ("/opt/automate_waf_rules.py", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/automate_waf_rules.py"),
    ("/opt/country_mmdb.py", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/country_mmdb.py"),
    ("/opt/setup_cronjobs.py", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/setup_cronjobs.py"),
    ("/opt/clear_logs.py", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/clear_logs.py"),
    ("/root/delete_openresty_files.py", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/delete_openresty_files.py"),
    ("/var/log/400.py", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/400.py"),
    ("/var/log/403.py", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/403.py"),
    ("/var/log/alluri.py", "https://raw.githubusercontent.com/Jegansri/swgopenrestyautomation/main/alluri.py"),
]
for dest, url in files_to_replace:
    run(["rm", "-f", dest], use_sudo=True)
    run(["wget", "-O", dest, url], use_sudo=True)

# 10b. Install MaxMindDB development library (required for GeoIP2 module)
print("=== [10b] Installing MaxMindDB development library for GeoIP2 ===")
run(["apt-get", "install", "-y", "libmaxminddb-dev", "mmdb-bin"], use_sudo=True)

# 11. Download ngx_http_geoip2_module
print("=== [11] Downloading GeoIP2 module ===")
geoip2_zip = os.path.join(home, "master.zip")
geoip2_dir = os.path.join(home, "ngx_http_geoip2_module-master")
if not os.path.isdir(geoip2_dir):
    run(["wget", "-O", "master.zip", "https://github.com/leev/ngx_http_geoip2_module/archive/master.zip"], cwd=home)
    run(["unzip", "-o", "master.zip"], cwd=home)

# 12. Build GeoIP2 dynamic module (uses openresty_src_dir from before)
print("=== [12] Building GeoIP2 dynamic module ===")
run(["./configure", "--with-compat", f"--add-dynamic-module={geoip2_dir}"], cwd=openresty_src_dir)
run(["make"], cwd=openresty_src_dir)
run(["make", "install"], cwd=openresty_src_dir, use_sudo=True)

# 13. Create GeoIP directory
print("=== [13] Creating /etc/openresty/geoip directory ===")
run(["mkdir", "-p", "/etc/openresty/geoip"], use_sudo=True)

# 14. Download latest GeoLite2-Country.mmdb
print("=== [14] Fetching latest GeoLite2 database URL ===")
api_url = "https://api.github.com/repos/P3TERX/GeoLite.mmdb/releases/latest"
api_response = run(["curl", "-s", api_url], capture_output=True)
release_info = json.loads(api_response)
mmdb_url = None
for asset in release_info.get("assets", []):
    if asset.get("name") == "GeoLite2-Country.mmdb":
        mmdb_url = asset.get("browser_download_url")
        break
if not mmdb_url:
    print("❌ Could not find GeoLite2-Country.mmdb in the latest release.")
    sys.exit(1)
print(f"Downloading mmdb file from: {mmdb_url}")
run([
    "wget", "-O", "/etc/openresty/geoip/GeoLite2-Country.mmdb", mmdb_url
], use_sudo=True)
print("\n✅ All done! GeoLite2-Country.mmdb is installed in /etc/openresty/geoip/\n")

# 14b
run(["chmod", "+x", "/opt/automate_waf_rules.py"], use_sudo=True)
run(["chmod", "+x", "/opt/country_mmdb.py"], use_sudo=True)
run(["chmod", "+x", "/opt/clear_logs.py"], use_sudo=True)
run(["chmod", "+x", "/opt/setup_cronjobs.py"], use_sudo=True)
run(["chmod", "+x", "/var/log/400.py"], use_sudo=True)
run(["chmod", "+x", "/var/log/403.py"], use_sudo=True)
run(["chmod", "+x", "/var/log/alluri.py"], use_sudo=True)

# 14c
run(["/usr/bin/python3", "/opt/setup_cronjobs.py"], use_sudo=True)


# 15. Restart OpenResty
print("=== [15] Restarting OpenResty ===")
run(["systemctl", "enable", "openresty"], use_sudo=True)
run(["systemctl", "restart", "openresty"], use_sudo=True)
run(["systemctl", "status", "openresty"], use_sudo=True)

run(["rm", "-rf", "/root/master.zip"], use_sudo=True)
run(["rm", "-rf", "/root/ModSecurity"], use_sudo=True)
run(["rm", "-rf", "/root/ModSecurity-nginx"], use_sudo=True)
run(["rm", "-rf", "/root/websecurityopenresty.py"], use_sudo=True)
run(["rm", "-rf", "/root/ngx_http_geoip2_module-master"], use_sudo=True)
run(["chmod", "+x", "/root/delete_openresty_files.py"], use_sudo=True)
run(["/usr/bin/python3", "/root/delete_openresty_files.py"], use_sudo=True)
run(["rm", "-rf", "/root/delete_openresty_files.py"], use_sudo=True)

print("\n✅ All Done! ModSecurity WAF and GeoIP restrictions is now active with OpenResty.\n")
