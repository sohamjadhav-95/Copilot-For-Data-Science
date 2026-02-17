# 🔧 Copilot for Data Science — Setup Guide

Welcome to the **Copilot for Data Science** project! This guide will walk you through the exact steps to set up and run the full application on your local machine, including launching the CLI Copilot with one click.

---

## 📦 Prerequisites

Ensure you have the following installed:

| Tool   | Version         | Notes                                                        |
| ------ | --------------- | ------------------------------------------------------------ |
| Python | 3.10+           | Install from [python.org](https://www.python.org/downloads/) |
| pip    | Latest          | Comes with Python                                            |
| Git    | Latest          | [git-scm.com](https://git-scm.com/)                          |
| ttyd   | Precompiled EXE | For browser-based terminal UI                                |
| ngrok  | Free account    | Required to expose terminal app publicly (optional)          |

---

## 📁 1. Download the Project

You can either **clone the repository** or **download the latest version from Google Drive**:

### Option 1: Clone via GitHub (Use Latest Version)

```bash
git clone https://github.com/yourusername/Copilot-For-Data-Science.git
cd Copilot-For-Data-Science
```

### Option 2: Download ZIP (Latest Version)

* [📥 Download Latest Release via Google Drive](https://drive.google.com/drive/folders/1vv7lUjC58Y1mVB3sDPybx_-4BFwVs-3F?usp=sharing)
* Unzip the folder to a directory of your choice

---

## 📥 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Make sure to clean up or confirm packages in `requirements.txt`. It typically includes:

```text
rich
pandas
scikit-learn
matplotlib
groq
```

---

## 🔐 3. Set Up API Key (Secure, Auto-Managed)

* On first run, the system will prompt you for your **Groq API key**.
* It will be securely saved in `config/api_key.txt`.
* The API key **automatically expires in 7 days** and will be requested again.
* You do **not** need to hardcode your key manually.

---

## 📂 4. Set Dataset Path (Auto-Prompted)

* On first run, you'll be asked to enter the full path to your dataset (.csv).
* This will be saved in `config/dataset_path.txt` and used across the project.
* You can change the dataset by deleting the file or resetting within the app.

---

## 🚀 5. One-Click Launch via `.bat` File

We’ve included a `.bat` file for Windows users:

### ✅ `launch_copilot.bat` — Runs your terminal UI

```bat
@echo off
cd /d %~dp0
start "" "C:\Path\To\ttyd.exe" python rich_cli.py
timeout /t 2 >nul
start "" "C:\Path\To\ngrok.exe" http 7681
```

> Edit this file to match your actual paths to `ttyd.exe` and `ngrok.exe`

### ✅ `Launch Copilot.lnk`

* A shortcut to run the `.bat` file with a custom icon
* Place it on your desktop for one-click access

---

## 🌐 6. Run and Interact

After launching:

* A terminal session will open in your browser
* You’ll be able to type natural language commands
* Outputs, visuals, and results will be returned inside the rich terminal interface

---

## 💬 Example Commands to Try

| Operation        | Example Command                                |
| ---------------- | ---------------------------------------------- |
| Display Data     | "Show me the first 10 rows of the dataset"     |
| Modify Data      | "Remove all rows with null values"             |
| Visualize Data   | "Plot the distribution of the target variable" |
| Analyze Data     | "Generate a summary of the dataset"            |
| Machine Learning | "Build and test a machine learning model"      |

---

## 📁 Project Structure

```
Copilot-For-Data-Science/
├── config/
│   ├── api_key.txt
│   ├── dataset_path.txt
│   ├── api_manager.py
│   └── [other config files]
│
├── launch_copilot.bat
├── Launch Copilot.lnk
├── copilot_icon.ico
├── requirements.txt
├── rich_cli.py
├── README.md
├── setup.md
│
├── Core_Automation_Engine/
│   ├── Engine_Data_analysis.py
│   ├── Engine_Display_data.py
│   ├── Engine_Modify_data.py
│   ├── Engine_Visualize_data.py
│   ├── NL_processor.py
│   ├── Data.py
│   └── [other core engine files]
│
├── Machine_Learning/
│   ├── ML_Models_Engine_autogluon.py
│   └── [other ML files]
│
├── Retrival_Agumented_Generation/
│   ├── rag_command_parser.py
│   ├── commands_database.csv
│   └── [other RAG files]
│
└── data/
    └── [your datasets]
```

---

## 💡 Troubleshooting

* ❌ `Python not found` → Install and add Python to PATH
* ❌ `Module not found` → Rerun `pip install -r requirements.txt`
* ❌ `Groq API error` → Check if your API key is valid or expired
* ❌ `Dataset error` → Check that path exists and points to a valid `.csv` file

---

## 🙋 Need Help?

Reach out to us:

* 📧 [soham.ai.engineer@gmail.com](mailto:soham.ai.engineer@gmail.com)
* 📧 [omkargadakh1272004@gmail.com](mailto:omkargadakh1272004@gmail.com)

---

## ✅ You're Ready!

You now have a fully interactive Copilot AI running in your terminal. Happy building! 🚀
