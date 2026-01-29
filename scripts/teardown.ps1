# Teardown multitenant-chatbot: remove app and optionally the EKS cluster
# Account: 026544696832 | Region: us-east-1
# Usage:
#   .\teardown.ps1              # Delete app only (namespace); cluster stays
#   .\teardown.ps1 -Full       # Delete app then delete EKS cluster

param(
    [switch]$Full  # If set, also delete EKS cluster via eksctl
)

$ErrorActionPreference = "Stop"
$NAMESPACE = "multi-tenant-chatbot"
$EKSCTL_CONFIG = "infrastructure/eksctl-config.yaml"

Write-Host "Teardown multitenant-chatbot (namespace: $NAMESPACE)..."

# 1. Delete Kubernetes app (namespace removes all resources in it: deployments, services, ingress, ALB, etc.)
Write-Host "Deleting namespace $NAMESPACE (this removes all app resources and the internal ALB)..."
kubectl delete namespace $NAMESPACE --ignore-not-found=true --timeout=120s 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "If namespace is stuck, check: kubectl get all -n $NAMESPACE"
}

Write-Host "App teardown complete. Namespace $NAMESPACE removed."

if ($Full) {
    if (-not (Test-Path $EKSCTL_CONFIG)) {
        Write-Host "EKS config not found: $EKSCTL_CONFIG. Skipping cluster delete."
        exit 0
    }
    Write-Host "Deleting EKS cluster (eksctl delete cluster -f $EKSCTL_CONFIG)..."
    eksctl delete cluster -f $EKSCTL_CONFIG
    Write-Host "Full teardown complete. Cluster deleted. ECR repos and Secrets Manager secret are left; delete manually if desired."
} else {
    Write-Host "Cluster left running. To delete cluster later: .\teardown.ps1 -Full"
    Write-Host "To recreate app only: .\deploy.ps1"
}
