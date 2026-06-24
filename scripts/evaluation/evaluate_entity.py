import json
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

def load_entities(true_file, pred_file):
    y_true_prod = []
    y_pred_prod = []
    
    with open(true_file, "r", encoding="utf-8") as f1, open(pred_file, "r", encoding="utf-8") as f2:
        for l1, l2 in zip(f1, f2):
            if not l1.strip() or not l2.strip(): continue
            t1 = json.loads(l1)
            t2 = json.loads(l2)
            
            p1 = t1.get("entities", {}).get("products", [])
            p2 = t2.get("entities", {}).get("products", [])
            
            # Sort to compare or treat as multi-label.
            # For simplicity in template, just stringify the sorted list.
            y_true_prod.append(",".join(sorted(p1)) if p1 else "None")
            y_pred_prod.append(",".join(sorted(p2)) if p2 else "None")
            
    return y_true_prod, y_pred_prod

def evaluate(y_true, y_pred, output_prefix="entity"):
    labels = sorted(list(set(y_true + y_pred)))
    
    # Classification Report
    report = classification_report(y_true, y_pred, labels=labels, zero_division=0)
    print("Classification Report:")
    print(report)
    with open(f"{output_prefix}_classification_report.txt", "w") as f:
        f.write(report)
        
    # Confusion Matrix
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    plt.figure(figsize=(12, 10))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Greens", xticklabels=labels, yticklabels=labels)
    plt.ylabel('Actual')
    plt.xlabel('Predicted')
    plt.title('Entity (Product) Confusion Matrix')
    plt.tight_layout()
    plt.savefig(f"{output_prefix}_confusion_matrix.png")
    print(f"Saved {output_prefix}_confusion_matrix.png")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python evaluate_entity.py <true_jsonl> <pred_jsonl>")
        print("Running with dummy data template...")
        y_true = ["pepsi", "coca,sting", "None", "7up"]
        y_pred = ["pepsi", "coca", "None", "7up"]
        evaluate(y_true, y_pred, "entity_template")
    else:
        y_true, y_pred = load_entities(sys.argv[1], sys.argv[2])
        evaluate(y_true, y_pred, "entity")
