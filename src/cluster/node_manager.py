import logging
from kubernetes import client, config
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

PORT = 8080

class NodeManager:
    def __init__(self):
        config.load_kube_config()
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.model_deployments = {}  # Track deployed models and their locations

    #Lists all nodes and their conditions
    def list_nodes(self):
        nodes = self.core_v1.list_node().items
        for node in nodes:
            logger.info(f"Node Name: {node.metadata.name}")
            logger.info(f"Labels: {node.metadata.labels}")
            logger.info(f"Conditions: {[c.type for c in node.status.conditions if c.status == 'True']}")
            logger.info("-" * 40)
        
    #Adds or updates labels on a specific node.
    def label_node(self, node_name, labels):
        body = {
            "metadata": {
                "labels": labels
            }
        }
        self.core_v1.patch_node(node_name, body)
        logger.info(f"Applied labels {labels} to node {node_name}")

    #Marks a node as unschedulable to prevent new workloads from being scheduled.
    def cordon_node(self, node_name):
        body = {
            "spec": {
                "unschedulable": True
            }
        }
        self.core_v1.patch_node(node_name, body)
        logger.info(f"Node {node_name} cordoned")

    #Removes the unschedulable flag from a node.
    def uncordon_node(self, node_name):
        body = {
            "spec": {
                "unschedulable": False
            }
        }
        self.core_v1.patch_node(node_name, body)
        logger.info(f"Node {node_name} uncordoned")

    #Evicts all pods from a node and marks it as unschedulable.
    def drain_node(self, node_name):
        pods = self.core_v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}").items
        for pod in pods:
            if pod.metadata.deletion_grace_period_seconds is None:
                self.core_v1.delete_namespaced_pod(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    body=client.V1DeleteOptions(grace_period_seconds=0)
                )
                logger.info(f"Evicted pod {pod.metadata.name} from node {node_name}")
        self.cordon_node(node_name)

    #Monitors the health and readiness of all nodes.
    def monitor_nodes(self):
        nodes = self.core_v1.list_node().items
        for node in nodes:
            conditions = {c.type: c.status for c in node.status.conditions}
            if conditions.get("Ready") != "True":
                logger.warning(f"Node {node.metadata.name} is not Ready")
    
    # Get available worker nodes for model deployment
    def get_available_worker_nodes(self) -> List[str]:
        """Get a list of available worker nodes for model deployment."""
        available_nodes = []
        nodes = self.core_v1.list_node().items
        
        for node in nodes:
            # Check if node is ready
            is_ready = any(c.type == "Ready" and c.status == "True" for c in node.status.conditions)
            if not is_ready:
                continue
                
            # Check if node is not cordoned
            if node.spec and node.spec.unschedulable:
                continue
                
            # Check if node has worker label
            labels = node.metadata.labels or {}
            if labels.get("node-type") == "worker":
                available_nodes.append(node.metadata.name)
                
        logger.info(f"Found {len(available_nodes)} available worker nodes")
        return available_nodes
    
    # Deploy a model to a specific node
    def deploy_model(self, model_name: str, model_version: str, node_name: str, 
                    container_image: str) -> bool:
        """Deploy an ML model to a specific node."""
        # Create a deployment for the model
        deployment_name = f"{model_name}-{model_version}"
        
        # Define the container
        container = client.V1Container(
            name=model_name,
            image=container_image,
            ports=[client.V1ContainerPort(container_port=PORT)]
        )
        
        # Define the pod template
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": model_name, "version": model_version}),
            spec=client.V1PodSpec(
                containers=[container],
                node_selector={"kubernetes.io/hostname": node_name}
            )
        )
        
        # Define the deployment spec
        spec = client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(
                match_labels={"app": model_name, "version": model_version}
            ),
            template=template
        )
        
        # Create the deployment
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=deployment_name),
            spec=spec
        )
        
        try:
            self.apps_v1.create_namespaced_deployment(
                namespace="default",
                body=deployment
            )
            
            # Track the deployment
            self.model_deployments[deployment_name] = {
                "model_name": model_name,
                "version": model_version,
                "node": node_name,
                "status": "deploying"
            }
            
            logger.info(f"Deployed model {model_name} version {model_version} to node {node_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to deploy model {model_name}: {str(e)}")
            return False
    
    # Deploy a model in a distributed manner across multiple nodes
    def deploy_distributed_model(self, model_name: str, model_version: str, 
                               container_image: str, num_shards: int) -> Dict[str, str]:
        """Deploy a model in a distributed manner across multiple nodes."""
        # Get available worker nodes
        available_nodes = self.get_available_worker_nodes()
        
        if len(available_nodes) < num_shards:
            logger.warning(f"Not enough available nodes ({len(available_nodes)}) for {num_shards} shards")
            return {}
        
        # Select nodes for deployment
        selected_nodes = available_nodes[:num_shards]
        deployment_map = {}
        
        # Deploy each shard
        for i, node in enumerate(selected_nodes):
            shard_name = f"{model_name}-shard{i}"
            success = self.deploy_model(
                model_name=shard_name,
                model_version=model_version,
                node_name=node,
                container_image=container_image
            )
            
            if success:
                deployment_map[shard_name] = node
        
        logger.info(f"Deployed {model_name} in {len(deployment_map)} shards")
        return deployment_map
    
    # Get the status of model deployments
    def get_model_deployment_status(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get the status of model deployments."""
        if model_name:
            # Filter for specific model
            deployments = {k: v for k, v in self.model_deployments.items() 
                          if v["model_name"] == model_name}
        else:
            deployments = self.model_deployments
            
        # Update status from Kubernetes
        for deployment_name, info in deployments.items():
            try:
                # Fetch deployment status from Kubernetes
                deployment = self.apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace="default"
                )
                
                # Update status based on deployment
                if deployment.status.ready_replicas == deployment.spec.replicas:
                    info["status"] = "ready"
                elif deployment.status.available_replicas == 0:
                    info["status"] = "failed"
                else:
                    info["status"] = "deploying"
                    
                info["replicas"] = deployment.status.ready_replicas
                info["available"] = deployment.status.available_replicas
                
            except Exception as e:
                logger.error(f"Error getting status for {deployment_name}: {str(e)}")
                info["status"] = "unknown"
                
        return deployments
    
    # Simulate routing an inference request to a model shard
    def route_inference_request(self, model_name: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate routing an inference request to the appropriate model shard."""
        # Get all shards for this model
        shards = {k: v for k, v in self.model_deployments.items() 
                 if v["model_name"].startswith(model_name) and v["status"] == "ready"}
        
        if not shards:
            logger.error(f"No ready shards found for model {model_name}")
            return {"error": "No ready model shards available"}
        
        # Simple round-robin load balancing for simulation
        shard_names = list(shards.keys())
        selected_shard = shard_names[hash(str(time.time())) % len(shard_names)]
        
        # Simulate inference request
        return {
            "shard": selected_shard,
            "node": shards[selected_shard]["node"],
            "request_id": hash(str(time.time())),
            "timestamp": time.time(),
            "simulated_result": f"Inference result from {selected_shard} on node {shards[selected_shard]['node']}"
        }
    
    # Simulate monitoring inference performance
    def monitor_inference_performance(self, model_name: str, time_window: int = 300) -> Dict[str, Any]:
        """Simulate monitoring inference performance for a model."""
        # Get all shards for this model
        shards = {k: v for k, v in self.model_deployments.items() 
                 if v["model_name"].startswith(model_name) and v["status"] == "ready"}
        
        # Simulate performance metrics
        return {
            "model": model_name,
            "time_window": time_window,
            "num_shards": len(shards),
            "metrics": {
                "requests_per_second": 10,
                "average_latency_ms": 50,
                "p95_latency_ms": 100,
                "p99_latency_ms": 200,
                "error_rate": 0.01
            },
            "shard_metrics": {
                shard: {
                    "requests_processed": 100,
                    "average_latency_ms": 50 + i * 10,
                    "error_rate": 0.01
                } for i, shard in enumerate(shards.keys())
            }
        }
    
    # Clean up model deployments
    def cleanup_model_deployment(self, model_name: str) -> bool:
        """Clean up all deployments for a model."""
        try:
            # Find all deployments for this model
            deployments = self.apps_v1.list_namespaced_deployment(
                namespace="default",
                label_selector=f"app={model_name}"
            )
            
            for deployment in deployments.items:
                # Delete the deployment
                self.apps_v1.delete_namespaced_deployment(
                    name=deployment.metadata.name,
                    namespace="default"
                )
                
                # Remove from tracking
                if deployment.metadata.name in self.model_deployments:
                    del self.model_deployments[deployment.metadata.name]
                
                logger.info(f"Deleted deployment {deployment.metadata.name}")
                
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup {model_name}: {str(e)}")
            return False