# 🐍 Algo-HR(UV Environment)

This project uses **[uv](https://docs.astral.sh/uv/)** — a modern Python package manager — for managing dependencies, environments, and builds.
It provides fast, reproducible, and isolated Python environments.

---

## 🚀 Project Structure

```
.
├── app/                 # Main application code
├── main.py              # Entry point
├── .env                 # Environment variables
├── pyproject.toml       # Project configuration
├── requirements.txt     # Optional dependencies file
├── uv.lock              # UV lockfile (auto-generated)
└── README.md
```

---

## ⚙️ Installation

### 1. Prerequisites

Make sure you have:

* **Python 3.9+**
* **uv** installed (you can install it with one line):

```bash
pip install uv
```

---

### 2. Clone the Repository

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

---

### 3. Create & Activate Virtual Environment

```bash
uv venv
source .venv/bin/activate   # (Linux/Mac)
# OR
.venv\Scripts\activate      # (Windows)
```

---

### 4. Install Dependencies

```bash
uv sync
```

This will install all dependencies from `pyproject.toml` and lock them using `uv.lock`.

Alternatively, you can install from `requirements.txt` if needed:

```bash
pip install -r requirements.txt
```

---

## 🧠 Running the App

To start the main script:

```bash
uv run python main.py

or 

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Or directly using Python (if venv is activated):

```bash
uv run main.py
```

---

## 🧩 Environment Variables

All environment variables are stored in `.env`.
Create one if it doesn’t exist:

```
ENV=development
API_KEY=your_api_key_here
```

---

## 🧪 Development Commands

| Command               | Description                            |
| --------------------- | -------------------------------------- |
| `uv sync`             | Install and sync dependencies          |
| `uv run <cmd>`        | Run a script inside the UV environment |
| `uv add <package>`    | Add a new dependency                   |
| `uv remove <package>` | Remove a dependency                    |
| `uv lock`             | Regenerate the lockfile                |

---

## 🧾 License

This project is licensed under the [MIT License](LICENSE).


