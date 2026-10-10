#!/usr/bin/env python3
"""Builds Task13_Deployment_Report.pdf (Task 7 report style) from the project files and the
real output recorded by deploy_dl.py in evidence/run_log.json.

    python deploy_dl.py
    # open http://localhost:8090, take a screenshot, save it as evidence/browser_app.png
    python build_report.py --name "Your Name" --id "Your ID" [--github URL]

Needs: pip install reportlab pillow
"""
import argparse, datetime, json, math, os, re, tempfile, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether, Image as RLImage, Flowable)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.pdfgen import canvas as pdfcanvas

ap = argparse.ArgumentParser()
ap.add_argument("--name", default="Shrikant Daulat Nagare"); ap.add_argument("--cls", default="M.Sc. DSBDA - Part 2")
ap.add_argument("--id", default="22"); ap.add_argument("--github", default="")
ARGS = ap.parse_args()

SRC = Path(os.environ.get("T13_ROOT", Path(__file__).parent)); EV = SRC / "evidence"
FIG = Path(tempfile.mkdtemp()); OUT = SRC / "Task13_Deployment_Report.pdf"
if not (EV / "run_log.json").exists():
    raise SystemExit("evidence/run_log.json not found - run deploy_dl.py first")
LOG = json.load(open(EV / "run_log.json"))
FD = '/usr/share/fonts/truetype/dejavu/'
if not os.path.exists(FD):   # macOS / Windows: use matplotlib's bundled DejaVu fonts
    import matplotlib; FD = os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data/fonts/ttf/')

def E(prefix):
    return next((e for e in LOG if e['title'].startswith(prefix)), None)
def OUTP(prefix):
    e = E(prefix); return e['output'] if e else ''
def JS(prefix):
    try: return json.loads(OUTP(prefix))
    except Exception: return None

# ---------- fonts / colours ----------
for n, f in [('DV', 'DejaVuSans.ttf'), ('DV-B', 'DejaVuSans-Bold.ttf'), ('DV-I', 'DejaVuSans-Oblique.ttf'),
             ('DV-BI', 'DejaVuSans-BoldOblique.ttf'), ('DVM', 'DejaVuSansMono.ttf'), ('DVM-B', 'DejaVuSansMono-Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily('DV', normal='DV', bold='DV-B', italic='DV-I', boldItalic='DV-BI')
NAVY = colors.HexColor('#1B3A6B'); BLUE = colors.HexColor('#1F5FA8'); GREY = colors.HexColor('#5A6270')
LGREY = colors.HexColor('#EFEFEF'); LINE = colors.HexColor('#D5D5D5'); CODEBG = colors.HexColor('#0F1419')
W = A4[0] - 4 * cm  # content width

body = ParagraphStyle('body', fontName='DV', fontSize=8.6, leading=13, textColor=colors.HexColor('#222222'), spaceAfter=6)
small = ParagraphStyle('small', parent=body, fontSize=7.8, leading=11, spaceAfter=0)
cell = ParagraphStyle('cell', parent=body, fontSize=7.8, leading=10.5, spaceAfter=0)
cellb = ParagraphStyle('cellb', parent=cell, fontName='DV-B')
cellh = ParagraphStyle('cellh', parent=cell, fontName='DV-B', textColor=colors.white)
title = ParagraphStyle('title', fontName='DV-B', fontSize=21, leading=27, textColor=NAVY, spaceAfter=8)
subtitle = ParagraphStyle('sub', fontName='DV', fontSize=10, leading=14, textColor=GREY, spaceAfter=18)
h2 = ParagraphStyle('h2', fontName='DV-B', fontSize=11, leading=15, textColor=BLUE, spaceBefore=10, spaceAfter=6)
cap = ParagraphStyle('cap', fontName='DV-I', fontSize=7.6, leading=10.5, textColor=GREY, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10)
bullet = ParagraphStyle('bullet', parent=body, leftIndent=14, bulletIndent=2, spaceAfter=4)
num = ParagraphStyle('num', parent=body, leftIndent=16, bulletIndent=0, spaceAfter=5)

def code(t): return f'<font face="DVM" size="7.4" backColor="#E8EEF7">&nbsp;{esc(t)}&nbsp;</font>'
def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
def P(t, st=body): return Paragraph(t, st)

class H1(Table):
    def __init__(self, text):
        p = Paragraph(text, ParagraphStyle('h1', fontName='DV-B', fontSize=14, leading=18, textColor=NAVY))
        Table.__init__(self, [['', p]], colWidths=[4, W - 4])
        self.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), BLUE), ('LEFTPADDING', (1, 0), (1, 0), 8),
                                  ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                                  ('LEFTPADDING', (0, 0), (0, 0), 0), ('RIGHTPADDING', (0, 0), (0, 0), 0)]))
        self.toc_level, self.toc_text, self.keepWithNext = 0, text, 1
        self.spaceAfter = 8; self.spaceBefore = 6
class H2(Paragraph):
    def __init__(self, text):
        Paragraph.__init__(self, text, h2); self.toc_level, self.toc_text, self.keepWithNext = 1, re.sub('<[^>]+>', '', text), 1

