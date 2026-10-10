"""Digit-classifier inference service (Flask) used for the Kubernetes deployment."""
import os
import socket
import time

import joblib
import numpy as np
from flask import Flask, jsonify, render_template_string, request
from sklearn.datasets import load_digits

MODEL_PATH = os.getenv("MODEL_PATH", "model.joblib")
APP_NAME = os.getenv("APP_NAME", "DL Digit Classifier")
MODEL_VERSION = os.getenv("MODEL_VERSION", "1.0")
POD = os.getenv("POD_NAME", socket.gethostname())
NODE = os.getenv("NODE_NAME", "unknown")

bundle = joblib.load(MODEL_PATH)
model, meta = bundle["model"], bundle["meta"]
digits = load_digits()
TEST_IDX = meta["test_indices"]
STARTED = time.time()
app = Flask(__name__)

PAGE = """<!doctype html><title>{{name}}</title>
<body style="font-family:sans-serif;max-width:640px;margin:40px auto;text-align:center">
<h1>{{name}}</h1>
<p>Model <b>{{meta.name}}</b> v{{version}} &middot; held-out accuracy <b>{{acc}}%</b></p>
<p>Served by pod <code>{{pod}}</code> on node <code>{{node}}</code></p>
<button onclick="go()" style="font-size:16px;padding:8px 16px">Classify a random held-out digit</button>
<div id="grid" style="display:grid;grid-template-columns:repeat(8,28px);gap:2px;justify-content:center;margin:20px"></div>
<h2 id="out"></h2>
<script>
async function go(){
  const i = Math.floor(Math.random()*{{n}});
  const r = await (await fetch('/predict/sample/'+i)).json();
  const g = document.getElementById('grid'); g.innerHTML='';
  r.pixels.forEach(v=>{const d=document.createElement('div');d.style.cssText='width:28px;height:28px;background:rgb('+(255-v*16)+','+(255-v*16)+','+(255-v*16)+')';g.appendChild(d)});
  document.getElementById('out').textContent = 'Predicted '+r.prediction+' (confidence '+(r.confidence*100).toFixed(1)+'%) - true label '+r.true_label+(r.correct?' (correct)':' (wrong)')+' - answered by '+r.pod;
}
go();
</script>"""


def _predict(pixels):
    x = np.asarray(pixels, dtype=float).reshape(1, 64) / 16.0
    p = model.predict_proba(x)[0]
    k = int(np.argmax(p))
    return {"prediction": k, "confidence": round(float(p[k]), 4),
            "probabilities": {str(i): round(float(v), 4) for i, v in enumerate(p)}}


@app.get("/")
def home():
    return render_template_string(PAGE, name=APP_NAME, meta=meta, version=MODEL_VERSION,
                                  acc=round(meta["test_accuracy"] * 100, 2), pod=POD, node=NODE, n=len(TEST_IDX))


@app.get("/health")
def health():
    return jsonify(status="ok", pod=POD, uptime_s=round(time.time() - STARTED, 1))


@app.get("/model-info")
def model_info():
    info = {k: v for k, v in meta.items() if k != "test_indices"}
    return jsonify(app=APP_NAME, version=MODEL_VERSION, pod=POD, node=NODE, **info)


@app.get("/predict/sample/<int:i>")
def predict_sample(i):
    j = TEST_IDX[i % len(TEST_IDX)]                       # always a held-out image
    out = _predict(digits.data[j])
    out.update(true_label=int(digits.target[j]), correct=out["prediction"] == int(digits.target[j]),
               pixels=[int(v) for v in digits.data[j]], pod=POD)
    return jsonify(out)


@app.post("/predict")
def predict():
    data = request.get_json(silent=True) or {}
    px = data.get("pixels")
    if not isinstance(px, list) or len(px) != 64:
        return jsonify(error="send JSON {'pixels': [64 numbers between 0 and 16]}"), 400
    out = _predict(px)
    out["pod"] = POD
    return jsonify(out)
