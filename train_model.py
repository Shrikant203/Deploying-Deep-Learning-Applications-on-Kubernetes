"""Train a small neural network (multi-layer perceptron) on the UCI handwritten
digits dataset and save it, together with metadata, to model.joblib.
Runs once at image-build time so every container starts with the model baked in."""
import platform
import joblib
import sklearn
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier

digits = load_digits()
X, y = digits.data / 16.0, digits.target          # 8x8 images, pixel values 0-16 -> 0-1
idx = range(len(y))
X_tr, X_te, y_tr, y_te, i_tr, i_te = train_test_split(X, y, list(idx), test_size=0.2, stratify=y, random_state=42)

model = MLPClassifier(hidden_layer_sizes=(64, 32), activation="relu", max_iter=600, random_state=42)
model.fit(X_tr, y_tr)
acc = float(model.score(X_te, y_te))

meta = {
    "name": "digits-mlp",
    "task": "handwritten digit classification (0-9)",
    "architecture": "Input 64 -> Dense 64 (ReLU) -> Dense 32 (ReLU) -> Dense 10 (softmax)",
    "parameters": int(sum(w.size for w in model.coefs_) + sum(b.size for b in model.intercepts_)),
    "train_images": len(y_tr),
    "test_images": len(y_te),
    "test_accuracy": round(acc, 4),
    "test_indices": [int(i) for i in i_te],
    "sklearn_version": sklearn.__version__,
    "python_version": platform.python_version(),
}
joblib.dump({"model": model, "meta": meta}, "model.joblib")
print(f"Trained {meta['name']}: {meta['parameters']} parameters, held-out accuracy {acc:.4f}")