class CodeBlock(Flowable):
    LH, FS, PAD = 7.5, 6.1, 8
    def __init__(self, lines, start=1, wrap=118):
        Flowable.__init__(self)
        self.rows = []
        for n, l in enumerate(lines, start):
            l = l.replace('\t', '    ')
            parts = textwrap.wrap(l, wrap, drop_whitespace=False, replace_whitespace=False) or ['']
            for k, pt in enumerate(parts):
                self.rows.append((str(n) if k == 0 else '', ('↳ ' if k else '') + pt))
    def wrap(self, aw, ah):
        self.w = aw; self.h = len(self.rows) * self.LH + 2 * self.PAD; return aw, self.h
    def draw(self):
        c = self.canv; c.setFillColor(CODEBG); c.roundRect(0, 0, self.w, self.h, 3, fill=1, stroke=0)
        y = self.h - self.PAD - self.FS
        for n, t in self.rows:
            c.setFont('DVM', self.FS); c.setFillColor(colors.HexColor('#6E7681')); c.drawRightString(26, y, n)
            c.setFillColor(colors.HexColor('#D6DDE6')); c.drawString(34, y, t); y -= self.LH

# ---------- terminal-style figure renderer (real command output from run_log.json) ----------
MONO = ImageFont.truetype(FD + 'DejaVuSansMono.ttf', 28); CW = MONO.getlength('M'); LH = 42
def pane(e, lines=None):
    out = lines if lines is not None else e['output'].splitlines()
    rows = [('cmd', '$ ' + e['cmd'])]
    for l in out:
        for k, p in enumerate(textwrap.wrap(l, 150, drop_whitespace=False, replace_whitespace=False) or ['']):
            rows.append(('out', ('    ' if k else '') + p))
    return e['title'], rows
def render(panes, name):
    maxc = max(len(t) for _, rows in panes for _, t in rows)
    w = int(max(1800, CW * maxc + 70)); h = sum(54 + LH * len(rows) + 30 for _, rows in panes)
    img = Image.new('RGB', (w, h), (24, 26, 31)); d = ImageDraw.Draw(img); y = 0
    for ttl, rows in panes:
        d.rectangle([0, y, w, y + 50], fill=(50, 54, 62)); d.text((20, y + 9), ttl, fill=(225, 225, 225), font=MONO)
        yy = y + 70
        for kind, t in rows:
            d.text((28, yy), t, fill=(120, 220, 140) if kind == 'cmd' else (228, 228, 228), font=MONO); yy += LH
        y += 54 + LH * len(rows) + 30
    p = FIG / f'{name}.png'; img.save(p); return p

def split_even(lines, maxl=44):
    n = math.ceil(len(lines) / maxl); sz = math.ceil(len(lines) / n); return [lines[i:i + sz] for i in range(0, len(lines), sz)]

def fig_img(path, maxw=W, maxh=21.5 * cm, scale=0.26):
    iw, ih = Image.open(path).size; w = iw * scale; h = ih * scale
    f = min(1, maxw / w, maxh / h); return RLImage(str(path), width=w * f, height=h * f)

# ---------- document ----------
class Doc(BaseDocTemplate):
    def __init__(self, fn):
        BaseDocTemplate.__init__(self, fn, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                                 title='Task 13: Deploying Deep Learning Applications on Kubernetes', author=ARGS.name,
                                 subject='Containerized neural-network digit classifier deployed and exposed on a Kind cluster')
        self.addPageTemplates([PageTemplate(id='p', frames=[Frame(2 * cm, 2 * cm, W, A4[1] - 4 * cm, id='f', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)])])
    def afterFlowable(self, fl):
        if hasattr(fl, 'toc_level'): self.notify('TOCEntry', (fl.toc_level, fl.toc_text, self.page))
class NumCanvas(pdfcanvas.Canvas):
    def __init__(self, *a, **k): pdfcanvas.Canvas.__init__(self, *a, **k); self._saved = []
    def showPage(self): self._saved.append(dict(self.__dict__)); self._startPage()
    def save(self):
        n = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            if self._pageNumber > 1:
                self.setFont('DV', 7.5); self.setFillColor(GREY); self.drawCentredString(A4[0] / 2, 1.1 * cm, f'{self._pageNumber} / {n}')
            pdfcanvas.Canvas.showPage(self)
        pdfcanvas.Canvas.save(self)

