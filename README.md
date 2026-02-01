## Kid Fever & Medication Tracker

Log a child’s temperature measurements and medications, then visualize trends over time. Built with Streamlit, Plotly, and SQLite for simple local use.

### Requirements
- Python 3.10+ (3.11 recommended)
- pip

Dependencies are listed in `requirements.txt`:
- `streamlit`
- `pandas`
- `plotly`

### Quickstart (macOS/Linux)
1) Create and activate a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Run the app:

```bash
streamlit run vibe/app.py
```

4) Open the URL shown in the terminal (usually `http://localhost:8501`) if a browser doesn’t open automatically.

### Quickstart (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run vibe\app.py
```

### What you can do
- Add temperature measurements with date/time and optional notes.
- Add medications with name, dose/amount, date/time, and optional notes.
- See temperature as a line-plus-points chart; medication events appear as vertical markers with labels and hover details.
- Browse and edit data in tables; delete with an undo option.
- Export measurements and medications as CSV files.

### Data storage
- All data is saved locally in `vibe/data.db` (SQLite).
- The database is created on first run.
- To reset data, stop the app and delete `vibe/data.db`.

### Project structure
```
.
├── requirements.txt
└── vibe/
    ├── app.py   # Streamlit UI and plotting
    └── db.py    # SQLite schema and CRUD functions
```

### Configuration tips
- Change the port:

```bash
streamlit run vibe/app.py --server.port 8502
```

- Run headless (no browser auto-open):

```bash
streamlit run vibe/app.py --server.headless true
```

### Notes
- Temperatures are stored in Celsius.
- Timestamps are saved as local-time ISO-8601 strings (minute precision).
- This app is intended for local, personal use only and does not provide medical advice.
