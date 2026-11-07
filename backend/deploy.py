import os
import shutil
import subprocess
import sys
import zipfile


def main():
    print("Creating Lambda deployment package...")

    # Clean up
    if os.path.exists("lambda-package"):
        shutil.rmtree("lambda-package")
    if os.path.exists("lambda-deployment.zip"):
        os.remove("lambda-deployment.zip")

    # Create package directory
    os.makedirs("lambda-package")

    # Install dependencies for the Lambda runtime.
    #
    # We do NOT use Docker here. pip can cross-build a package for Lambda's
    # platform directly by naming the target explicitly, which is AWS's own
    # documented approach. Running pip inside an emulated linux/amd64 container
    # on Apple Silicon routes downloads through Docker Desktop's network stack,
    # which throttles sustained transfers badly enough that pip hits its read
    # timeout mid-download and aborts the whole install.
    #
    # --platform / --python-version / --only-binary pin the wheels to Lambda's
    # runtime regardless of the machine running this script, so the output is
    # identical on macOS arm64 and on a Linux CI runner.
    print("Installing dependencies for Lambda runtime (python3.12, x86_64)...")

    # Prefer uv when present: it is the project's toolchain, it is far faster,
    # and `uv run deploy.py` executes under a venv that has no pip at all.
    if shutil.which("uv"):
        install_cmd = [
            "uv",
            "pip",
            "install",
            "--target",
            "lambda-package",
            "-r",
            "requirements.txt",
            "--python-platform",
            "x86_64-manylinux2014",
            "--python-version",
            "3.12",
            "--only-binary",
            ":all:",
        ]
    else:
        install_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            "lambda-package",
            "-r",
            "requirements.txt",
            "--platform",
            "manylinux2014_x86_64",
            "--python-version",
            "3.12",
            "--implementation",
            "cp",
            "--only-binary=:all:",
            "--upgrade",
            # Survive a slow or flaky link instead of failing the build.
            "--retries",
            "10",
            "--timeout",
            "120",
        ]

    subprocess.run(install_cmd, check=True)

    # Copy application files
    print("Copying application files...")
    for file in ["server.py", "lambda_handler.py", "context.py", "resources.py"]:
        if os.path.exists(file):
            shutil.copy2(file, "lambda-package/")
    
    # Copy data directory
    if os.path.exists("data"):
        shutil.copytree("data", "lambda-package/data")

    # Create zip
    print("Creating zip file...")
    with zipfile.ZipFile("lambda-deployment.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("lambda-package"):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, "lambda-package")
                zipf.write(file_path, arcname)

    # Show package size
    size_mb = os.path.getsize("lambda-deployment.zip") / (1024 * 1024)
    print(f"✓ Created lambda-deployment.zip ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()