S = []
def tbl(data, widths, header=True, label_col=False, zebra=False):
    rows = []
    for r, row in enumerate(data):
        rows.append([c if not isinstance(c, str) else P(c, cellh if (header and r == 0) else (cellb if (label_col and ci == 0) else cell)) for ci, c in enumerate(row)])
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    st = [('GRID', (0, 0), (-1, -1), .5, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LEFTPADDING', (0, 0), (-1, -1), 7)]
    if header: st.append(('BACKGROUND', (0, 0), (-1, 0), NAVY))
    if label_col: st.append(('BACKGROUND', (0, 0), (0, -1), LGREY))
    if zebra: st += [('BACKGROUND', (0, r), (-1, r), colors.HexColor('#F6F8FB')) for r in range(2, len(data), 2)]
    t.setStyle(TableStyle(st)); return t


# ---------- figure plan (order = figure numbers; figures with no recorded output are skipped) ----------
BROWSER = EV / 'browser_app.png'
FIGS = [
 ('build', '6.1 Container image', 'Tool versions, the Docker build of dl-digits:1.0 (the neural network is trained inside the build; last lines shown) and the resulting image.', ['Tool versions', 'Build Docker image', 'Docker image details']),
 ('cluster', '6.2 Cluster setup', 'Creation of the three-node Kind cluster task13 (host port 8090 mapped to NodePort 30090) and selection of its kubectl context.', ['List kind clusters', 'Create Kind cluster', 'Set kubectl context']),
 ('nodes', None, 'All nodes Ready, node listing, and the image loaded into every Kind node (Kind cannot pull a locally built image from a registry).', ['Wait for all nodes Ready', 'Cluster nodes', 'Load image into Kind']),
 ('apply', '6.3 Deployment and services', 'kubectl apply -f k8s13/ creates the Namespace, ConfigMap, Deployment and both Services; rollout status waits for all replicas.', ['Apply manifests', 'Wait for rollout']),
 ('pods', '6.4 Verification of pods and services', 'Pods with their IPs and nodes, and the Deployment, Services (ClusterIP and NodePort), EndpointSlices and ConfigMaps.', ['Get pods', 'Get deployment, services']),
 ('svc', None, 'kubectl describe svc dl-api: NodePort 30090 → targetPort 8000, selector app=dl-api and the pod endpoints.', ['Describe external service']),
 ('health', '6.5 External accessibility', 'Health check and model metadata requested from outside the cluster at http://localhost:8090.', ['Health check', 'Model info']),
 ('predict', None, 'Predictions on ten held-out digit images (GET) and a custom POST /predict request; every response names the pod that answered.', ['Predictions on held-out', 'POST /predict']),
 ('browser', None, 'The application opened in a browser at http://localhost:8090 (classifying a random held-out digit).', 'browser'),
 ('lb', '6.6 Load balancing and in-cluster access', 'Thirty requests to the NodePort Service are spread across the pods; the ClusterIP Service is reached from a temporary pod inside the cluster.', ['Load balancing', 'In-cluster access']),
 ('logs', '6.7 Monitoring deployment status', 'Application logs of one pod (gunicorn access log, including probe requests).', ['Pod logs']),
 ('desc', None, 'kubectl describe deployment dl-api: replicas, rolling-update strategy, image, ports, probes, resources, environment from the ConfigMap and the pod fields, and the ReplicaSet.', ['Deployment details']),
 ('events', None, 'Namespace events sorted by time: scheduling, container start and probe activity.', ['Recent events']),
]
def have(spec): return spec == 'browser' and BROWSER.exists() or (isinstance(spec, list) and any(E(p) for p in spec))
FIGS = [f for f in FIGS if have(f[3])]
FN = {k: i + 1 for i, (k, *_r) in enumerate(FIGS)}
def F(k): return f'Figure {FN[k]}' if k in FN else 'the corresponding figure'

# ---------- parsed results ----------
info = JS('Model info') or {}
health = JS('Health check') or {}
nodes_out = OUTP('Cluster nodes').splitlines()[1:]
node_rows = [l.split() for l in nodes_out if l.strip()]
pods_out = [l.split() for l in OUTP('Get pods').splitlines()[1:] if l.strip()]
running = sum(1 for r in pods_out if len(r) > 2 and r[2] == 'Running' and r[1] == '1/1')
pred_rows = []
for l in OUTP('Predictions on held-out').splitlines():
    m = re.match(r'sample (\d+): predicted (\d)\s+true (\d)\s+confidence ([\d.]+)\s+(OK|ERR)\s+pod (\S+)', l)
    if m: pred_rows.append(list(m.groups()))
correct = sum(1 for r in pred_rows if r[4] == 'OK')
lb_rows = [re.match(r'(\S+): (\d+) requests', l).groups() for l in OUTP('Load balancing').splitlines() if re.match(r'(\S+): (\d+) requests', l)]
incluster_ok = '"status"' in OUTP('In-cluster access') and 'ok' in OUTP('In-cluster access')
m = re.search(r'CreationTimestamp:\s+\w+, (\d+ \w+ \d{4})', OUTP('Deployment details'))
run_date = m.group(1) if m else datetime.date.today().strftime('%d %B %Y')
acc = f"{info['test_accuracy'] * 100:.2f}%" if 'test_accuracy' in info else 'see model-info output'
params = f"{info['parameters']:,}" if 'parameters' in info else '6,570'

S = []
def tbl(data, widths, header=True, label_col=False, zebra=False):
    rows = []
    for r, row in enumerate(data):
        rows.append([c if not isinstance(c, str) else P(c, cellh if (header and r == 0) else (cellb if (label_col and ci == 0) else cell)) for ci, c in enumerate(row)])
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    st = [('GRID', (0, 0), (-1, -1), .5, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LEFTPADDING', (0, 0), (-1, -1), 7)]
    if header: st.append(('BACKGROUND', (0, 0), (-1, 0), NAVY))
    if label_col: st.append(('BACKGROUND', (0, 0), (0, -1), LGREY))
    if zebra: st += [('BACKGROUND', (0, r), (-1, r), colors.HexColor('#F6F8FB')) for r in range(2, len(data), 2)]
    t.setStyle(TableStyle(st)); return t

# ===== Title page =====
S += [Spacer(1, 3.2 * cm), P('Task 13: Deploying Deep Learning Applications on Kubernetes', title),
      P('A Containerized Neural-Network Digit Classifier Served by Flask and gunicorn, Deployed with Declarative Manifests and Exposed Through ClusterIP and NodePort Services', subtitle)]
rows = [['Student Name', ARGS.name], ['Class', ARGS.cls], ['Student ID', ARGS.id],
    ['Tools', f'Docker, Kind, kubectl, Python 3.12, Flask, gunicorn, scikit-learn; automation script {code("deploy_dl.py")}'],
    ['Application', f'Digit classifier: MLP neural network ({params} parameters), held-out accuracy {acc}, REST API and web page'],
    ['Cluster', f'{code("task13")}: 1 control-plane + 2 worker nodes (Kind on Docker Desktop)'],
    ['Exposure', f'ClusterIP {code("dl-api-internal")} (inside the cluster) and NodePort {code("dl-api")} 30090 → {code("http://localhost:8090")}'],
    ['Deployment Result', f'{running} of {len(pods_out)} pods Running 1/1; {correct}/{len(pred_rows)} held-out predictions correct through the Service' if pred_rows else 'See Section 7'],
    ['Run Date', run_date]]
if ARGS.github: rows.append(['GitHub Repository', f'<link href="{ARGS.github}" color="#1F3A9B">{ARGS.github}</link>'])
S.append(tbl(rows, [5.2 * cm, W - 5.2 * cm], header=False, label_col=True)); S.append(PageBreak())

# ===== Contents =====
S.append(H1('Contents')); del S[-1].toc_level
toc = TableOfContents(); toc.dotsMinLevel = 0
toc.levelStyles = [ParagraphStyle('t0', fontName='DV-B', fontSize=9, leading=11.6, leftIndent=0, firstLineIndent=0, textColor=colors.HexColor('#222222')),
                   ParagraphStyle('t1', fontName='DV', fontSize=7.6, leading=9.6, leftIndent=14, firstLineIndent=0, textColor=colors.HexColor('#333333'))]
S += [Spacer(1, 6), toc, PageBreak()]

# ===== 1-3 =====
S += [H1('1. Objective'),
      P('To deploy and expose a containerized deep-learning application in a Kubernetes environment: package a trained neural network and its inference API as a Docker image, describe the deployment and the services in YAML manifests, deploy the application to a cluster, expose it outside the cluster and verify that it is accessible.'),
      H1('2. Reference Tools'),
      P(f'<b>The deep-learning application</b> is a small neural network (a multi-layer perceptron: 64 inputs → 64 ReLU → 32 ReLU → 10 softmax) trained on the UCI handwritten-digits dataset that ships with scikit-learn (1,797 images of 8×8 pixels). It is wrapped in a <b>Flask</b> REST API served by <b>gunicorn</b>. <b>Docker</b> packages it; <b>Kind</b> (Kubernetes IN Docker) provides a local three-node <b>Kubernetes</b> cluster; <b>kubectl</b> deploys and inspects it. The same procedure applies unchanged to a larger model: only the image content changes.'),
      H1('3. Approach'),
      P(f'<b>1. Create deployment manifests</b> — Namespace, ConfigMap and a Deployment with 3 replicas, health probes, resource requests/limits, a non-root security context and spread across nodes (Sections 5.6–5.8).', num),
      P(f'<b>2. Configure services</b> — a ClusterIP Service for internal clients and a NodePort Service for external clients (Sections 5.9–5.10).', num),
      P(f'<b>3. Deploy applications</b> — build the image (the model is trained during the build), load it into the Kind nodes and run {code("kubectl apply -f k8s13/")} ({F("build")}–{F("apply")}).', num),
      P(f'<b>4. Expose services externally</b> — Kind maps host port 8090 to NodePort 30090, so the application is available at {code("http://localhost:8090")} ({F("cluster")}, {F("svc")}).', num),
      P(f'<b>5. Verify application accessibility</b> — health, model-info and prediction requests from outside the cluster, a browser check, load-balancing across pods and a request from inside the cluster through the ClusterIP Service ({F("health")}–{F("lb")}).', num),
      P(f'The whole procedure is automated by {code("deploy_dl.py")}, which records every command and its real output to {code("evidence/run_log.json")}; the figures and result tables in this report are generated from that log.')]

# ===== 4 Architecture =====
S += [H1('4. Architecture'),
      P('One image, one Deployment, two Services. The model is baked into the image at build time, so each pod is self-contained and any pod can answer any request; the Services provide stable addresses and spread requests over the pods.')]
S.append(H2('4.1 Project files'))
S.append(tbl([['File', 'Role'],
    [code('app/app.py'), 'Flask API: web page, /health, /model-info, GET /predict/sample/&lt;i&gt; and POST /predict; every response reports the pod that served it.'],
    [code('app/train_model.py'), 'Trains the MLP on the digits dataset (80/20 split) and saves the model and metadata; run during the image build.'],
    [code('app/Dockerfile'), 'Image definition: python:3.12-slim, dependencies, model training, non-root user, gunicorn entry point.'],
    [code('app/requirements.txt'), 'Python dependencies (Flask, gunicorn, NumPy, scikit-learn, joblib).'],
    [code('kind-config-task13.yaml'), 'Cluster with one control-plane and two workers; host port 8090 mapped to NodePort 30090.'],
    [code('k8s13/*.yaml'), 'Namespace dl-demo, ConfigMap dl-config, Deployment dl-api, Services dl-api-internal and dl-api.'],
    [code('deploy_dl.py'), 'Automation and evidence collection: build, cluster, deploy, expose, verify, monitor.'],
    [code('Task13_DeepLearning_on_Kubernetes.ipynb'), 'Notebook version of the same workflow (alternative to the .py script).']], [6.2 * cm, W - 6.2 * cm], zebra=True))
S.append(H2('4.2 Deployment architecture'))
def diagram():
    H = 250; d = Drawing(W, H)
    def box(x, y, w, h, fill, stroke): d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=0.8))
    def txt(x, y, s, size=7, bold=False, anchor='middle', col=colors.HexColor('#1f2933')):
        d.add(String(x, y, s, fontName='DV-B' if bold else 'DV', fontSize=size, textAnchor=anchor, fillColor=col))
    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=BLUE, strokeWidth=1.3))
        d.add(Line(x2, y2, x2 - 3.5, y2 + 2.5, strokeColor=BLUE, strokeWidth=1.3)); d.add(Line(x2, y2, x2 - 3.5, y2 - 2.5, strokeColor=BLUE, strokeWidth=1.3))
    box(0, 0, W, H, colors.HexColor('#F7F9FC'), colors.HexColor('#C9D3E3'))
    txt(10, H - 16, 'macOS host  ·  Docker Desktop  ·  Kind cluster "task13"', 7.5, True, 'start', NAVY)
    box(10, H - 52, W - 20, 24, colors.HexColor('#EEF3FB'), colors.HexColor('#9FB4D8'))
    txt(W / 2, H - 38, 'Image dl-digits:1.0 (python:3.12-slim + Flask + gunicorn + trained MLP)  →  kind load  →  every node', 6.6, True)
    NX, NY, NH, GAP = 108, 26, 160, 10
    NW = (W - 10 - NX - 2 * GAP) / 3; xs = [NX + i * (NW + GAP) for i in range(3)]
    for x, (n, r) in zip(xs, [('task13-control-plane', '(control-plane)'), ('task13-worker', '(worker)'), ('task13-worker2', '(worker)')]):
        box(x, NY, NW, NH, colors.white, colors.HexColor('#8FA3C4')); txt(x + NW / 2, NY + NH - 14, n, 6.8, True); txt(x + NW / 2, NY + NH - 24, r, 6.3, False, 'middle', GREY)
    box(10, 120, 88, 46, colors.white, BLUE); txt(54, 148, 'Browser / curl', 7, True); txt(54, 136, 'localhost:8090', 6.8)
    box(10, NY + 4, 88, 84, colors.HexColor('#FFF6E5'), colors.HexColor('#E3B25C'))
    for i, (t, b) in enumerate([('Service dl-api', True), ('NodePort 80:30090', False), ('Service dl-api-internal', True), ('ClusterIP 80', False), ('selector app=dl-api', False)]):
        txt(54, NY + 74 - i * 13, t, 6.4 if b else 6.2, b)
    txt(54, NY + 10, 'Namespace dl-demo', 6, False, 'middle', GREY)
    for i, t in enumerate(['kube-apiserver', 'etcd · scheduler', 'controller-manager', 'CoreDNS · kube-proxy']):
        box(xs[0] + 8, NY + NH - 50 - i * 24, NW - 16, 18, colors.HexColor('#EAF1FB'), colors.HexColor('#B7C8E4')); txt(xs[0] + NW / 2, NY + NH - 44 - i * 24, t, 6.3)
    txt(xs[0] + NW / 2, NY + 10, 'host 8090 → NodePort 30090', 5.9, False, 'middle', GREY)
    for x, k in [(xs[1], 2), (xs[2], 1)]:
        for i in range(k):
            box(x + 8, NY + NH - 54 - i * 32, NW - 16, 26, colors.HexColor('#E7F6EC'), colors.HexColor('#7DBB91'))
            txt(x + NW / 2, NY + NH - 40 - i * 32, 'dl-api pod', 6.6, True); txt(x + NW / 2, NY + NH - 48 - i * 32, 'gunicorn :8000 · MLP', 5.8, False, 'middle', GREY)
    arrow(98, 143, xs[0], 143); arrow(xs[0] + NW, 100, xs[1], 100); arrow(xs[1] + NW, 100, xs[2], 100)
    txt(W / 2, 11, 'Diagram 1: Image distribution and request path (illustrative; the scheduler spreads the 3 replicas over the two workers).', 6.3, False, 'middle', GREY)
    return d
