# Copilot for Data Science

## 🧠 Overview

"Copilot for Data Science" is a powerful and interactive AI-driven automation platform that streamlines the entire data science workflow — from exploratory data analysis to model deployment — all through **natural language commands**.

The tool interprets user input using NLP and executes dynamic operations like data visualization, cleaning, transformation, machine learning, and analysis.

## 🚀 Use Cases

* Quickly explore datasets by typing "show me the top 10 rows".
* Clean and transform messy CSV files without writing code.
* Auto-generate plots and statistical summaries.
* Build, test, and deploy machine learning models.
* Generate PDF reports and interactive dashboards.
* Perform all of the above via a terminal interface — no GUI required!

## ⚠️ Caution

> This project runs **strictly in terminal/CLI** using Python and Rich. GUI-based services (e.g., Streamlit) are intentionally not used due to performance and flexibility constraints.

If you're looking for a browser-based or GUI version, it's not available in this version.

## ✨ Features

* ✅ **Natural Language Processor** — Understands your commands and routes them correctly.
* ✅ **Data Visualization & Modification** — Perform real-time data edits and visual plots.
* ✅ **Automated Insights & Reporting** — PDF generation, summaries, and pattern analysis.
* ✅ **Machine Learning Module** — Train, test, deploy, and interact with ML models.
* ✅ **Error Explainability** — Dynamic, AI-generated debugging suggestions.
* ✅ **Rich Terminal UI** — Enhanced CLI interface using `rich`.

## 🛠️ Installation

📥 **Download the Latest Version:**

* Always use the **highest/latest version** of the project.
* You can either:

  * Clone the GitHub repository (recommended)
  * Or download it directly via the provided Google Drive link (mentioned in `setup.md`).

📄 **View Full Setup Guide:** [setup.md →](https://github.com/sohamjadhav95/Copilot-For-Data-Science/blob/main/setup.md)

Includes:

* How to download the project (GitHub or Google Drive)
* How to install dependencies
* How to launch the project via `.bat` or terminal
* API key configuration

---

## 📁 Project Directory Structure

```
Copilot-For-Data-Science/
├── launch_copilot.bat
├── Launch Copilot.lnk
├── copilot_icon.ico
├── requirements.txt
├── setup.md
├── README.md
│
├── main.py
├── rich_cli.py
│
├── Core_Automation_Engine/
│   ├── Engine_Data_analysis.py
│   ├── Engine_Display_data.py
│   ├── Engine_Modify_data.py
│   ├── Engine_Visualize_data.py
│   ├── NL_processor.py
│   └── Data.py
│
├── Machine_Learning/
│   └── ML_Models_Engine_autogluon.py
│
├── Retrival_Agumented_Generation/
│   ├── rag_command_parser.py
│   └── commands_database.csv
│
├── config/
│   ├── api_key.txt
│   ├── api_manager.py
│   ├── dataset_path.txt
│   └── [other config files]
│
└── data/
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a new branch (`feature/xyz` or `fix/bug123`)
3. Commit and push your changes
4. Open a pull request

## 📄 License

This project is licensed under the **MIT License** — see the `LICENSE` file for details.

## 📬 Contact

For queries, suggestions, or feedback:

* 📧 **[soham.ai.engineer@gmail.com](mailto:soham.ai.engineer@gmail.com)**
* 📧 **[omkargadakh1272004@gmail.com](mailto:omkargadakh1272004@gmail.com)**
