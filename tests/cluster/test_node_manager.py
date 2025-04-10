import unittest
import logging
from unittest.mock import Mock, patch, ANY
from kubernetes.client import V1Node, V1NodeSpec, V1NodeStatus, V1ObjectMeta, V1PodList, V1Pod
import sys
print(sys.path)



class TestNodeManager(unittest.TestCase):
    def setUp(self):
        self.mock_core_v1 = Mock()
        self.mock_config = Mock()
        
        self.patcher = patch.multiple(
            'src.cluster.node_manager',
            client=Mock(CoreV1Api=Mock(return_value=self.mock_core_v1)),
            config=Mock(load_kube_config=self.mock_config)
        )
        self.patcher.start()
        
        from src.cluster.node_manager import NodeManager
        self.manager = NodeManager()
        
        # Setup logging capture
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.handler = logging.StreamHandler()
        self.logger.addHandler(self.handler)

    def tearDown(self):
        self.patcher.stop()
        self.logger.removeHandler(self.handler)

    def test_list_nodes(self):
        mock_node = V1Node(
            metadata=V1ObjectMeta(name="node-1", labels={"role": "worker"}),
            status=V1NodeStatus(conditions=[Mock(type="Ready", status="True")])
        )
        self.mock_core_v1.list_node.return_value.items = [mock_node]

        with self.assertLogs(level='INFO') as cm:
            self.manager.list_nodes()
            self.assertTrue(any("Node Name: node-1" in msg for msg in cm.output))
            self.assertTrue(any("Labels: {'role': 'worker'}" in msg for msg in cm.output))

    def test_label_node(self):
        test_labels = {"environment": "test"}
        with self.assertLogs(level='INFO') as cm:
            self.manager.label_node("node-1", test_labels)
            self.assertTrue(any("Applied labels {'environment': 'test'} to node node-1" in msg for msg in cm.output))

    def test_cordon_node(self):
        with self.assertLogs(level='INFO') as cm:
            self.manager.cordon_node("node-2")
            self.mock_core_v1.patch_node.assert_called_once_with(
                "node-2",
                {"spec": {"unschedulable": True}}
            )
            self.assertTrue(any("Node node-2 cordoned" in msg for msg in cm.output))

    def test_drain_node(self):
        mock_pod = V1Pod(
            metadata=V1ObjectMeta(name="pod-1", namespace="default")
        )
        self.mock_core_v1.list_pod_for_all_namespaces.return_value = V1PodList(items=[mock_pod])

        with self.assertLogs(level='INFO') as cm:
            self.manager.drain_node("node-3")
            self.assertTrue(any("Evicted pod pod-1 from node node-3" in msg for msg in cm.output))

    def test_monitor_nodes(self):
        mock_node = V1Node(
            metadata=V1ObjectMeta(name="bad-node"),
            status=V1NodeStatus(conditions=[
                Mock(type="Ready", status="False"),
                Mock(type="DiskPressure", status="True")
            ])
        )
        self.mock_core_v1.list_node.return_value.items = [mock_node]

        with self.assertLogs(level='WARNING') as cm:
            self.manager.monitor_nodes()
            self.assertTrue(any("Node bad-node is not Ready" in msg for msg in cm.output))

if __name__ == "__main__":
    unittest.main()
