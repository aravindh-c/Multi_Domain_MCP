# Export current Kubernetes resources (multi-tenant-chatbot namespace) to YAML
# Use this to backup live state before teardown; repo manifests remain source of truth for recreate.
# Output: infrastructure/export/k8s-export-<timestamp>.yaml

$ErrorActionPreference = "Stop"
$NAMESPACE = "multi-tenant-chatbot"
$EXPORT_DIR = "infrastructure/export"
$TIMESTAMP = Get-Date -Format "yyyyMMdd-HHmmss"
$OUTFILE = "$EXPORT_DIR/k8s-export-$TIMESTAMP.yaml"

if (-not (Test-Path $EXPORT_DIR)) { New-Item -ItemType Directory -Path $EXPORT_DIR -Force | Out-Null }

Write-Host "Exporting K8s resources from namespace $NAMESPACE to $OUTFILE..."

kubectl get all,ingress,configmap,secret,pvc,serviceaccount,networkpolicy -n $NAMESPACE -o yaml | Set-Content -Path $OUTFILE

Write-Host "Export written to $OUTFILE"
Write-Host "To restore from this file is not automated; use repo manifests and deploy.ps1 for recreate."
