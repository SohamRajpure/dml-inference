from unittest.mock import Mock, patch
import pytest
from src.cluster.node_manager import NodeManager
import sys
print(sys.path)  # Should include /path/to/dml-inference/src

@pytest.fixture
def mock_k8s_client():
    with patch('kubernetes.client.CoreV1Api') as mock_core_v1:
        yield mock_core_v1()

@pytest.fixture
def node_manager(mock_k8s_client):
    return NodeManager()

def test_label_node(node_manager, mock_k8s_client):
    # Test label application
    test_labels = {"inference-tier": "primary"}
    node_manager.label_node("worker-node-1", test_labels)
    
    # Verify patch_node called with correct args
    mock_k8s_client.patch_node.assert_called_once_with(
        "worker-node-1",
        {"metadata": {"labels": test_labels}}
    )

def test_cordon_node(node_manager, mock_k8s_client):
    node_manager.cordon_node("worker-node-2")
    mock_k8s_client.patch_node.assert_called_once_with(
        "worker-node-2",
        {"spec": {"unschedulable": True}}
    )

def test_drain_node(node_manager, mock_k8s_client):
    # Mock pod list response
    mock_pod = Mock()
    mock_pod.metadata = Mock(name="pod-1", namespace="default")
    mock_k8s_client.list_pod_for_all_namespaces.return_value.items = [mock_pod]

    node_manager.drain_node("worker-node-3")
    
    # Verify eviction and cordon
    mock_k8s_client.delete_namespaced_pod.assert_called_once_with(
        name="pod-1",
        namespace="default",
        body=ANY  # Use unittest.mock.ANY for complex objects
    )
    mock_k8s_client.patch_node.assert_called_with(
        "worker-node-3",
        {"spec": {"unschedulable": True}}
    )