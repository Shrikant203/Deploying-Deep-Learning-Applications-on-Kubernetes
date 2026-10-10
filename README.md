# Deploying Deep Learning Applications on Kubernetes

## Objective
Deploy and expose a containerised deep-learning application in a Kubernetes environment and verify that it is accessible.

## What this project does
1. Packages a **neural-network digit classifier** (scikit-learn MLP: 64 → 64 → 32 → 10, trained on the UCI handwritten-digits dataset) behind a **Flask + gunicorn** REST API as a Docker image. The model is trained **during the image build**, so every pod is self-contained.
2. Creates a 3-node Kind cluster and loads the image into the nodes.
3. Deploys it with manifests: ConfigMap, Deployment (3 replicas, startup/readiness/liveness probes, resource requests/limits, non-root security context, topology spread, pod/node name via the downward API).
4. Exposes it with a **ClusterIP** Service (inside the cluster) and a **NodePort** Service (outside, host port 8090).
5. Verifies accessibility: health check, model info, predictions on held-out samples, a custom `POST /predict`, load balancing across pods, and access from inside the cluster.

## Files
| File | Purpose |
|---|---|
| `app/app.py` | Flask API and web page |
| `app/train_model.py` | Trains the MLP and saves model + metadata (runs at image build) |
| `app/Dockerfile`, `app/requirements.txt` | Image definition (python:3.12-slim, non-root user, gunicorn) |
| `kind-config-task13.yaml` | Cluster definition; host port **8090** → NodePort **30090** |
| `k8s13/00-namespace.yaml` | Namespace `dl-demo` |
| `k8s13/01-configmap.yaml` | ConfigMap `dl-config` (app name, model version) |
| `k8s13/02-deployment.yaml` | Deployment `dl-api` |
| `k8s13/03-service-internal.yaml` | ClusterIP Service `dl-api-internal` |
| `k8s13/04-service-external.yaml` | NodePort Service `dl-api` (30090) |
| `deploy_dl.py` | Automation: build, cluster, load image, deploy, verify, monitor |
| `Task13_DeepLearning_on_Kubernetes.ipynb` | Notebook version |
| `build_report.py` | Builds the PDF report from the evidence |
| `evidence/` | `run_log.json`, `run_log.txt`, screenshots, `browser_app.png` |
| `Task13_Deployment_Report.pdf` | Final report |

## Prerequisites
Docker Desktop (running), `kubectl`, `kind`, Python 3.9+ and `pip install pillow reportlab matplotlib`. Internet access is needed on the first run (Python image and packages).

## How to run
```bash
python deploy_dl.py                  # first run takes several minutes
# open http://localhost:8090 → save a screenshot as evidence/browser_app.png
python build_report.py --name "Your Name" --id "Your ID" --github <repo-url>
```
Cleanup (after submitting): `kind delete cluster --name task13`

## API
| Endpoint | Purpose |
|---|---|
| `GET /` | Web page that classifies a random held-out digit |
| `GET /health` | Liveness / readiness |
| `GET /model-info` | Architecture, parameters, held-out accuracy, serving pod |
| `GET /predict/sample/<i>` | Prediction for the i-th held-out image |
| `POST /predict` | `{"pixels": [64 values 0–16]}` → digit + class probabilities |

Example:
```bash
curl http://localhost:8090/model-info
curl http://localhost:8090/predict/sample/3
```

## Architecture
```
Image dl-digits:1.0 ──kind load──► every node
Browser/curl ► localhost:8090 ► NodePort 30090 ► Service dl-api ───┐
Pods in cluster ► Service dl-api-internal (ClusterIP :80) ─────────┴► 3 × dl-api pods (gunicorn :8000)
```

## Design notes
- **Self-contained image:** the trained model is baked in; a new model needs a new image and a rollout.
- **`imagePullPolicy: IfNotPresent`:** the image exists only locally (loaded into Kind), not in a registry.
- **Probes:** the startup probe gives the pod time to load scikit-learn and the model; readiness keeps it out of the Service until it answers.
- **Two Services, one set of pods:** ClusterIP for internal clients, NodePort for external ones.
- Every response includes the answering **pod name**, so load balancing is directly visible.

## Troubleshooting
| Problem | Fix |
|---|---|
| Build very slow / Docker Hub error `500 … auth.docker.io` | Temporary Docker Hub issue – retry, `docker logout`, or build with `FROM public.ecr.aws/docker/library/python:3.12-slim` |
| `kind load docker-image` fails | `docker save dl-digits:1.0 -o /tmp/dl.tar && kind load image-archive /tmp/dl.tar --name task13` (the script does this automatically) |
| Port 8090 in use | Change `hostPort` in `kind-config-task13.yaml` and recreate the cluster |
| Pods `ImagePullBackOff` | The image was not loaded into the nodes – run the load step again |

## Limitations
Small model (demonstrates the pattern, not production scale); local single-machine cluster; NodePort via host port mapping (production would use Ingress/LoadBalancer with TLS); no autoscaling or model versioning.

## Deliverables checklist
- [ ] Kubernetes deployment files (`k8s13/`)
- [ ] Service configurations (`03-…`, `04-…`)
- [ ] Deployment report (`Task13_Deployment_Report.pdf`)
- [ ] Source as `.py` / `.ipynb`
