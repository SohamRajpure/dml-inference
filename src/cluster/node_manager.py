import logging
from kubernetes import client, config

logger = logging.getLogger(__name__)

class NodeManager:
    def __init__(self):
        config.load_kube_config()
        self.core_v1 = client.CoreV1Api()

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