S += [diagram(), Spacer(1, 14), P('A request to <i>localhost:8090</i> enters the control-plane node through Kind\'s port mapping, is handled by kube-proxy on NodePort 30090 and is forwarded to one of the ready pods selected by <i>app=dl-api</i>. Pods inside the cluster use the ClusterIP Service <i>dl-api-internal</i>, which load-balances over the same pods.')]
S.append(H2('4.3 Container image'))
S.append(tbl([['Aspect', 'Choice', 'Reason'],
    ['Base image', 'python:3.12-slim', 'Small Python runtime with a good wheel availability for NumPy and scikit-learn.'],
    ['Model', 'Trained in the build (RUN python train_model.py)', 'Image is self-contained: no external model download or volume at start-up; identical model in every pod.'],
    ['Server', 'gunicorn, 2 workers, port 8000', 'Production-style WSGI server instead of the Flask development server.'],
    ['User', 'Non-root UID 10001', 'Least privilege; enforced again by runAsNonRoot in the Pod spec.']], [3 * cm, 6 * cm, W - 9 * cm], zebra=True))
S.append(H2('4.4 Manifest design'))
S.append(tbl([['Setting', 'Value', 'Purpose'],
    ['replicas / strategy', '3 · RollingUpdate (maxSurge 1, maxUnavailable 0)', 'Several pods share the load; updates never reduce capacity.'],
    ['imagePullPolicy', 'IfNotPresent', 'The image exists only locally (loaded into Kind); a registry pull would fail.'],
    ['envFrom ConfigMap', 'dl-config (APP_NAME, MODEL_VERSION)', 'Configuration separated from the image.'],
    ['env fieldRef', 'POD_NAME, NODE_NAME', 'The API reports which pod and node answered, which makes load balancing visible.'],
    ['probes', 'startup, readiness and liveness on /health :8000', 'Traffic only reaches pods whose model is loaded; hung pods are restarted.'],
    ['resources', 'requests 100m / 256Mi · limits 500m / 512Mi', 'Scheduling hint and protection against memory growth.'],
    ['securityContext', 'runAsNonRoot, UID 10001, no privilege escalation', 'Hardening of the container.'],
    ['topologySpread', 'maxSkew 1 on hostname (ScheduleAnyway)', 'Spreads replicas across nodes without blocking scheduling.'],
    ['Services', 'ClusterIP 80 → 8000 · NodePort 30090 → 8000', 'Internal and external access to the same pods.']], [3.4 * cm, 6.2 * cm, W - 9.6 * cm], zebra=True))
