# 💎 Data-Cleaning-Agent (DataPure AI)

An intelligent data cleaning pipeline that leverages LLMs for deep-layer auditing and automated Pandas script generation.

## 🚀 Project Overview

DataPure AI is an end-to-end automation tool designed to detect anomalies in datasets and apply corrective actions through a remote execution engine. It connects a Streamlit frontend with an n8n workflow engine and a remote Google Colab environment.

## 🛠️ My Technical Contributions

I implemented the following core components and logic for this project:

* **Remote Execution Backend**: I developed the Flask-based backend script designed for Google Colab, utilizing `ngrok` to create a secure tunnel for remote data processing.
* **Safe Code Execution**: I implemented a secure environment using `exec()` with specific `exec_globals` (including `pd` and `np`) and `exec_locals` to safely execute dynamically generated Python scripts against the dataframe.
* **Comprehensive Error Handling**: I built-in error handling to catch syntax errors in AI-generated code and return detailed tracebacks to the frontend for easy troubleshooting.
* **Validation & Sanitization**: I implemented logic to verify that the execution produces a valid pandas DataFrame and returns success status with row/column counts.
* **Streamlit UI Development**: I built the multi-step "DataPure AI" frontend, managing state transitions from file upload to AI auditing and interactive rule definition.
* **n8n Workflow Engineering**: I configured the n8n logic using Groq's Llama-3.3-70b to perform deep-layer audits (detecting outliers, type mismatches, and placeholders) and translate instructions into executable code.
* **Code Safety Layer**: I developed a sanitization layer in the frontend to validate generated code syntax using `compile()` before transmission to the backend, preventing runtime crashes.

## 📂 Repository Structure

```text
Data-Cleaning-Agent-main/
├── app.py                  # Streamlit frontend (UI & code sanitization)
├── Colab-Turnel            # Flask backend for remote code execution
├── Data-Cleaning-Agent.json # n8n workflow configuration (AI Agent)
├── .gitignore              # Project ignore rules
├── LICENSE                 # MIT License
└── README.md               # Project documentation

```

## ⚙️ Architecture & Workflow

1. **Audit Phase**: A sample of the dataset is sent to the n8n AI agent to identify issues like `MISSING_VALUES` or `OUTLIERS`.
2. **Rule Definition**: Users review the audit and select corrective actions (e.g., IQR filtering, ISO 8601 formatting).
3. **Code Generation**: The n8n agent generates a raw Python script based on the selected rules.
4. **Processing**: The validated script and data are sent to the Colab backend via ngrok, where they are executed to produce a clean CSV.

## 🛡️ License

This project is licensed under the MIT License - see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.

---

*Developed by Krishnapalsinh Zala*
