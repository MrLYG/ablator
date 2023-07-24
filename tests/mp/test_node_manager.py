from pathlib import Path
import time
import sys
import pytest
import ray
from ablator.mp.node_manager import NodeManager, Resource


# @pytest.mark.skipif(sys.platform != 'linux', reason="CI doesn't support MacOS and Windows")
def test_node_manager(tmp_path: Path, ray_cluster):
    # TODO py-test clean-ups
    timeout = 1200
    n_nodes = 2
    manager = NodeManager(tmp_path)
    results = manager.run_cmd("whoami", timeout=timeout)
    test_ips = ray_cluster.node_ips()
    for node, result in results.items():
        node_username, node_ip = node.split("@")
        test_ips.remove(node_ip)
        assert result.strip() == node_username
    assert len(test_ips) == 0

    results = manager.run_cmd("whoami", timeout=timeout)
    # reultes {node_ip: node_username, ...}
    print(results)

    assert (
        len(results) == len(ray_cluster.node_ips()) and len(results) == n_nodes + 1
    )  # +1 for the head node
    ray_cluster.kill_node(0)
    n_nodes -= 1
    results = manager.run_cmd("whoami", timeout=timeout)
    assert (
        len(results) == len(ray_cluster.node_ips()) and len(results) == n_nodes + 1
    )  # +1 for the head node

    assert (
        len(results) == len(ray_cluster.node_ips()) and len(results) == n_nodes + 1
    )  # +1 for the head node
    ray_cluster.kill_node(0)
    n_nodes -= 1
    results = manager.run_cmd("whoami", timeout=timeout)
    assert (
        len(results) == len(ray_cluster.node_ips()) and len(results) == n_nodes + 1
    )  # +1 for the head node

    def wait_for_append_nodes(num, max_wait_time=50, output_fn=True):
        start_time = time.time()
        while True:
            results = manager.run_cmd("whoami", timeout=timeout)
            if time.time() - start_time > max_wait_time:
                raise RuntimeError("Timed out waiting for append nodes.")
            if output_fn:
                print(results)
            if len(results) > num:
                break
            time.sleep(0.1)

    ray_cluster.append_nodes(1)
    wait_for_append_nodes(1)
    n_nodes += 1
    results = manager.run_cmd("whoami", timeout=timeout)
    # reultes {node_ip: node_username, ...}
    print(results)
    assert (
        len(results) == len(ray_cluster.node_ips()) and len(results) == n_nodes + 1
    )  # +1 for the head node

    ray_cluster.kill_all()

    results = manager.run_cmd("whoami", timeout=timeout)
    assert len(results) == 1  # the head node

    ray.shutdown()
    try:
        results = manager.run_cmd("whoami", timeout=5)
    except Exception as e:
        assert "Ray has not been started yet." in str(e)

    # NOTE test restarting ray and NodeManager
    ray_cluster = type(ray_cluster)(nodes=0)
    ray_cluster.setUp(Path(__file__).parent)
    manager = NodeManager(tmp_path, ray_address=ray_cluster.cluster_ip)
    results = manager.run_cmd("whoami", timeout=timeout)
    assert len(results) == 1  # the head node
    ray_cluster.append_nodes(2)
    results = manager.run_cmd("whoami", timeout=timeout)

    assert len(results) == len(ray_cluster.node_ips())
    ray_cluster.kill_all()
    results = manager.run_cmd("whoami", timeout=timeout)
    assert len(results) == 1  # the head node
