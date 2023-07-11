from typing import Optional
import pytest
from pathlib import Path
from ablator.modules.storage.cloud import GcpConfig
from unittest import mock
import socket
import torch
import os
from unittest.mock import patch, MagicMock
from ablator.modules.loggers.file import FileLogger


def assert_error_msg(fn, error_msg):
    try:
        fn()
        assert False
    except Exception as excp:
        if not error_msg == str(excp):
            raise excp


def write_rand_tensors(tmp_path: Path, n=2):
    tensors = []
    for i in range(n):
        a = torch.rand(100)
        torch.save(a, tmp_path.joinpath(f"t_{i}.pt"))
        tensors.append(a)
    return tensors


def load_rand_tensors(tmp_path: Path, n=2):
    tensors = []
    for i in range(n):
        a = torch.load(tmp_path.joinpath(f"t_{i}.pt"))
        tensors.append(a)
    return tensors


def assert_tensor_list_eq(a, b):
    assert all([all(_a == _b) for _a, _b in zip(a, b)])


def assert_tensor_list_diff(a, b):
    assert all([all(_a != _b) for _a, _b in zip(a, b)])


def mock_list_bucket_error_cmd(self, destination: str | None = None):
    destination = (
        Path(self.bucket) / destination
        if destination is not None
        else Path(self.bucket)
    )
    cmd = ["gsutil", "ls", f"gs://{destination}"]
    raise Exception(f"There was an error running `{' '.join(cmd)}`. "
                    "Make sure gsutil is installed and that the destination exists. `CommandException: One or more URLs matched no objects.`")


def test_gcp(tmp_path: Path, bucket: str = "gs://iordanis/"):

    mock_gs_path = f"{tmp_path}/gs"
    bucket_name = bucket.lstrip('gs:').lstrip('/').rstrip('/')
    os.makedirs(f"{mock_gs_path}/{bucket_name}")

    rand_folder = f"{torch.rand(1).item()}"

    tmp_path = tmp_path/"localhost"
    os.mkdir(tmp_path)
    rand_destination = bucket + rand_folder
    # GcpConfig(bucket=rand_destination)._make_process(["gsutil", "-m", "rm", "-rf", rand_destination], verbose=False)

    def mock_make_cmd_up(self, local_path: Path, destination: str):
        os.mkdir(f"{mock_gs_path}/{bucket_name}/{rand_folder}")
        destination = Path(self.bucket) / destination / local_path.name
        src = local_path
        cmd = ["rsync", "-r"]
        if self.exclude_glob is not None:
            cmd += ["--exclude", f"{self.exclude_glob}"]
        if self.exclude_chkpts:
            cmd += ["--exclude", "*.pt"]
        cmd += [f"{src}/", f"{mock_gs_path}/{destination}"]
        return cmd

    def mock_make_cmd_down(self, src_path: str, local_path: Path):
        src = Path(self.bucket) / src_path / local_path.name
        destination = local_path
        cmd = ["rsync", "-rI"]
        cmd += [f"{mock_gs_path}/{src}/", f"{destination}"]
        return cmd

    def mock_list_bucket(self, destination: str | None = None):
        destination = (
            Path(self.bucket) / destination
            if destination is not None
            else Path(self.bucket)
        )
        cmd = ["ls", f"{mock_gs_path}/{destination}"]

        p = self._make_process(cmd, verbose=False)
        stdout, stderr = p.communicate()
        assert len(stderr) == 0, (
            f"There was an error running `{' '.join(cmd)}`. "
            "Make sure gsutil is installed and that the destination exists. "
            f"`{stderr.decode('utf-8').strip()}`"
        )
        return stdout.decode("utf-8").strip().split("\n")
    with mock.patch("ablator.modules.storage.cloud.GcpConfig.list_bucket", mock_list_bucket_error_cmd):
        assert_error_msg(
            lambda: GcpConfig(bucket=rand_destination),
            f"There was an error running `gsutil ls {rand_destination}`. Make sure gsutil is installed and that the destination exists. `CommandException: One or more URLs matched no objects.`",
        )
    with mock.patch("ablator.modules.storage.cloud.GcpConfig._find_gcp_nodes", return_value={}):
        with mock.patch("ablator.modules.storage.cloud.GcpConfig.list_bucket", mock_list_bucket):
            with mock.patch("socket.gethostname", return_value="localhost"):
                assert_error_msg(
                    lambda: GcpConfig(bucket=bucket),
                    f"Can only use GcpConfig from Google Cloud Server. Consider switching to RemoteConfig.",
                )

    with mock.patch("socket.gethostname", return_value="gcp-machine1"):
        with mock.patch("socket.gethostbyname", return_value="111.111.111.111"):
            with mock.patch("ablator.modules.storage.cloud.GcpConfig._find_gcp_nodes", return_value=[{"networkInterfaces": [{"networkIP": "111.111.111.111"}]}]):
                with mock.patch("ablator.modules.storage.cloud.GcpConfig.list_bucket", mock_list_bucket):
                    with mock.patch("ablator.modules.storage.cloud.GcpConfig._make_cmd_up", mock_make_cmd_up):
                        cfg = GcpConfig(bucket=bucket)
                        files = cfg.list_bucket()
                        original_tensors = write_rand_tensors(tmp_path)
                        cfg.rsync_up(tmp_path, rand_folder)

    with mock.patch("ablator.modules.storage.cloud.GcpConfig.list_bucket", mock_list_bucket):
        new_files = cfg.list_bucket()
    rand_destination = rand_folder
    assert set(new_files).difference(files) == {rand_destination}
    uploaded_files = None
    with mock.patch("ablator.modules.storage.cloud.GcpConfig.list_bucket", mock_list_bucket):
        uploaded_files = cfg.list_bucket(rand_folder + "/" + tmp_path.name)
    assert len(uploaded_files) == 2
    # Replace original tensors
    new_tensors = write_rand_tensors(tmp_path)
    assert_tensor_list_diff(original_tensors, new_tensors)
    loaded_tensors = load_rand_tensors(tmp_path=tmp_path)
    assert_tensor_list_eq(loaded_tensors, new_tensors)
    # Update the local tensors with the original tensors from gcp

    with mock.patch("ablator.modules.storage.cloud.GcpConfig._make_cmd_down", mock_make_cmd_down):
        cfg.rsync_down(rand_folder, tmp_path, verbose=False)
    loaded_tensors = load_rand_tensors(tmp_path=tmp_path)
    assert_tensor_list_eq(loaded_tensors, original_tensors)

    # Update a mock node from gcp

    hostname = "localhost"
    mock_node_path = tmp_path.joinpath(hostname).joinpath(tmp_path.name)

    def mock_rsync_down_node(
        self,
        node_hostname,
        remote_path: str,
        local_path: Path,
        logger: FileLogger | None = None,
        verbose=True,
    ):
        os.makedirs(local_path)
        cmd = self._make_cmd_down(remote_path, local_path)
        p = self._make_process(cmd, verbose)
        hostname = socket.gethostname()
        if logger is not None:
            logger.info(f"Rsync {cmd[-2]} to {hostname}:{cmd[-1]}")
        p.wait()
    with mock.patch("ablator.modules.storage.cloud.GcpConfig._make_cmd_down", mock_make_cmd_down):
        with mock.patch("ablator.modules.storage.cloud.GcpConfig.rsync_down_node", mock_rsync_down_node):
            cfg.rsync_down_node(hostname, rand_folder, mock_node_path)
    node_tensors = load_rand_tensors(tmp_path=mock_node_path)
    assert_tensor_list_eq(node_tensors, original_tensors)
    # TODO teardown refactoring
    cmd = ["rm", "-rf", f"{mock_gs_path}/{bucket_name}/{rand_destination}"]

    p = cfg._make_process(cmd, verbose=False)
    out, err = p.communicate()
    assert len(out) == 0


