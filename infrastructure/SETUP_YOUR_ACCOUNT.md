# Setup for Your AWS Account

**Account ID:** `026544696832`  
**Region:** `us-east-1`  
**Project:** multitenant-chatbot  
**Access:** internal only  
**Max users:** 3  

For a **single file with the exact order** (create cluster → add node groups with names → add-ons → Secrets Manager → ECR → IRSA → deploy), see **[docs/CREATE_SETUP_IN_ORDER.md](../docs/CREATE_SETUP_IN_ORDER.md)**.

---

## 1. Create the secret in AWS Secrets Manager

Store your OpenAI API key (and optional LangSmith key) so the app can read them at runtime.

```bash
aws secretsmanager create-secret \
  --region us-east-1 \
  --name multitenant-chatbot-secrets1 \
  --secret-string '{"OPENAI_API_KEY":"sk-YOUR_OPENAI_KEY","LANGSMITH_API_KEY":"ls-YOUR_LANGSMITH_KEY"}'
```

If the secret already exists, update it:

```bash
aws secretsmanager put-secret-value \
  --region us-east-1 \
  --secret-id multitenant-chatbot-secrets1 \
  --secret-string '{"OPENAI_API_KEY":"sk-YOUR_OPENAI_KEY","LANGSMITH_API_KEY":"ls-YOUR_LANGSMITH_KEY"}'
```

Replace `sk-YOUR_OPENAI_KEY` and `ls-YOUR_LANGSMITH_KEY` with your real keys. You can omit `LANGSMITH_API_KEY` if you don’t use LangSmith.

---

## 2. Create the EKS cluster (if you don’t have one)

Minimal cluster in `us-east-1` with one CPU node group and one GPU node group (minimal GPU: g4dn.xlarge).

Using **eksctl** (recommended):

```bash
# Install eksctl if needed: https://eksctl.io/installation/

eksctl create cluster \
  --name multitenant-chatbot-eks \
  --region us-east-1 \
  --version 1.28 \
  --nodegroup-name cpu-nodes \
  --node-type t3.medium \
  --nodes 1 \
  --nodes-min 1 \
  --nodes-max 3 \
  --managed

# Add GPU node group (after cluster is ready)
eksctl create nodegroup \
  --cluster multitenant-chatbot-eks \
  --region us-east-1 \
  --name gpu-nodes \
  --node-type g4dn.xlarge \
  --nodes 1 \
  --nodes-min 0 \
  --nodes-max 2 \
  --managed \
  --labels node-type=gpu,accelerator=nvidia-tesla-t4
```

Install NVIDIA device plugin on the cluster so GPU nodes can schedule GPU workloads:

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.1/nvidia-device-plugin.yml
```

---

## 3. Create ECR repositories and push images

```bash
AWS_ACCOUNT=026544696832
REGION=us-east-1

for repo in multitenant-chatbot-request-router multitenant-chatbot-orchestrator multitenant-chatbot-rag-service; do
  aws ecr create-repository --region $REGION --repository-name $repo 2>/dev/null || true
done

# Log in to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com

# Build and push (from repo root)
docker build -f dockerfiles/Dockerfile.router -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-request-router:latest .
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-request-router:latest

docker build -f dockerfiles/Dockerfile.orchestrator -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-orchestrator:latest .
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-orchestrator:latest

