#!/usr/bin/env python3
"""Task 13 - Deploy and expose a containerized deep-learning application on Kubernetes (Kind).

    python deploy_dl.py              # build image, create cluster, deploy, expose, verify
    python deploy_dl.py --cleanup    # also delete the cluster at the end

Every command and its real output is saved to evidence/run_log.json (+ .txt) and rendered as
terminal-style PNG screenshots in evidence/ (needs: pip install pillow).
"""
import argparse, json, os, shutil, subprocess, sys, time, urllib.request, urllib.error
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
EVID = ROOT / "evidence"; EVID.mkdir(exist_ok=True)
NS, CLUSTER, IMAGE = "dl-demo", "task13", "dl-digits:1.0"
BASE = "http://localhost:8090"
LOG = []
BASH = "/bin/bash" if os.path.exists("/bin/bash") else None


def run(title, cmd, check=True, timeout=900):
    print(f"\n=== {title} ===\n$ {cmd}")
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, executable=BASH)
    out = (p.stdout + p.stderr).strip()
    print(out)
    LOG.append({"title": title, "cmd": cmd, "output": out, "rc": p.returncode})
    if check and p.returncode != 0:
        save_logs(); sys.exit(f"Command failed ({p.returncode}): {cmd}")
    return out


def run_live(title, cmd, timeout=3600, keep=22):
    """Run a long command, streaming its output to the terminal; log only the last lines."""
    print(f"\n=== {title} ===\n$ {cmd}")
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, executable=BASH)
    lines, t0 = [], time.time()
    for line in p.stdout:
        print(line, end="", flush=True); lines.append(line.rstrip())
        if time.time() - t0 > timeout:
            p.kill(); break
    p.wait()
    out = "\n".join(lines[-keep:])
    LOG.append({"title": title, "cmd": cmd, "output": out, "rc": p.returncode})
    if p.returncode != 0:
        save_logs(); sys.exit(f"Command failed ({p.returncode}): {cmd}")
    return out


def record(title, cmd, output, rc=0):
    print(f"\n=== {title} ===\n$ {cmd}\n{output}")
    LOG.append({"title": title, "cmd": cmd, "output": output, "rc": rc})


def http(path, data=None, retries=1):
    url = BASE + path
    for k in range(retries):
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                         headers={"Content-Type": "application/json"} if data is not None else {})
            return json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        except Exception as ex:
            err = ex; time.sleep(2)
    raise err


def save_logs():
    (EVID / "run_log.json").write_text(json.dumps(LOG, indent=2))
    with open(EVID / "run_log.txt", "w") as f:
        for e in LOG:
            f.write(f"=== {e['title']} ===\n$ {e['cmd']}\n{e['output']}\n\n")
    try:
        render_screenshots()
    except ImportError:
        print("Pillow not installed - skipping PNG rendering (pip install pillow)")


