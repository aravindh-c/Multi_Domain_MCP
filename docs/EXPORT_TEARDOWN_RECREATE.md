# Export, Teardown, and Recreate: Complete Setup from Scripts

This doc describes how to **export** your complete AWS/EKS setup into scripts and config so you can **turn off all services** and **recreate the entire setup later** from that same repo.

---

## What is the “complete setup”?

The full setup has two layers:

| Layer | What it is | Where it’s defined |
|-------|------------|--------------------|
| **AWS / EKS** | EKS cluster, node groups, (optional) VPC | **eksctl**: `infrastructure/eksctl-config.yaml` |
| **AWS one-time** | Secrets Manager secret, ECR repos, IAM roles for IRSA | **Manual / Console** or scripts; see [infrastructure/SETUP_YOUR_ACCOUNT.md](../infrastructure/SETUP_YOUR_ACCOUNT.md) |
| **Kubernetes app** | Namespace, ServiceAccounts, Deployments, Services, Ingress, NetworkPolicies | **Manifests**: `infrastructure/kubernetes/*.yaml` |
| **Deploy order** | Apply manifests in the right order | **Scripts**: `scripts/deploy.ps1` or `scripts/deploy.sh` |

So the **“export”** is: this repo (eksctl config + K8s manifests + deploy/teardown scripts). You don’t need to export from the AWS Console; the repo **is** the definition. Optionally you can snapshot live K8s state with `scripts/export-k8s.*` before teardown.

---

## 1. Export (what to save)

- **Primary “export”**: The repo itself.
  - `infrastructure/eksctl-config.yaml` – cluster and node groups (create/delete with eksctl).
  - `infrastructure/kubernetes/*.yaml` – all app resources.
  - `infrastructure/config/aws-config.yaml` – account/region/project settings (reference only).
  - `scripts/deploy.ps1`, `scripts/deploy.sh` – apply K8s in order.
  - `scripts/teardown.ps1`, `scripts/teardown.sh` – remove app and optionally cluster.

- **Optional backup of live state** (before teardown):
  - Run `scripts/export-k8s.ps1` or `scripts/export-k8s.sh`.
  - Writes `infrastructure/export/k8s-export-<timestamp>.yaml` with current namespace resources.
  - Recreate is still done from the repo manifests and deploy scripts; the export is a backup only.
  - You can add `infrastructure/export/` to `.gitignore` if you don’t want to commit these backups.

---

## 2. Teardown (turn off all services)

Two levels:

### Option A – App only (cluster stays)

Removes the app and the internal ALB; the EKS cluster and node groups stay. Good when you want to stop paying for app pods but keep the cluster for later.

**PowerShell:**

```powershell
.\scripts\teardown.ps1
```

**Bash:**

```bash
./scripts/teardown.sh
```

This deletes the namespace `multi-tenant-chatbot`, so all deployments, services, ingress (and the ALB created by that ingress) are removed. ECR repos and the Secrets Manager secret are **not** deleted.

### Option B – Full teardown (app + EKS cluster)

Removes the app **and** the EKS cluster (and node groups). Use when you want to turn off everything and recreate from scratch later.

**PowerShell:**

```powershell
.\scripts\teardown.ps1 -Full
```

**Bash:**

```bash
./scripts/teardown.sh --full
```

This runs the same namespace delete, then `eksctl delete cluster -f infrastructure/eksctl-config.yaml`. ECR repos and the Secrets Manager secret are **left**; delete them manually if you want (see below).

---

## 3. Recreate (bring everything back)

Order of operations:

### Step 1 – Create EKS cluster (only if you did full teardown)

From repo root:

```bash
eksctl create cluster -f infrastructure/eksctl-config.yaml
```

For the full ordered checklist (cluster → node groups → add-ons → Secrets Manager → ECR → IRSA → deploy), see [docs/CREATE_SETUP_IN_ORDER.md](CREATE_SETUP_IN_ORDER.md).

Wait until the cluster is ready (`kubectl get nodes`). Then install any add-ons you use:

- **AWS Load Balancer Controller** (for Ingress → ALB): if not already installed, follow [AWS docs](https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html).
- **NVIDIA device plugin** (only if you use GPU node group and vLLM):

  ```bash
  kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.1/nvidia-device-plugin.yml
  ```

### Step 2 – One-time AWS resources (if missing)

- **Secrets Manager**: Create or update the secret (see [SETUP_YOUR_ACCOUNT.md](../infrastructure/SETUP_YOUR_ACCOUNT.md)).
- **ECR**: Create repos and push images (or use your CI); see SETUP_YOUR_ACCOUNT.md.
- **IAM / IRSA**: Create IAM roles for the service accounts and link them (see SETUP_YOUR_ACCOUNT.md).

### Step 3 – Deploy the app

**PowerShell:**

```powershell
.\scripts\deploy.ps1
```

**Bash:**

```bash
./scripts/deploy.sh
```

This applies namespace, IRSA service accounts, secrets (if `OPENAI_API_KEY` is set), then all deployments, network policies, and ingress. After that, use `kubectl get pods -n multi-tenant-chatbot` and (if using Ingress) `kubectl get ingress -n multi-tenant-chatbot` to confirm.

---

## 4. Summary table

| Action | Command / location |
|--------|--------------------|
| **Export** | Repo = export. Optional: `scripts/export-k8s.ps1` or `export-k8s.sh` for K8s backup. |
| **Teardown app only** | `scripts/teardown.ps1` or `teardown.sh` |
| **Teardown app + cluster** | `scripts/teardown.ps1 -Full` or `teardown.sh --full` |
| **Recreate cluster** | `eksctl create cluster -f infrastructure/eksctl-config.yaml` |
| **Recreate app** | `scripts/deploy.ps1` or `deploy.sh` (after cluster and one-time AWS resources exist) |

---

## 5. Optional: delete ECR and Secrets Manager

If you did a full teardown and want to remove **everything**:

- **Secrets Manager**:  
  `aws secretsmanager delete-secret --region us-east-1 --secret-id multitenant-chatbot-secrets1 --force-delete-without-recovery`

- **ECR repos** (from repo root, after setting `AWS_ACCOUNT` and `REGION`):  
  For each repo (`multitenant-chatbot-request-router`, `multitenant-chatbot-orchestrator`, `multitenant-chatbot-rag-service`):  
  `aws ecr delete-repository --region $REGION --repository-name <repo-name> --force`

Recreate later: create the secret and ECR repos again (see SETUP_YOUR_ACCOUNT.md), then push images and run the deploy script.
