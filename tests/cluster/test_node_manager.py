import unittest
import logging
from unittest.mock import Mock, patch, ANY
from kubernetes.client import V1Node, V1NodeSpec, V1NodeStatus, V1ObjectMeta, V1PodList, V1Pod, V1Deployment, V1DeploymentSpec, V1DeploymentStatus, V1Container, V1PodTemplateSpec, V1LabelSelector, V1PodSpec
import sys
print(sys.path)



class TestNodeManager(unittest.TestCase):
    def setUp(self):
        self.mock_core_v1 = Mock()
        self.mock_apps_v1 = Mock()
        self.mock_config = Mock()
        
        self.patcher = patch.multiple(
            'src.cluster.node_manager',
            client=Mock(
                CoreV1Api=Mock(return_value=self.mock_core_v1),
                AppsV1Api=Mock(return_value=self.mock_apps_v1)
            ),
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
            
    def test_get_available_worker_nodes(self):
        # Create mock nodes with different conditions
        mock_worker_node = V1Node(
            metadata=V1ObjectMeta(name="worker-1", labels={"node-type": "worker"}),
            status=V1NodeStatus(conditions=[Mock(type="Ready", status="True")]),
            spec=V1NodeSpec(unschedulable=False)
        )
        
        mock_cordoned_node = V1Node(
            metadata=V1ObjectMeta(name="worker-2", labels={"node-type": "worker"}),
            status=V1NodeStatus(conditions=[Mock(type="Ready", status="True")]),
            spec=V1NodeSpec(unschedulable=True)
        )
        
        mock_not_ready_node = V1Node(
            metadata=V1ObjectMeta(name="worker-3", labels={"node-type": "worker"}),
            status=V1NodeStatus(conditions=[Mock(type="Ready", status="False")]),
            spec=V1NodeSpec(unschedulable=False)
        )
        
        mock_control_plane = V1Node(
            metadata=V1ObjectMeta(name="control-1", labels={"node-type": "control-plane"}),
            status=V1NodeStatus(conditions=[Mock(type="Ready", status="True")]),
            spec=V1NodeSpec(unschedulable=False)
        )
        
        self.mock_core_v1.list_node.return_value.items = [
            mock_worker_node, mock_cordoned_node, mock_not_ready_node, mock_control_plane
        ]
        
        available_nodes = self.manager.get_available_worker_nodes()
        
        # Should only include the ready, non-cordoned worker node
        self.assertEqual(len(available_nodes), 1)
        self.assertEqual(available_nodes[0], "worker-1")
        
    def test_deploy_model(self):
        # Mock the deployment creation
        self.mock_apps_v1.create_namespaced_deployment.return_value = None
        
        with self.assertLogs(level='INFO') as cm:
            result = self.manager.deploy_model(
                model_name="test-model",
                model_version="v1",
                node_name="worker-1",
                container_image="ml-model:latest"
            )
            
            # Check that the deployment was created
            self.mock_apps_v1.create_namespaced_deployment.assert_called_once()
            
            # Check that the deployment was tracked
            self.assertIn("test-model-v1", self.manager.model_deployments)
            self.assertEqual(self.manager.model_deployments["test-model-v1"]["model_name"], "test-model")
            self.assertEqual(self.manager.model_deployments["test-model-v1"]["node"], "worker-1")
            
            # Check log message
            self.assertTrue(any("Deployed model test-model version v1 to node worker-1" in msg for msg in cm.output))
            
            # Check return value
            self.assertTrue(result)
            
    def test_deploy_model_failure(self):
        # Mock the deployment creation to raise an exception
        self.mock_apps_v1.create_namespaced_deployment.side_effect = Exception("Deployment failed")
        
        with self.assertLogs(level='ERROR') as cm:
            result = self.manager.deploy_model(
                model_name="test-model",
                model_version="v1",
                node_name="worker-1",
                container_image="ml-model:latest"
            )
            
            # Check error log
            self.assertTrue(any("Failed to deploy model test-model" in msg for msg in cm.output))
            
            # Check return value
            self.assertFalse(result)
            
    def test_deploy_distributed_model(self):
        # Mock get_available_worker_nodes to return multiple nodes
        self.manager.get_available_worker_nodes = Mock(return_value=["worker-1", "worker-2", "worker-3"])
        
        # Mock deploy_model to return success
        self.manager.deploy_model = Mock(return_value=True)
        
        with self.assertLogs(level='INFO') as cm:
            result = self.manager.deploy_distributed_model(
                model_name="test-model",
                model_version="v1",
                container_image="ml-model:latest",
                num_shards=2
            )
            
            # Check that deploy_model was called for each shard
            self.assertEqual(self.manager.deploy_model.call_count, 2)
            
            # Check that the correct nodes were used
            self.manager.deploy_model.assert_any_call(
                model_name="test-model-shard0",
                model_version="v1",
                node_name="worker-1",
                container_image="ml-model:latest"
            )
            self.manager.deploy_model.assert_any_call(
                model_name="test-model-shard1",
                model_version="v1",
                node_name="worker-2",
                container_image="ml-model:latest"
            )
            
            # Check log message
            self.assertTrue(any("Deployed test-model in 2 shards" in msg for msg in cm.output))
            
            # Check return value
            self.assertEqual(len(result), 2)
            self.assertIn("test-model-shard0", result)
            self.assertIn("test-model-shard1", result)
            
    def test_deploy_distributed_model_not_enough_nodes(self):
        # Mock get_available_worker_nodes to return fewer nodes than needed
        self.manager.get_available_worker_nodes = Mock(return_value=["worker-1"])
        
        with self.assertLogs(level='WARNING') as cm:
            result = self.manager.deploy_distributed_model(
                model_name="test-model",
                model_version="v1",
                container_image="ml-model:latest",
                num_shards=2
            )
            
            # Check warning log
            self.assertTrue(any("Not enough available nodes (1) for 2 shards" in msg for msg in cm.output))
            
            # Check return value
            self.assertEqual(result, {})
            
    def test_get_model_deployment_status(self):
        # Setup model deployments
        self.manager.model_deployments = {
            "test-model-v1": {
                "model_name": "test-model",
                "version": "v1",
                "node": "worker-1",
                "status": "deploying"
            },
            "test-model-shard0": {
                "model_name": "test-model-shard0",
                "version": "v1",
                "node": "worker-1",
                "status": "deploying"
            },
            "test-model-shard1": {
                "model_name": "test-model-shard1",
                "version": "v1",
                "node": "worker-2",
                "status": "deploying"
            }
        }
        
        # Create a complete mock deployment with all required fields
        container = V1Container(
            name="test-model",
            image="ml-model:latest",
            ports=[Mock(container_port=8080)]
        )
        
        pod_spec = V1PodSpec(
            containers=[container],
            node_selector={"kubernetes.io/hostname": "worker-1"}
        )
        
        pod_template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels={"app": "test-model", "version": "v1"}),
            spec=pod_spec
        )
        
        selector = V1LabelSelector(match_labels={"app": "test-model", "version": "v1"})
        
        deployment_spec = V1DeploymentSpec(
            replicas=1,
            selector=selector,
            template=pod_template
        )
        
        mock_deployment = V1Deployment(
            metadata=V1ObjectMeta(name="test-model-v1"),
            spec=deployment_spec,
            status=V1DeploymentStatus(ready_replicas=1, available_replicas=1)
        )
        
        self.mock_apps_v1.read_namespaced_deployment.return_value = mock_deployment
        
        # Test getting status for all models
        status = self.manager.get_model_deployment_status()
        
        # Check that the status was updated
        self.assertEqual(status["test-model-v1"]["status"], "ready")
        self.assertEqual(status["test-model-v1"]["replicas"], 1)
        self.assertEqual(status["test-model-v1"]["available"], 1)
        
        # Test getting status for a specific model
        status = self.manager.get_model_deployment_status("test-model")
        
        # Check that only the relevant models are returned
        self.assertEqual(len(status), 2)
        self.assertIn("test-model-shard0", status)
        self.assertIn("test-model-shard1", status)
        
    def test_route_inference_request(self):
        # Setup model deployments
        self.manager.model_deployments = {
            "test-model-shard0": {
                "model_name": "test-model-shard0",
                "version": "v1",
                "node": "worker-1",
                "status": "ready"
            },
            "test-model-shard1": {
                "model_name": "test-model-shard1",
                "version": "v1",
                "node": "worker-2",
                "status": "ready"
            }
        }
        
        # Test routing a request
        result = self.manager.route_inference_request("test-model", {"input": "test data"})
        
        # Check that a shard was selected
        self.assertIn("shard", result)
        self.assertIn("node", result)
        self.assertIn("request_id", result)
        self.assertIn("timestamp", result)
        self.assertIn("simulated_result", result)
        
    def test_route_inference_request_no_shards(self):
        # Setup model deployments with no ready shards
        self.manager.model_deployments = {
            "test-model-shard0": {
                "model_name": "test-model-shard0",
                "version": "v1",
                "node": "worker-1",
                "status": "deploying"
            }
        }
        
        # Test routing a request
        result = self.manager.route_inference_request("test-model", {"input": "test data"})
        
        # Check error response
        self.assertIn("error", result)
        self.assertEqual(result["error"], "No ready model shards available")
        
    def test_monitor_inference_performance(self):
        # Setup model deployments
        self.manager.model_deployments = {
            "test-model-shard0": {
                "model_name": "test-model-shard0",
                "version": "v1",
                "node": "worker-1",
                "status": "ready"
            },
            "test-model-shard1": {
                "model_name": "test-model-shard1",
                "version": "v1",
                "node": "worker-2",
                "status": "ready"
            }
        }
        
        # Test monitoring performance
        metrics = self.manager.monitor_inference_performance("test-model")
        
        # Check metrics structure
        self.assertEqual(metrics["model"], "test-model")
        self.assertEqual(metrics["time_window"], 300)
        self.assertEqual(metrics["num_shards"], 2)
        self.assertIn("metrics", metrics)
        self.assertIn("shard_metrics", metrics)
        self.assertEqual(len(metrics["shard_metrics"]), 2)
        
    def test_cleanup_model_deployment(self):
        # Setup model deployments
        self.manager.model_deployments = {
            "test-model-v1": {
                "model_name": "test-model",
                "version": "v1",
                "node": "worker-1",
                "status": "ready"
            }
        }
        
        # Mock deployment list
        mock_deployment = V1Deployment(
            metadata=V1ObjectMeta(name="test-model-v1")
        )
        self.mock_apps_v1.list_namespaced_deployment.return_value.items = [mock_deployment]
        
        with self.assertLogs(level='INFO') as cm:
            result = self.manager.cleanup_model_deployment("test-model")
            
            # Check that the deployment was deleted
            self.mock_apps_v1.delete_namespaced_deployment.assert_called_once_with(
                name="test-model-v1",
                namespace="default"
            )
            
            # Check that the deployment was removed from tracking
            self.assertEqual(len(self.manager.model_deployments), 0)
            
            # Check log message
            self.assertTrue(any("Deleted deployment test-model-v1" in msg for msg in cm.output))
            
            # Check return value
            self.assertTrue(result)
            
    def test_cleanup_model_deployment_failure(self):
        # Mock deployment list to raise an exception
        self.mock_apps_v1.list_namespaced_deployment.side_effect = Exception("Cleanup failed")
        
        with self.assertLogs(level='ERROR') as cm:
            result = self.manager.cleanup_model_deployment("test-model")
            
            # Check error log
            self.assertTrue(any("Failed to cleanup test-model" in msg for msg in cm.output))
            
            # Check return value
            self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
