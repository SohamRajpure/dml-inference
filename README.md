# Distributed ML Inference Simulation

This project simulates a distributed machine learning inference system using Kubernetes (Kind) for orchestration. It demonstrates how to deploy and manage inference workers in a distributed environment without requiring actual ML models or GPUs.

## Project Overview

The project consists of:
- Inference workers deployed as Kubernetes pods
- Primary and backup worker nodes for high availability
- Minimal resource requirements for simulation purposes
- Health monitoring and load balancing

### Key Features
- Lightweight inference simulation
- Resource-efficient deployment
- High availability with primary/backup workers
- Kubernetes-native deployment
- Health monitoring and metrics collection

## Project Structure

```
.
├── src/
│   ├── cluster/
│   │   ├── docker/
│   │   │   └── Dockerfile.inference    # Docker configuration for inference workers
│   │   └── deployment/
│   │       ├── deployment.yaml         # Kubernetes deployment configuration
│   │       ├── service.yaml            # Service configuration
│   │       └── README.md               # Detailed deployment instructions
├── requirements.txt                     # Python dependencies
└── README.md                           # This file
```

## Getting Started

### Prerequisites
- Docker installed and running
- Kubernetes cluster (Kind) set up
- `kubectl` configured to access your cluster

### Deployment Instructions

For detailed instructions on how to deploy the inference workers, please refer to the [deployment guide](src/cluster/deployment/README.md) in the `src/cluster/deployment` directory. The guide includes:

1. Building the Docker image
2. Loading the image into Kind
3. Deploying inference workers
4. Setting up the service
5. Verifying the deployment
6. Monitoring and maintenance
7. Troubleshooting common issues

## Resource Requirements

The deployment is optimized for minimal resource usage:
- Each worker pod requests:
  - CPU: 50m (5% of a CPU core)
  - Memory: 32Mi
- Maximum limits per pod:
  - CPU: 100m (10% of a CPU core)
  - Memory: 64Mi

## Monitoring

The deployment includes:
- Health checks for pods
- Resource usage monitoring
- Service availability checks

## Cleanup

For instructions on how to clean up the deployment, refer to the [Cleanup section](src/cluster/deployment/README.md#cleanup) in the deployment guide.

## Contributing

Feel free to submit issues and enhancement requests.