def render_screenshots():
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for f in ("DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "Menlo.ttc", "Courier New.ttf"):
        try:
            font = ImageFont.truetype(f, 15); break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    for i, e in enumerate(LOG, 1):
        lines = [f"$ {e['cmd'][:140]}"] + [l[:140] for l in e["output"].splitlines()[:45]]
        w = max(900, 9 * max(len(l) for l in lines) + 40); h = 40 + 21 * len(lines)
        img = Image.new("RGB", (w, h), (24, 26, 31)); d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w, 26], fill=(50, 54, 62)); d.text((10, 5), e["title"], fill=(220, 220, 220), font=font)
        for n, l in enumerate(lines):
            d.text((14, 36 + 21 * n), l, fill=(120, 220, 140) if n == 0 else (225, 225, 225), font=font)
        img.save(EVID / f"{i:02d}_{e['title'].lower().replace(' ', '_').replace('/', '-')[:40]}.png")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cleanup", action="store_true"); a = ap.parse_args()
    for t in ("docker", "kubectl", "kind"):
        if not shutil.which(t):
            sys.exit(f"'{t}' not found in PATH - install it first (see README.md)")

    # 1. Build the container image (the model is trained inside the build)
    run("Tool versions", "docker --version && kubectl version --client && kind version")
    run_live("Build Docker image", f"docker build --progress=plain --provenance=false --sbom=false -t {IMAGE} app 2>&1")
    run("Docker image details", "docker image ls dl-digits")

    # 2. Cluster
    existing = run("List kind clusters", "kind get clusters", check=False)
    if CLUSTER not in existing.split():
        run("Create Kind cluster (1 control-plane + 2 workers)",
            f"kind create cluster --name {CLUSTER} --config kind-config-task13.yaml --wait 120s")
    run("Set kubectl context", f"kubectl config use-context kind-{CLUSTER}")
    run("Wait for all nodes Ready", "kubectl wait --for=condition=Ready nodes --all --timeout=180s")
    run("Cluster nodes", "kubectl get nodes -o wide")
    out = run("Load image into Kind", f"kind load docker-image {IMAGE} --name {CLUSTER}", check=False)
    if LOG[-1]["rc"] != 0:      # Docker Desktop's containerd image store can break 'docker-image' loading
        LOG.pop()
        run("Load image into Kind (archive method)",
            f"docker save {IMAGE} -o /tmp/dl-digits.tar && kind load image-archive /tmp/dl-digits.tar --name {CLUSTER}")

    # 3. Deploy and expose
    run("Apply manifests", "kubectl apply -f k8s13/")
    run("Wait for rollout", f"kubectl rollout status deployment/dl-api -n {NS} --timeout=240s")

    # 4. Verify objects
    run("Get pods", f"kubectl get pods -n {NS} -o wide")
    run("Get deployment, services, endpoints", f"kubectl get deploy,svc,endpointslices,cm -n {NS}")
    run("Describe external service", f"kubectl describe svc dl-api -n {NS}")

    # 5. Verify accessibility from outside the cluster
    try:
        h = http("/health", retries=15)
        record("Health check (external)", f"curl -s {BASE}/health", json.dumps(h, indent=2))
        record("Model info (external)", f"curl -s {BASE}/model-info", json.dumps(http("/model-info"), indent=2))
        rows = []
        for i in range(10):
            r = http(f"/predict/sample/{i}")
            rows.append(f"sample {i}: predicted {r['prediction']}  true {r['true_label']}  "
                        f"confidence {r['confidence']:.3f}  {'OK ' if r['correct'] else 'ERR'}  pod {r['pod']}")
        record("Predictions on held-out samples", f"curl -s {BASE}/predict/sample/<0..9>", "\n".join(rows))
        px = http("/predict/sample/0")["pixels"]
        r = http("/predict", {"pixels": px})
        top = sorted(r["probabilities"].items(), key=lambda kv: -kv[1])[:3]
        record("POST /predict with a custom request",
               f"curl -s -X POST -H 'Content-Type: application/json' -d '{{\"pixels\": {px[:8]}...}}' {BASE}/predict",
               json.dumps({"prediction": r["prediction"], "confidence": r["confidence"], "top3": dict(top), "pod": r["pod"]}, indent=2))
        cnt = Counter(http("/health")["pod"] for _ in range(30))
        record("Load balancing across pods", f"30 x curl -s {BASE}/health",
               "\n".join(f"{p}: {n} requests" for p, n in sorted(cnt.items())))
    except Exception as ex:
        record("HTTP tests", f"curl {BASE}", f"FAILED: {ex}", 1)

    # 6. Verify accessibility from inside the cluster (ClusterIP service)
    run("In-cluster access via ClusterIP service",
        f"kubectl run curl-test -n {NS} --rm -i --restart=Never --image=curlimages/curl:8.10.1 -- "
        f"curl -s http://dl-api-internal/health", check=False, timeout=240)

    # 7. Monitoring
    run("Pod logs", f"kubectl logs deployment/dl-api -n {NS} --tail=12")
    run("Deployment details", f"kubectl describe deployment dl-api -n {NS}")
    run("Recent events", f"kubectl get events -n {NS} --sort-by=.lastTimestamp")

    save_logs()
    print(f"\nDone. Logs + screenshots saved in {EVID}")
    if a.cleanup:
        subprocess.run(f"kind delete cluster --name {CLUSTER}", shell=True)


if __name__ == "__main__":
    main()