docker build -f dockerfiles/Dockerfile.rag -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-rag-service:latest .
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-rag-service:latest
```

---

## 4. Create IAM roles for IRSA (pod access to AWS)

The pods need IAM roles so they can read Secrets Manager and write CloudWatch. Create one role per service account and link it to the service account.

**4.1 Request Router role**  
- Trust policy: allow `multitenant-chatbot` namespace, service account `request-router-sa`.  
- Permissions: read `multitenant-chatbot-secrets1`, write CloudWatch Logs and CloudWatch Metrics in `eu-north-1`.

**4.2 Orchestrator role**  
- Same trust for `orchestrator-sa`.  
- Permissions: read `multitenant-chatbot-secrets1`, write CloudWatch Logs and CloudWatch Metrics.

**4.3 RAG role**  
- Same trust for `rag-sa`.  
- Permissions: read `multitenant-chatbot-secrets1`, write CloudWatch Logs and CloudWatch Metrics.

**4.4 vLLM role**  
- Same trust for `vllm-sa`.  
- Permissions: write CloudWatch Logs and CloudWatch Metrics (and ECR pull if your images are in this account).

Role names used in the manifests:

- `multitenant-chatbot-request-router-role`
- `multitenant-chatbot-orchestrator-role`
- `multitenant-chatbot-rag-role`
- `multitenant-chatbot-vllm-role`

Use the AWS console (IAM → Roles → Create role → Web identity → EKS OIDC provider for your cluster, then attach policies) or Terraform/CloudFormation. After creating each role, set its ARN in the service account annotation in `infrastructure/kubernetes/irsa-service-accounts.yaml` (already set for account `026544696832`).

---

## 5. Deploy the app to EKS

```bash
# Ensure kubectl points to your cluster
aws eks update-kubeconfig --name multitenant-chatbot-eks --region eu-north-1

# Create namespace and IRSA
kubectl apply -f infrastructure/kubernetes/namespace.yaml
kubectl apply -f infrastructure/kubernetes/irsa-service-accounts.yaml

# Create K8s secret with OpenAI key (used by orchestrator/rag until they use Secrets Manager)
# Optional if pods already use IRSA + Secrets Manager
kubectl create secret generic orchestrator-secrets \
  --from-literal=OPENAI_API_KEY="sk-YOUR_KEY" \
  --from-literal=LANGSMITH_API_KEY="ls-YOUR_KEY" \
  -n multi-tenant-chatbot --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic rag-secrets \
  --from-literal=OPENAI_API_KEY="sk-YOUR_KEY" \
  -n multi-tenant-chatbot --dry-run=client -o yaml | kubectl apply -f -

# Deploy workloads (order: vLLM → RAG → orchestrator → router)
kubectl apply -f infrastructure/kubernetes/vllm-deployment.yaml
kubectl apply -f infrastructure/kubernetes/rag-deployment.yaml
kubectl apply -f infrastructure/kubernetes/orchestrator-deployment.yaml
kubectl apply -f infrastructure/kubernetes/router-deployment.yaml

# Optional: network policies and internal ingress
kubectl apply -f infrastructure/kubernetes/network-policies.yaml
kubectl apply -f infrastructure/kubernetes/ingress.yaml
```

---

## 6. Check that everything is running

```bash
kubectl get pods -n multi-tenant-chatbot
kubectl get svc -n multi-tenant-chatbot
kubectl get ingress -n multi-tenant-chatbot
```

The ALB will be **internal**. Use the ALB DNS name from the ingress (or the router service) from inside the VPC (e.g. bastion, VPN, or another pod) to call the chatbot.

---

## 7. Call the chatbot (from inside the VPC)

```bash
# Replace INTERNAL_ALB_DNS with the ingress ALB hostname
curl -X POST http://INTERNAL_ALB_DNS/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: t1" \
  -d '{"tenant_id":"t1","user_id":"u1","session_id":"s1","query":"Hello","locale":"en"}'
```

---

## Summary of what you must do

| Step | What you do |
|------|-------------|
| 1 | Create (or update) secret `multitenant-chatbot-secrets1` in Secrets Manager in `eu-north-1` with `OPENAI_API_KEY` (and optionally `LANGSMITH_API_KEY`). |
| 2 | Create EKS cluster in `eu-north-1` (or use existing), add CPU and GPU node groups, install NVIDIA device plugin. |
| 3 | Create ECR repos, build and push the three images to `026544696832.dkr.ecr.eu-north-1.amazonaws.com/`. |
| 4 | Create the four IAM roles for IRSA and associate them with the service accounts. |
| 5 | Run `kubectl apply` for namespace, IRSA, secrets, deployments, and optionally network policies and ingress. |
| 6 | Use the internal ALB hostname from inside the VPC to send requests with `X-Tenant-Id` and the JSON body above. |

All names (cluster, roles, repos, secret, namespace) are already set in the repo for account `026544696832` and region `eu-north-1`.