S.append(H2('4.5 Running the project'))
for i, c in enumerate(['python deploy_dl.py', 'open http://localhost:8090', 'python build_report.py   # builds the PDF from evidence/'], 1):
    S.append(P(f'{i}. {code(c)}', num))
S.append(P(f'Prerequisites: Docker Desktop running, {code("kubectl")}, {code("kind")} and Python 3 with Pillow. The script builds the image, creates (or re-uses) the {code("task13")} cluster, loads the image, deploys, verifies and records the evidence; {code("--cleanup")} deletes the cluster afterwards.'))
S.append(H2('4.6 Design notes and constraints'))
S.append(tbl([['Topic', 'Detail'],
    ['Loading the image', f'Kind nodes cannot see the host\'s Docker images, so the image is copied in with {code("kind load docker-image")} (the script falls back to {code("docker save")} + {code("kind load image-archive")} if Docker Desktop\'s image store makes the first method fail).'],
    ['Port mapping', 'The host-to-NodePort mapping (8090 → 30090) can only be defined when the cluster is created, so a dedicated cluster configuration is used.'],
    ['Separate cluster', 'The cluster is named task13 and uses host port 8090, so it can coexist with a cluster from another task that uses a different port.'],
    ['Model scope', 'The model is deliberately small so the image builds quickly; the deployment pattern is independent of model size.']], [3.6 * cm, W - 3.6 * cm], zebra=True))
