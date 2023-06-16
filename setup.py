from setuptools import setup, find_packages
from setuptools.command.install import install
from pathlib import Path
import subprocess
import os
import os
import sys
import platform
import requests
import zipfile
import shutil
import tempfile

# def download_rlcone():
#     subprocess.run(["bash", "./scripts/install_rclone.sh"], check=True)


def download_and_install_rclone(beta=False):
    system = platform.system().lower()
    machine = platform.machine()

    if system == "windows":
        arch = "amd64" if machine in ["AMD64"] else "386"
    elif system == "darwin":
        system = "osx"
        arch = "amd64" if machine in ["x86_64", "amd64"] else "386"
    elif system == "linux":
        arch = "amd64" if machine in ["x86_64", "amd64"] else "386"
    else:
        print("OS type not supported")
        sys.exit(2)

    if beta:
        download_url = f"https://beta.rclone.org/rclone-beta-latest-{system}-{arch}.zip"
        rclone_zip = f"rclone-beta-latest-{system}-{arch}.zip"
    else:
        download_url = f"https://downloads.rclone.org/rclone-current-{system}-{arch}.zip"
        rclone_zip = f"rclone-current-{system}-{arch}.zip"

    print(f"Downloading rclone from {download_url}...")

    resp = requests.get(download_url)

    with open(rclone_zip, 'wb') as f_out:
        f_out.write(resp.content)

    print(f"Unzipping {rclone_zip}...")

    with zipfile.ZipFile(rclone_zip, 'r') as zip_ref:
        zip_ref.extractall("./")

    print("Moving rclone binary to appropriate directory...")

    if system == "windows":
        try:
            shutil.move("./rclone.exe", "C:/Windows/System32/rclone.exe")
        except PermissionError:
            print("Permission denied. You might need to run this script as Administrator.")
    else:
        try:
            shutil.move("./rclone", "/usr/bin/")
            os.chmod("/usr/bin/rclone", 0o755)
        except PermissionError:
            print("Permission denied. You might need to run this script as root.")


download_and_install_rclone()

setup(
    name="ablator",
    version="0.0.1b2",
    author="Iordanis Fostiropoulos",
    author_email="dev@iordanis.xyz",
    url="https://iordanis.xyz",
    packages=find_packages(),
    description="Model Ablation Tool-Kit",
    python_requires=">3.10",
    long_description=Path(__file__).parent.joinpath("README.md").read_text(),
    long_description_content_type="text/markdown",
    install_requires=[
        "numpy==1.24.1",
        "pandas==2.0.0",
        "scikit-learn==1.2.2",
        "torch==1.13.1",
        "torchvision==0.14.1",
        "tqdm==4.64.1",
        "tensorboardX==2.6",
        "matplotlib==3.7.1",
        "omegaconf==2.2.3",
        "scipy==1.10.1",
        "setproctitle==1.3.2",
        "ray>=2.1.0,<=2.2.0",
        "pynvml==11.5.0",
        "optuna==3.1.1",
        "tabulate==0.9.0",
        "seaborn==0.12.2",
        "numpydoc==1.5.0",
    ],
    extras_require={
        "dev": [
            "mypy==1.2.0",
            "pytest==7.3.0",
            "black==23.3.0",
            "flake8==6.0.0",
            "pylint==2.17.2",
            "tensorboard==2.12.2",
        ],
    },
)
