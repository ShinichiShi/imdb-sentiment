import json
import os
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, roc_curve, auc
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def load_data(input_path="data/processed/"):
    print("Loading data...")
    X_train = sparse.load_npz(f"{input_path}X_train_tfidf.npz")
    X_test = sparse.load_npz(f"{input_path}X_test_tfidf.npz")
    y_train = pd.read_csv(f"{input_path}y_train.csv").values.ravel()
    y_test = pd.read_csv(f"{input_path}y_test.csv").values.ravel()
    print("Data successfully loaded!")
    return X_train, X_test, y_train, y_test

def plot_confusion_matrix(y_true, y_pred, save_path="confusion_matrix.png"):
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=["Negative", "Positive"], yticklabels=["Negative", "Positive"])
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.title("Confusion Matrix")
    plt.savefig(save_path)
    plt.close()
    return save_path

class _NoRun(dict):
    """Stand-in when Neptune is not configured: swallows logging calls."""
    def __getitem__(self, k): return self
    def upload(self, *a, **k): pass
    def stop(self): pass


def init_run():
    """Neptune is optional: set NEPTUNE_API_TOKEN (and NEPTUNE_PROJECT) to enable it."""
    token = os.environ.get("NEPTUNE_API_TOKEN")
    if not token:
        print("NEPTUNE_API_TOKEN not set -> experiment tracking disabled")
        return _NoRun()
    import neptune
    return neptune.init_run(project=os.environ.get("NEPTUNE_PROJECT", "himarygr/imdm-classifier"),
                            api_token=token)


def random_search_log_model(X_train, X_test, y_train, y_test):
    # Initialize Neptune run
    run = init_run()

    print("Initializing RandomizedSearchCV...")

    param_distributions = {
        "C": np.logspace(-4, 4, 20),
        "solver": ["liblinear", "lbfgs", "newton-cg"],
        "max_iter": [100, 200, 300, 500, 1000],
    }

    model = LogisticRegression()

    # Randomized Search
    search = RandomizedSearchCV(
        estimator=model, 
        param_distributions=param_distributions, 
        n_iter=10,  
        scoring="accuracy",
        cv=3, 
        random_state=42,
        verbose=1,
        n_jobs=-1
    )

    print("Performing Random Search...")
    search.fit(X_train, y_train)

    # Neptune
    best_params = search.best_params_
    run["best_parameters"] = best_params
    print(f"Best Parameters: {best_params}")

    best_model = search.best_estimator_
    y_pred = best_model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True)

    run["metrics/accuracy"] = accuracy
    run["metrics/f1_score"] = report["weighted avg"]["f1-score"]

    print(f"Final Test Accuracy: {accuracy:.4f}")


    cm_path = plot_confusion_matrix(y_test, y_pred)
    run["val/conf_matrix"].upload(cm_path)

    fpr, tpr, _ = roc_curve(y_test, best_model.predict_proba(X_test)[:, 1])
    roc_auc = auc(fpr, tpr)
    plt.figure()
    plt.plot(fpr, tpr, color="blue", lw=2, label=f"ROC curve (area = {roc_auc:.2f})")
    plt.plot([0, 1], [0, 1], color="gray", linestyle="--")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("Receiver Operating Characteristic")
    plt.legend(loc="lower right")
    plt_fig_roc = plt.gcf()
    run["val/roc_curve"].upload(plt_fig_roc)
    plt.close()

    metrics = {
        "algorithm": "Logistic Regression on TF-IDF (5000 features)",
        "accuracy": accuracy, "f1": report["weighted avg"]["f1-score"],
        "precision": report["weighted avg"]["precision"], "recall": report["weighted avg"]["recall"],
        "roc_auc": roc_auc, "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "train_size": int(X_train.shape[0]), "test_size": int(X_test.shape[0]),
        "best_params": {k: (v.item() if hasattr(v, "item") else v) for k, v in best_params.items()},
    }
    with open("model/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print("Saved model/metrics.json")

    print("Saving the best model...")
    joblib.dump(best_model, "model/best_sentiment_model.pkl")
    print("Best model saved!")
    
    run.stop()

if __name__ == "__main__":
    X_train, X_test, y_train, y_test = load_data()
    random_search_log_model(X_train, X_test, y_train, y_test)