S.append(PageBreak())

# ===== 5 Source =====
DESC = {'Dockerfile': 'container image definition', 'requirements.txt': 'Python dependencies', 'train_model.py': 'model training (runs during the image build)',
        'app.py': 'inference API', 'kind-config-task13.yaml': 'Kind cluster definition', '00-namespace.yaml': 'Namespace', '01-configmap.yaml': 'ConfigMap',
        '02-deployment.yaml': 'Deployment', '03-service-internal.yaml': 'ClusterIP Service', '04-service-external.yaml': 'NodePort Service', 'deploy_dl.py': 'automation script'}
NL = len((SRC / 'deploy_dl.py').read_text().splitlines())
S += [H1('5. Source Code'),
      P(f'Every file needed to reproduce the deployment is listed with line numbers: the application and image (5.1–5.4), the cluster and manifests (5.5–5.10) and the automation script (5.11, {NL} lines). Lines longer than 118 characters are wrapped and continued with "↳".')]
def listing(no, label, path, chunk=60):
    lines = Path(path).read_text().splitlines()
    for i in range(0, len(lines), chunk):
        part = lines[i:i + chunk]; rng = f' (lines {i+1}–{i+len(part)})' if len(lines) > chunk else ''
        S.append(KeepTogether([H2(f'{no} {code(label)} — {DESC[label]}{rng}'), CodeBlock(part, i + 1), Spacer(1, 4)]))
