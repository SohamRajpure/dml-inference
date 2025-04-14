from src.cluster.node_manager import NodeManager
from src.model_sharding.strategies import PartitionShardingStrategy
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def deploy_sharded_model():
    # Initialize node manager and sharding strategy
    node_manager = NodeManager()
    sharding_strategy = PartitionShardingStrategy(node_manager)
    
    # Model configuration
    model_name = "example-model"
    model_version = "v1"
    container_image = "example/model:latest"  # Replace with your actual model container image
    num_shards = 3  # Number of shards to create
    
    # Deploy the model using partition sharding
    deployment_map = sharding_strategy.deploy_model(
        model_name=model_name,
        model_version=model_version,
        container_image=container_image,
        num_shards=num_shards
    )
    
    logger.info(f"Deployment map: {deployment_map}")
    
    # Monitor deployment status
    status = sharding_strategy.get_deployment_status(model_name)
    logger.info(f"Deployment status: {status}")
    
    # Simulate some inference requests
    for i in range(5):
        request_data = {"input": f"test_data_{i}"}
        result = sharding_strategy.route_inference_request(model_name, request_data)
        logger.info(f"Inference result {i}: {result}")
    
    # Monitor performance
    performance = sharding_strategy.monitor_performance(model_name)
    logger.info(f"Performance metrics: {performance}")

if __name__ == "__main__":
    deploy_sharded_model() 