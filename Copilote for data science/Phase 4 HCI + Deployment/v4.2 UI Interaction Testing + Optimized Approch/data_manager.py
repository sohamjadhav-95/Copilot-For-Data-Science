# data_manager.py — Dataset loading, saving, backup, and undo operations
import os
import shutil
import pandas as pd

MODIFIED_DIR = "modified_files"


def ensure_modified_dir():
    """Create the modified_files directory if it doesn't exist."""
    os.makedirs(MODIFIED_DIR, exist_ok=True)


def save_uploaded_file(uploaded_file):
    """Save an uploaded CSV to the modified_files directory and return path."""
    ensure_modified_dir()
    save_path = os.path.join(MODIFIED_DIR, uploaded_file.name)
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return save_path


def load_dataframe(file_path):
    """Load a CSV into a DataFrame."""
    return pd.read_csv(file_path)


def get_df_info(df, file_path):
    """Return a dict of dataset metadata for AI prompts."""
    return {
        "file_path": file_path,
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "head": df.head(50).to_string(max_rows=50),
        "tail": df.tail(20).to_string(max_rows=20),
    }


def create_backup(file_path):
    """Create a .backup copy before modifications."""
    backup_path = file_path + ".backup"
    if os.path.exists(file_path):
        shutil.copy(file_path, backup_path)
    return backup_path


def undo_last_change(file_path):
    """Restore the dataset from the last backup."""
    backup_path = file_path + ".backup"
    if os.path.exists(backup_path):
        shutil.copy(backup_path, file_path)
        return True, "✅ Undo successful — data restored from the last backup."
    return False, "⚠️ No backup found. Cannot undo."