for no, label, path in [('5.1', 'Dockerfile', 'app/Dockerfile'), ('5.2', 'requirements.txt', 'app/requirements.txt'), ('5.3', 'train_model.py', 'app/train_model.py'),
                        ('5.4', 'app.py', 'app/app.py'), ('5.5', 'kind-config-task13.yaml', 'kind-config-task13.yaml'), ('5.6', '00-namespace.yaml', 'k8s13/00-namespace.yaml'),
                        ('5.7', '01-configmap.yaml', 'k8s13/01-configmap.yaml'), ('5.8', '02-deployment.yaml', 'k8s13/02-deployment.yaml'),
                        ('5.9', '03-service-internal.yaml', 'k8s13/03-service-internal.yaml'), ('5.10', '04-service-external.yaml', 'k8s13/04-service-external.yaml'),
                        ('5.11', 'deploy_dl.py', 'deploy_dl.py')]:
    listing(no, label, SRC / path)
S.append(PageBreak())

# ===== 6 Screenshots =====
S += [H1('6. Screenshots and Command Output'),
      P(f'Terminal figures show the exact output captured by {code("deploy_dl.py")} during the run ({code("evidence/run_log.json")}), rendered in a terminal style rather than retyped; the browser figure is a real screen capture. Long outputs are split into parts. Pod names, IPs and timings are those of this particular run.')]
for key, sect, caption, spec in FIGS:
    n = FN[key]; blocks = []
    if sect: blocks.append(H2(sect))
    if spec == 'browser':
        im = Image.open(BROWSER).convert('RGB'); p = FIG / 'browser.png'; im.save(p)
        blocks += [fig_img(p, maxw=W, maxh=13 * cm, scale=1), P(f'Figure {n}: {caption}', cap)]
    else:
        ents = [E(pfx) for pfx in spec if E(pfx)]
        if len(ents) == 1 and len(ents[0]['output'].splitlines()) > 44:
            e = ents[0]; parts = split_even(e['output'].splitlines())
            for j, pl in enumerate(parts, 1):
                pth = render([pane(e, pl)], f'f{n}_{j}'); lbl = f' (part {j} of {len(parts)})'
                blk = [fig_img(pth, scale=0.26), P(f'Figure {n}{lbl}: {caption}' if j == 1 else f'Figure {n}{lbl}: continued.', cap)]
                if j < len(parts): S.append(KeepTogether(blocks + blk)); blocks = []
                else: blocks += blk
        else:
            pth = render([pane(e) for e in ents], f'f{n}'); blocks += [fig_img(pth, scale=0.26), P(f'Figure {n}: {caption}', cap)]
    S.append(KeepTogether(blocks))
S.append(PageBreak())

# ===== 7 Results =====
S += [H1('7. Results'), P('The values below are taken from the run log; the figures referenced show the original output.')]
S.append(H2('7.1 Deployment summary'))
summ = [['Item', 'Result', 'Evidence']]
summ.append(['Image', f'dl-digits:1.0 built from python:3.12-slim; MLP with {params} parameters trained during the build', F('build')])
if node_rows: summ.append(['Cluster', f'task13: {len(node_rows)} nodes — ' + ', '.join(f'{r[0]} ({r[1]})' for r in node_rows if len(r) > 1), F('nodes')])
summ.append(['Objects', 'Namespace dl-demo, ConfigMap dl-config, Deployment dl-api, Services dl-api-internal (ClusterIP) and dl-api (NodePort 30090)', F('apply')])
if pods_out: summ.append(['Pods', f'{running} of {len(pods_out)} pods Running 1/1 (placement shown in the figure)', F('pods')])
if health: summ.append(['Health check', f'GET /health through localhost:8090 → status "{health.get("status")}" from pod {health.get("pod")}', F('health')])
if info: summ.append(['Model', f'{info.get("name")}: {info.get("architecture")}; held-out accuracy {acc} on {info.get("test_images")} test images', F('health')])
if pred_rows: summ.append(['Predictions', f'{correct} of {len(pred_rows)} held-out samples classified correctly through the Service', F('predict')])
if lb_rows: summ.append(['Load balancing', f'30 requests answered by {len(lb_rows)} distinct pods: ' + ', '.join(f'{p[-5:]}: {n}' for p, n in lb_rows), F('lb')])
if E('In-cluster access'): summ.append(['Internal access', 'ClusterIP Service dl-api-internal reachable from inside the cluster' if incluster_ok else 'See figure (in-cluster request did not return the expected health response)', F('lb')])
S.append(tbl(summ, [3.0 * cm, W - 6.2 * cm, 3.2 * cm], zebra=True))
S.append(H2('7.2 Evaluation criteria'))
S.append(tbl([['Criterion', 'How it was met', 'Status'],
    ['Successful deployment', f'Image built and loaded; Deployment rolled out; {running} of {len(pods_out)} pods Running and ready.' if pods_out else 'See Section 6.', 'Met' if pods_out and running == len(pods_out) else 'Check'],
    ['Service accessibility', 'API reachable through the NodePort from the host (curl and browser) and through the ClusterIP Service from inside the cluster; requests are spread over the pods.', 'Met' if health and (incluster_ok or not E('In-cluster access')) else 'Check'],
    ['Configuration quality', 'Declarative manifests with ConfigMap-based configuration, three probes, resource requests/limits, non-root security context, rolling-update strategy and topology spread; the cluster and image are reproducible from the listed files.', 'Met']], [4.2 * cm, W - 6.2 * cm, 2 * cm], zebra=True))
