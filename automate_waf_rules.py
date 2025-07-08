#!/usr/bin/env python3

import subprocess
import os
import time
import shutil

def run_command(command, shell=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(command, shell=shell, check=True,
                              capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def main():
    temp_dir = "/root/automate_waf_rules"

    try:
        # Create the temporary directory if it doesn't exist
        print(f"Creating temporary directory: {temp_dir}")
        os.makedirs(temp_dir, exist_ok=True)

        # Backup modsecurity configuration
        print("Backing up modsecurity configuration...")
        os.chdir("/usr/local/openresty/nginx/modsecurity-crs")
        shutil.copy2("crs-setup.conf", temp_dir)

        os.chdir("rules")
        shutil.copy2("REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf", temp_dir)

        # Clone the new ModSecurity CRS repository
        print("Cloning new ModSecurity CRS repository...")
        os.chdir(temp_dir)
        success, stdout, stderr = run_command("git clone https://github.com/coreruleset/coreruleset modsecurity-crs")
        if not success:
            print(f"Git clone failed: {stderr}")
            return

        # Wait for 2 minutes before continuing
        print("Waiting for 2 minutes...")
        time.sleep(120)

        # Clean up the example configuration files
        print("Cleaning up example configuration files...")
        os.chdir("modsecurity-crs")
        if os.path.exists("crs-setup.conf.example"):
            os.remove("crs-setup.conf.example")

        os.chdir("rules")
        if os.path.exists("REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf.example"):
            os.remove("REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf.example")

        # Move the backed-up files into the new CRS directory
        print("Moving backed-up files...")
        os.chdir(temp_dir)
        shutil.move("crs-setup.conf", "modsecurity-crs/")
        shutil.move("REQUEST-900-EXCLUSION-RULES-BEFORE-CRS.conf", "modsecurity-crs/rules/")

        # Replace the old modsecurity-crs with the new one
        print("Replacing old modsecurity-crs...")
        os.chdir("/usr/local/openresty/nginx/")
        if os.path.exists("modsecurity-crs"):
            shutil.rmtree("modsecurity-crs")
        shutil.move(f"{temp_dir}/modsecurity-crs", "/usr/local/openresty/nginx/")

        # Test the OpenResty configuration
        print("Testing OpenResty configuration...")
        success, stdout, stderr = run_command("openresty -t")

        if success:
            print("OpenResty configuration test passed.")

            # Reload OpenResty configuration
            print("Reloading OpenResty configuration...")
            reload_success, reload_stdout, reload_stderr = run_command("openresty -s reload")

            if reload_success:
                print("OpenResty configuration reloaded successfully.")
            else:
                print(f"OpenResty reload failed: {reload_stderr}")
        else:
            print(f"OpenResty configuration test failed: {stderr}")
            print("Please check the configuration.")

    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)
            print("Temporary directory removed successfully.")

if __name__ == "__main__":
    main()
