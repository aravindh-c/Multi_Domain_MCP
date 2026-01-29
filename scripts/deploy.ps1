# Deployment script for multitenant-chatbot (Windows PowerShell)
# Account: 026544696832 | Region: us-east-1

$ErrorActionPreference = "Stop"
$NAMESPACE = "multi-tenant-chatbot"
$REGION = if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }

Write-Host "Deploying multitenant-chatbot to EKS (region: $REGION)..."

Write-Host "Creating namespace..."
kubectl apply -f infrastructure/kubernetes/namespace.yaml

Write-Host "Creating service accounts..."
kubectl apply -f infrastructure/kubernetes/irsa-service-accounts.yaml

if ($env:OPENAI_API_KEY) {
    Write-Host "Creating K8s secrets..."
    kubectl create secret generic orchestrator-secrets `
        --from-literal=OPENAI_API_KEY="$env:OPENAI_API_KEY" `
        --from-literal=LANGSMITH_API_KEY="$($env:LANGSMITH_API_KEY)" `
        -n $NAMESPACE `
        --dry-run=client -o yaml | kubectl apply -f -

    kubectl create secret generic rag-secrets `
        --from-literal=OPENAI_API_KEY="$env:OPENAI_API_KEY" `
        -n $NAMESPACE `
        --dry-run=client -o yaml | kubectl apply -f -
} else {
    Write-Host "OPENAI_API_KEY not set; skip K8s secrets (ensure Secrets Manager secret multitenant-chatbot-secrets1 exists and IRSA can read it)."
}

Write-Host "Deploying vLLM (GPU nodes)..."
kubectl apply -f infrastructure/kubernetes/vllm-deployment.yaml

Write-Host "Deploying RAG service..."
kubectl apply -f infrastructure/kubernetes/rag-deployment.yaml

Write-Host "Deploying orchestrator..."
kubectl apply -f infrastructure/kubernetes/orchestrator-deployment.yaml

Write-Host "Deploying request router..."
kubectl apply -f infrastructure/kubernetes/router-deployment.yaml

Write-Host "Applying network policies..."
kubectl apply -f infrastructure/kubernetes/network-policies.yaml

Write-Host "Deploying internal ingress..."
kubectl apply -f infrastructure/kubernetes/ingress.yaml

Write-Host "Deployment complete!"
Write-Host "Check status: kubectl get pods -n $NAMESPACE"
Write-Host "Internal ALB hostname: kubectl get ingress -n $NAMESPACE"
