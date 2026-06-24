import json
import random

# ASR mapping for detection
asr_mapping = [
    "cA' ca", "cA' ka", "coca cA' la", "pAct si", "pep xi", "bAcp si",
    "xtinh", "x ting", "xA tin", "aqua fina", "a qua phi na",
    "seven up", "sA ven Ap", "se vn _p", "by Ap"
]

def load_data():
    files = ["dataset_final.jsonl", "dataset_150_bonus_v2.jsonl"]
    data = []
    for f in files:
        with open(f, "r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    data.append(json.loads(line))
    return data

def is_asr_noisy(text):
    for alias in asr_mapping:
        if alias in text:
            return True
    return False

def format_sample(sample):
    if "entities" not in sample:
        sample["entities"] = {}
        
    entities = sample.get("entities", {})
    prod = entities.get("product")
    
    products = []
    if prod:
        products = [p.strip() for p in prod.split(",")]
        
    sample["entities"]["products"] = products
    if "product" in sample["entities"]:
        del sample["entities"]["product"]
        
    return sample

def main():
    data = load_data()
    
    formatted_data = []
    unlabeled = []
    
    for sample in data:
        if sample.get("type") == "unlabeled" or not sample.get("intent"):
            unlabeled.append(format_sample(sample))
        else:
            formatted_data.append(format_sample(sample))
            
    # Deduplicate
    seen_texts = set()
    unique_data = []
    for sample in formatted_data:
        text = sample.get("text", "")
        if text not in seen_texts:
            seen_texts.add(text)
            unique_data.append(sample)
            
    random.seed(42)
    random.shuffle(unique_data)
    
    normal_test = []
    asr_test = []
    hard_test = []
    
    train_val_pool = []
    
    for sample in unique_data:
        text = sample.get("text", "")
        intent = sample.get("intent", "")
        products = sample.get("entities", {}).get("products", [])
        
        is_hard = len(products) > 1 or intent == "cancel" or intent == "change_product"
        is_asr = is_asr_noisy(text)
        
        if is_hard and len(hard_test) < 25:
            hard_test.append(sample)
        elif is_asr and len(asr_test) < 25:
            asr_test.append(sample)
        elif not is_hard and not is_asr and len(normal_test) < 25:
            normal_test.append(sample)
        else:
            train_val_pool.append(sample)
            
    # Split the remaining into train and val
    val_size = min(50, len(train_val_pool) // 5)
    val_set = train_val_pool[:val_size]
    train_set = train_val_pool[val_size:]
    
    def save_jsonl(data, filename):
        with open(filename, "w", encoding="utf-8") as f:
            for d in data:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                
    save_jsonl(normal_test, "normal_test.jsonl")
    save_jsonl(asr_test, "asr_noise_test.jsonl")
    save_jsonl(hard_test, "hard_test.jsonl")
    save_jsonl(train_set, "train.jsonl")
    save_jsonl(val_set, "val.jsonl")
    save_jsonl(unlabeled, "unlabeled.jsonl")

    print(f"Total labeled: {len(unique_data)}")
    print(f"Normal Test: {len(normal_test)}")
    print(f"ASR Noise Test: {len(asr_test)}")
    print(f"Hard Test: {len(hard_test)}")
    print(f"Validation: {len(val_set)}")
    print(f"Training: {len(train_set)}")
    print(f"Unlabeled: {len(unlabeled)}")

if __name__ == "__main__":
    main()
