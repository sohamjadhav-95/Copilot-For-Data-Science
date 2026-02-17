import os
import pandas as pd

CONFIG_PATH = os.path.join("config", "dataset_path.txt")

# Prompt user for dataset path if not stored
def get_dataset_path():
    os.makedirs("config", exist_ok=True)

    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            path = f.read().strip()
            if os.path.exists(path) and path.endswith(".csv"):
                return path
            else:
                print("⚠️ Saved dataset path is invalid or missing.")
    
    # Prompt user for new path
    while True:
        path = input("📂 Enter the full path to your dataset (.csv): ").strip()
        if os.path.exists(path) and path.endswith(".csv"):
            with open(CONFIG_PATH, "w") as f:
                f.write(path)
            print("✅ Dataset path saved.")
            return path
        else:
            print("❌ Invalid path or not a CSV. Try again.")

# Use the dynamic dataset path in functions
def Data_rows():
    try:
        dataset = pd.read_csv(get_dataset_path())
        first_100_rows = dataset.head(100)
        last_100_rows = dataset.tail(100)
        return first_100_rows, last_100_rows
    except Exception as e:
        print(f"An error occurred in Data_rows: {e}")
        return None, None

def filepath():
    return get_dataset_path()

def dataset_features():
    try:
        dataset = pd.read_csv(filepath())
        return {
            "shape": dataset.shape,
            "size": dataset.size,
            "columns": dataset.columns,
            "dtypes": dataset.dtypes
        }
    except Exception as e:
        print(f"An error occurred in dataset_features: {e}")
        return {}
