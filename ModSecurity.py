#!/usr/bin/env python3
import subprocess
import os
import sys

def run(cmd, cwd=None, env=None, use_sudo=False):
    final_cmd = cmd
    if use_sudo:
        final_cmd = ["sudo"] + cmd
    print(f"\n=== Running: {' '.join(final_cmd)} ===\n")
    result = subprocess.run(final_cmd, cwd=cwd, env=env)
    if result.returncode != 0:
        print(f"❌ Command failed: {' '.join(final_cmd)}")
        sys.exit(1)

# 1. Clone ModSecurity
run(["git", "clone", "https://github.com/SpiderLabs/ModSecurity"], cwd=os.path.expanduser("~"))

modsec_dir = os.path.join(os.path.expanduser("~"), "ModSecurity")

# 2. Init and update submodules
run(["git", "submodule", "init"], cwd=modsec_dir)
run(["git", "submodule", "update"], cwd=modsec_dir)

# 3. Run build.sh
run(["./build.sh"], cwd=modsec_dir)

# 4. Run ./configure
run(["./configure"], cwd=modsec_dir)

# 5. make
run(["make"], cwd=modsec_dir)

# 6. sudo make install
run(["make", "install"], cwd=modsec_dir, use_sudo=True)

print("\n✅ ModSecurity installed successfully.\n")
