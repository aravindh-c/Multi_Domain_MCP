# Create the Full Setup in Order

One file with the **exact order** and **names** to create the multitenant-chatbot setup from scratch. Follow the steps in sequence.

**Account:** `026544696832` · **Region:** `us-east-1` · **Cluster name:** `multitenant-chatbot-eks`

---

## Order overview

| Step | What you create | Name(s) |
|------|-----------------|--------|
| 1 | EKS cluster + node groups | Cluster: `multitenant-chatbot-eks` · Node groups: `cpu-nodes`, `gpu-nodes` |
| 2 | Add-ons (ALB controller, optional GPU plugin) | — |
| 3 | Secrets Manager secret | `multitenant-chatbot-secrets1` |
| 4 | ECR repositories | `multitenant-chatbot-request-router`, `multitenant-chatbot-orchestrator`, `multitenant-chatbot-rag-service` |
| 5 | IAM roles for IRSA | `multitenant-chatbot-request-router-role`, `multitenant-chatbot-orchestrator-role`, `multitenant-chatbot-rag-role`, `multitenant-chatbot-vllm-role` |
| 6 | Deploy app (namespace, IRSA, deployments, ingress) | Namespace: `multi-tenant-chatbot` |

---

## Step 1 – Create EKS cluster and node groups

You can do this in one of two ways.

### Option A – One command (cluster + both node groups)

Uses the config file that defines cluster and both node groups:

```bash
eksctl create cluster -f infrastructure/eksctl-config.yaml
```

This creates:

- **Cluster:** `multitenant-chatbot-eks` (region `us-east-1`, Kubernetes 1.28)
- **Node group 1:** `cpu-nodes`  
  - Instance type: `t3.medium`  
  - Min 1, max 3, desired 1  
  - Labels: `node-type=cpu`
- **Node group 2:** `gpu-nodes`  
  - Instance type: `g4dn.xlarge`  
  - Min 0, max 2, desired 0  
  - Labels: `node-type=gpu`, `accelerator=nvidia-tesla-t4`

Wait until the cluster is ready: `kubectl get nodes`

---

### Option B – Step-by-step (create cluster, then add each node group)

**1.1 Create the cluster (with first node group)**

```bash
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
```

This creates the cluster **multitenant-chatbot-eks** and the node group **cpu-nodes** (t3.medium). Wait until ready: `kubectl get nodes`.

**1.2 Add the second node group (GPU)**

```bash
eksctl create nodegroup \
  --cluster multitenant-chatbot-eks \
  --region us-east-1 \
  --name gpu-nodes \
  --node-type g4dn.xlarge \
  --nodes 0 \
  --nodes-min 0 \
  --nodes-max 2 \
  --managed \
  --labels node-type=gpu,accelerator=nvidia-tesla-t4
```

This adds the node group **gpu-nodes** (g4dn.xlarge) to the existing cluster.

---

## Step 2 – Add-ons (after cluster is ready)

**2.1 AWS Load Balancer Controller** (required for Ingress → ALB)

If not already installed, install it so the Ingress creates an ALB. See: [AWS Load Balancer Controller](https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html).

**2.2 NVIDIA device plugin** (only if you will run vLLM on GPU nodes)

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.1/nvidia-device-plugin.yml
```

---

## Step 3 – Create Secrets Manager secret

**Name:** `multitenant-chatbot-secrets1`

```bash
aws secretsmanager create-secret \
  --region us-east-1 \
  --name multitenant-chatbot-secrets1 \
  --secret-string '{"OPENAI_API_KEY":"sk-YOUR_OPENAI_KEY","LANGSMITH_API_KEY":"ls-YOUR_LANGSMITH_KEY"}'
```

If it already exists, update:

```bash
aws secretsmanager put-secret-value \
  --region us-east-1 \
  --secret-id multitenant-chatbot-secrets1 \
  --secret-string '{"OPENAI_API_KEY":"sk-YOUR_OPENAI_KEY","LANGSMITH_API_KEY":"ls-YOUR_LANGSMITH_KEY"}'
```

Replace the placeholder keys with your real values.

---

## Step 4 – Create ECR repositories and push images

**Repository names:**  
`multitenant-chatbot-request-router`, `multitenant-chatbot-orchestrator`, `multitenant-chatbot-rag-service`

```bash
AWS_ACCOUNT=026544696832
REGION=us-east-1

for repo in multitenant-chatbot-request-router multitenant-chatbot-orchestrator multitenant-chatbot-rag-service; do
  aws ecr create-repository --region $REGION --repository-name $repo 2>/dev/null || true
done

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com
```

Then build and push from repo root (or use your CI):

```bash
docker build -f dockerfiles/Dockerfile.router -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-request-router:latest .
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-request-router:latest

docker build -f dockerfiles/Dockerfile.orchestrator -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-orchestrator:latest .
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-orchestrator:latest

docker build -f dockerfiles/Dockerfile.rag -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-rag-service:latest .
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/multitenant-chatbot-rag-service:latest
```

---

## Step 5 – Create IAM roles for IRSA (pod access to AWS)

Create one role per service account and link it to the EKS OIDC provider. Role names:

- `multitenant-chatbot-request-router-role`
- `multitenant-chatbot-orchestrator-role`
- `multitenant-chatbot-rag-role`
- `multitenant-chatbot-vllm-role`

Trust policy: allow the EKS OIDC provider and the namespace `multi-tenant-chatbot` with the matching service account (`request-router-sa`, `orchestrator-sa`, `rag-sa`, `vllm-sa`).  
Permissions: read `multitenant-chatbot-secrets1` (Secrets Manager), write CloudWatch Logs/Metrics as needed.

Detailed steps and policies are in [infrastructure/SETUP_YOUR_ACCOUNT.md](../infrastructure/SETUP_YOUR_ACCOUNT.md). The Kubernetes ServiceAccounts in `infrastructure/kubernetes/irsa-service-accounts.yaml` already reference these role ARNs.

---

## Step 6 – Deploy the app (namespace, IRSA, deployments, ingress)

**Namespace:** `multi-tenant-chatbot`

From repo root:

**PowerShell:**

```powershell
.\scripts\deploy.ps1
```

**Bash:**

```bash
./scripts/deploy.sh
```

This applies in order: namespace → IRSA service accounts → (optional) K8s secrets → vLLM deployment → RAG deployment → orchestrator deployment → router deployment → network policies → ingress.

Check:

```bash
kubectl get pods -n multi-tenant-chatbot
kubectl get ingress -n multi-tenant-chatbot
```

---

## Quick reference: names and order

| Step | Resource type | Name(s) |
|------|----------------|--------|
| 1 | Cluster | `multitenant-chatbot-eks` |
| 1 | Node group 1 | `cpu-nodes` (t3.medium) |
| 1 | Node group 2 | `gpu-nodes` (g4dn.xlarge) |
| 3 | Secrets Manager secret | `multitenant-chatbot-secrets1` |
| 4 | ECR repos | `multitenant-chatbot-request-router`, `multitenant-chatbot-orchestrator`, `multitenant-chatbot-rag-service` |
| 5 | IAM roles | `multitenant-chatbot-request-router-role`, `multitenant-chatbot-orchestrator-role`, `multitenant-chatbot-rag-role`, `multitenant-chatbot-vllm-role` |
| 6 | Kubernetes namespace | `multi-tenant-chatbot` |

**Order:** 1 → 2 → 3 → 4 → 5 → 6.