@pytest.fixture
def gcp_config():
    return GcpConfig(bucket="gs://iordanis/")


def test_init(gcp_config):
    assert gcp_config.bucket == 'gs://iordanis/'
    assert gcp_config.exclude_glob is None
    assert not gcp_config.exclude_chkpts


def test_make_cmd_up(gcp_config):
    cmd = gcp_config._make_cmd_up(Path('file.txt'), 'dest_folder')
    assert cmd[-1] == 'gs://iordanis/dest_folder/file.txt'
    assert cmd[-2] == 'file.txt'


def test_make_cmd_down(gcp_config):
    cmd = gcp_config._make_cmd_down('src_folder/file.txt', Path('.'))
    assert cmd[-1] == '.'
    assert cmd[-2] == 'gs://iordanis/src_folder/file.txt'


def test_list_bucket(gcp_config, monkeypatch):
    def mock_communicate():
        return (b'file1.txt\nfile2.txt', b'')
    monkeypatch.setattr('subprocess.Popen.communicate', mock_communicate)
    files = gcp_config.list_bucket()
    assert files == ['file1.txt', 'file2.txt']


@patch('subprocess.Popen')
def test_find_gcp_nodes(mock_popen):
    # mock the Popen instance
    mock_p = MagicMock()
    # set the return values for `communicate` method
    mock_p.communicate.return_value = (b'[{"name": "node1"}]', b'')
    mock_popen.return_value = mock_p

    gcp_config = GcpConfig(bucket='test_bucket')

    # Test with a specific hostname
    nodes = gcp_config._find_gcp_nodes('node1')
    assert len(nodes) == 1
    assert nodes[0]['name'] == 'node1'

    # Test without a specific hostname
    nodes = gcp_config._find_gcp_nodes()
    assert len(nodes) == 1
    assert nodes[0]['name'] == 'node1'


@patch('subprocess.Popen')
def test_list_bucket(mock_popen):
    # mock the Popen instance
    mock_p = MagicMock()
    # set the return values for `communicate` method
    mock_p.communicate.return_value = (b'file1.txt\nfile2.txt\n', b'')
    mock_popen.return_value = mock_p

    gcp_config = GcpConfig(bucket='test_bucket')

    # Test with a specific destination
    files = gcp_config.list_bucket('test_destination')
    assert len(files) == 2
    assert files[0] == 'file1.txt'
    assert files[1] == 'file2.txt'

    # Test without a specific destination
    files = gcp_config.list_bucket()
    assert len(files) == 2
    assert files[0] == 'file1.txt'
    assert files[1] == 'file2.txt'


if __name__ == "__main__":
    import shutil

    bucket = "gs://iordanis/"

    rand_folder = f"aabb"
    rand_destination = bucket + rand_folder
    try:
        p = GcpConfig(bucket=rand_destination)._make_process(
            ["gsutil", "-m", "rm", "-rf", rand_destination], verbose=False
        )
        p.wait()
    except:
        pass
    tmp_path = Path("/tmp/gcp_test")
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(exist_ok=True)
    test_gcp(tmp_path, bucket)
    breakpoint()

    pass
