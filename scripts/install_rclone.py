import os
import sys
import platform
import urllib.request
import zipfile
import glob
import shutil
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "ablator"))
PATH_EXTRACT_ZIP_TO = os.path.abspath(os.path.join(CURRENT_DIR, "..", "rclone_installing"))


def get_system_architecture():
    system = platform.system().lower()
    machine = platform.machine()

    if system == "windows":
        arch = "amd64" if machine == "AMD64" else "386"
    elif system in ["darwin", "linux"]:
        arch = "amd64" if machine in ["x86_64", "amd64"] else "386"
    else:
        logging.error("Unsupported OS type")
        sys.exit(2)

    return system, arch


def get_rclone_download_url(system, arch, beta=False):
    version = "beta" if beta else "current"
    rclone_zip = f"rclone-{version}-latest-{system}-{arch}.zip"
    download_url = f"https://downloads.rclone.org/{rclone_zip}" if not beta else f"https://beta.rclone.org/{rclone_zip}"

    return download_url, rclone_zip


def find_rclone(known_part, unknown_part):
    pattern = os.path.join(known_part, unknown_part)
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def install_rclone(binary_path, destination_path):
    try:
        shutil.move(binary_path, destination_path)
    except PermissionError:
        logging.error("Permission denied. You might need to run this script as Administrator." if platform.system().lower() == "windows" else "Permission denied. You might need to run this script as root.")
        sys.exit(1)


def make_executable(file_path):
    if platform.system().lower() != "windows":
        os.chmod(file_path, 0o755)


def create_rclone_config(rclone_env_path):
    config_filename = "rclone.conf"
    config = {
        "gcs": {
            'type': 'google cloud storage',
            'project_number': "project_number",
            'service_account_file': "service_account_file",
            'object_acl': 'private',
            'bucket_acl': 'private',
            'location': 'us',
            'storage_class': 'STANDARD'
        }
    }
    config_content = '\n'.join(f'[{name}]\n' + '\n'.join(f'{k} = {v}' for k, v in settings.items()) for name, settings in config.items())

    os.makedirs(rclone_env_path, exist_ok=True)
    config_path = os.path.join(rclone_env_path, config_filename)
    # Why I create a file to set config rather than using tempfiler.NamedTemporaryFile
    # Cause it has bug on windows, see https://bugs.python.org/issue14243
    with open(config_path, "w") as f:
        f.write(config_content)
    logging.info(f"Rclone configuration file has been written to {config_path}")


def cleanup(files_and_dirs_to_remove):
    for item in files_and_dirs_to_remove:
        if os.path.exists(item):
            if os.path.isfile(item):
                os.remove(item)
            else:
                shutil.rmtree(item)


def download_and_install_rclone(beta=False):
    # Get system and architecture information
    system, arch = get_system_architecture()

    # Get download url and zip file name
    download_url, rclone_zip = get_rclone_download_url(system, arch, beta)

    # Download rclone zip file
    urllib.request.urlretrieve(download_url, rclone_zip)

    # Extract the rclone zip file
    with zipfile.ZipFile(rclone_zip, 'r') as zip_ref:
        zip_ref.extractall(PATH_EXTRACT_ZIP_TO)

    # Install rclone binary
    rclone_binary = find_rclone(PATH_EXTRACT_ZIP_TO, "*/rclone.exe" if system == "windows" else "*/rclone")
    if not rclone_binary:
        logging.error("No rclone binary found in the downloaded package.")
        sys.exit(1)

    install_rclone(rclone_binary, os.path.join(PROJECT_PATH, "rclone.exe" if system == "windows" else "rclone"))

    # Make rclone binary executable
    make_executable(os.path.join(PROJECT_PATH, "rclone.exe" if system == "windows" else "rclone"))

    # Create rclone default configuration file
    create_rclone_config(PROJECT_PATH)

    # Clean up downloaded and extracted files
    cleanup([rclone_zip, PATH_EXTRACT_ZIP_TO])


if __name__ == "__main__":
    download_and_install_rclone()
    logging.info('Rclone installation completed successfully.')
    sys.exit(0)