if pred_rows:
    S.append(H2('7.3 Predictions on held-out samples'))
    S.append(tbl([['Sample', 'Predicted', 'True', 'Confidence', 'Result', 'Answered by pod']] + [[r[0], r[1], r[2], r[3], 'correct' if r[4] == 'OK' else 'wrong', r[5]] for r in pred_rows],
                 [1.8 * cm, 2.2 * cm, 1.6 * cm, 2.4 * cm, 2.2 * cm, W - 10.2 * cm], zebra=True))
    S.append(P(f'The samples come from the 20% test split that the model never saw during training; the ten requests show per-image behaviour, while the accuracy of {acc} is measured on all {info.get("test_images", 360)} test images at training time.', small))
if lb_rows:
    S.append(H2('7.4 Load distribution'))
    S.append(tbl([['Pod', 'Requests (of 30)']] + [[p, n] for p, n in lb_rows], [W - 4 * cm, 4 * cm], zebra=True))
S.append(Spacer(1, 6))

# ===== 8-10 =====
lbtxt = f'The 30 requests were answered by {len(lb_rows)} different pods ({", ".join(n for _, n in lb_rows)} requests respectively), showing that the Service distributes traffic across replicas.' if lb_rows else 'The Service distributes requests across the replicas.'
S += [H1('8. Observations'),
      P('<b>Self-contained image.</b> Training the model during the build makes every pod identical and removes any runtime dependency on a model store; the price is that a new model needs a new image and a rollout.', bullet),
      P(f'<b>Image distribution in Kind.</b> The image exists only in the local Docker daemon, so it must be loaded into every Kind node and the Deployment must use {code("imagePullPolicy: IfNotPresent")}; with a registry, the same manifest would simply reference the registry image.', bullet),
      P('<b>Probes protect the model start-up.</b> The startup probe gives the pod time to import scikit-learn and load the model; readiness keeps it out of the Service until it answers, and liveness restarts it if it hangs.', bullet),
      P(f'<b>Two Services, one set of pods.</b> {code("dl-api-internal")} (ClusterIP) serves clients inside the cluster, {code("dl-api")} (NodePort 30090) serves clients outside; both select {code("app=dl-api")} and therefore always target exactly the ready pods.', bullet),
      P(f'<b>Load balancing is visible.</b> Because each response contains the pod name, distribution can be observed directly. {lbtxt}', bullet),
      P('<b>Configuration is externalised.</b> Application name and model version come from the ConfigMap and pod identity from the downward API, so the same image runs unchanged in any environment.', bullet),
      P('<b>Hardening.</b> The container runs as a non-root user with privilege escalation disabled and has CPU and memory limits, which are good defaults for any model-serving workload.', bullet),
      H1('9. Known Limitations'),
      P('• <b>Small model.</b> An MLP on 8×8 digits demonstrates the deployment pattern, not production-scale deep learning; larger models need more memory, possibly GPU nodes and a registry.', bullet),
      P('• <b>Local cluster.</b> All nodes are containers on one machine, so real network paths, node failures and cloud load balancers are not exercised.', bullet),
      P('• <b>NodePort exposure.</b> External access relies on Kind\'s host port mapping; production clusters would normally use an Ingress or a LoadBalancer Service with TLS.', bullet),
      P('• <b>No autoscaling or monitoring stack.</b> There is no metrics-server, HorizontalPodAutoscaler or Prometheus; the replica count is fixed at 3.', bullet),
      P('• <b>No model versioning.</b> The model is part of the image, and there is no A/B or canary rollout between model versions.', bullet),
      H1('10. Conclusion'),
      P('A containerized neural-network classifier was packaged with Docker, loaded into a three-node Kind cluster and deployed through declarative manifests with configuration, probes, resource limits and a hardened security context. It was exposed externally through a NodePort Service and internally through a ClusterIP Service, and its accessibility was verified with health, model-info and prediction requests, a browser check and a load-distribution test. The deliverables are the Kubernetes deployment files (Section 5), the service configurations (5.9–5.10), the screenshots and outputs (Section 6) and this deployment report.')]

Doc(str(OUT)).multiBuild(S, canvasmaker=NumCanvas)
print('Created', OUT)
