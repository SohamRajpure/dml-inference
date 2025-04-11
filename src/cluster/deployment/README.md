# Inference Worker Deployment Guide

This guide provides instructions for deploying inference workers in a Kubernetes cluster using Kind.

## Prerequisites

- Kubernetes cluster (Kind) is up and running
- `kubectl` is configured to access your cluster
- Docker is installed and running
- The inference service Docker image is built

## Directory Structure

```
src/cluster/deployment/
├── deployment.yaml    # Inference worker deployment configuration
├── service.yaml       # Service configuration
└── README.md          # This file
```

## Deployment Steps

### 1. Build the Docker Image

From the project root directory (where your `requirements.txt` is located):

```bash
# Build the inference service image
# Note: The '.' at the end specifies the build context (current directory)
docker build -t inference-service:latest -f src/cluster/docker/Dockerfile.inference .

# Verify the image was built
docker images | grep inference-service
```

If you encounter the BuildKit deprecation warning, you can either:
1. Install BuildKit as recommended, or
2. Use the legacy builder with:
```bash
DOCKER_BUILDKIT=0 docker build -t inference-service:latest -f src/cluster/docker/Dockerfile.inference .
```

### 2. Load the Image into Kind

If you're using Kind, you need to load the image into the cluster:

```bash
# Load the image into Kind
kind load docker-image inference-service:latest --name <your-cluster-name>

# Verify the image is available in Kind
kubectl get nodes -o jsonpath='{.items[*].status.images[*].names[*]}' | grep inference-service
```

### 3. Deploy the Inference Workers

```bash
# Deploy the inference workers
kubectl apply -f src/cluster/deployment/deployment.yaml

# Verify the deployment
kubectl get deployments
kubectl get pods -l app=inference-worker

# Check pod details
kubectl describe pods -l app=inference-worker
```

### 4. Deploy the Service

```bash
# Deploy the service
kubectl apply -f src/cluster/deployment/service.yaml

# Verify the service
kubectl get svc inference-service

# Get service details
kubectl describe svc inference-service
```

## Verifying the Deployment

### Check Pod Status

```bash
# Get pod status
kubectl get pods -l app=inference-worker -o wide

# Check pod logs
kubectl logs -l app=inference-worker
```

### Test Service Access

```bash
# Get the ClusterIP
kubectl get svc inference-service -o jsonpath='{.spec.clusterIP}'

# Test the service from within the cluster
kubectl run curl-test --image=curlimages/curl -i --tty -- sh
# Inside the pod:
curl http://inference-service.default.svc.cluster.local/health
```

## Monitoring and Maintenance

### View Resource Usage

```bash
# Check resource usage
kubectl top pods -l app=inference-worker
```

### Scaling the Deployment

```bash
# Scale up the number of replicas
kubectl scale deployment inference-worker --replicas=3

# Scale down
kubectl scale deployment inference-worker --replicas=2
```

### Updating the Deployment

```bash
# After making changes to the deployment.yaml
kubectl apply -f src/cluster/deployment/deployment.yaml

# Or use rollout
kubectl rollout restart deployment inference-worker
```

## Troubleshooting

### Common Issues

1. **Pods not starting**
   ```bash
   # Check events
   kubectl get events --sort-by='.lastTimestamp'
   
   # Check pod status
   kubectl describe pod <pod-name>
   ```

2. **Service not accessible**
   ```bash
   # Check service endpoints
   kubectl get endpoints inference-service
   
   # Check service details
   kubectl describe svc inference-service
   ```

3. **Resource issues**
   ```bash
   # Check node resources
   kubectl describe nodes
   
   # Check pod resource usage
   kubectl top pods -l app=inference-worker
   ```

4. **Docker build issues**
   ```bash
   # Check Docker version
   docker version
   
   # Check if BuildKit is enabled
   docker buildx version
   
   # Try building with explicit context
   docker build -t inference-service:latest -f src/cluster/docker/Dockerfile.inference $(pwd)
   ```

## Cleanup

To remove the deployment and service:

```bash
# Delete the deployment
kubectl delete -f src/cluster/deployment/deployment.yaml

# Delete the service
kubectl delete -f src/cluster/deployment/service.yaml

# Verify cleanup
kubectl get pods -l app=inference-worker
kubectl get svc inference-service
``` 