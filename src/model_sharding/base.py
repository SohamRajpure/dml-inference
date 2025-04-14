from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ModelShardingStrategy(ABC):
    """Abstract base class for model sharding strategies."""
    
    def __init__(self, node_manager):
        self.node_manager = node_manager
        self.model_deployments = {}
    
    @abstractmethod
    def deploy_model(self, model_name: str, model_version: str, 
                    container_image: str, **kwargs) -> Dict[str, str]:
        """Deploy a model using the specific sharding strategy.
        
        Args:
            model_name: Name of the model
            model_version: Version of the model
            container_image: Container image containing the model
            **kwargs: Additional strategy-specific parameters
            
        Returns:
            Dictionary mapping shard names to their deployment nodes
        """
        pass
    
    @abstractmethod
    def route_inference_request(self, model_name: str, 
                              request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Route an inference request to the appropriate shard.
        
        Args:
            model_name: Name of the model
            request_data: Input data for inference
            
        Returns:
            Inference result from the appropriate shard
        """
        pass
    
    def get_deployment_status(self, model_name: str) -> Dict[str, Any]:
        """Get the status of model deployments.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary containing deployment status information
        """
        return self.node_manager.get_model_deployment_status(model_name)
    
    def monitor_performance(self, model_name: str, 
                          time_window: int = 300) -> Dict[str, Any]:
        """Monitor inference performance.
        
        Args:
            model_name: Name of the model
            time_window: Time window for performance metrics in seconds
            
        Returns:
            Dictionary containing performance metrics
        """
        return self.node_manager.monitor_inference_performance(
            model_name, time_window)
    
    def cleanup(self, model_name: str) -> bool:
        """Clean up model deployments.
        
        Args:
            model_name: Name of the model to clean up
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        return self.node_manager.cleanup_model_deployment(model_name) 