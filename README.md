# NB Taxation Dashboard — OCC vs MMG

A self-contained Flask application that connects directly to an Oracle database and displays a live comparison of **OCC** and **MMG** `NB_Taxation` volumes — KPI cards, a daily comparison table, and a bar chart — for any selected date range.

The entire frontend (HTML/CSS/JavaScript) is embedded inside `app.py` as a single template string; there are no separate template or static files.

---

## What's in this folder

| File | Purpose |
|---|---|
| `app.py` | The Flask application — backend route logic, Oracle queries, and the embedded HTML/JS frontend all live here |
| `requirements.txt` | Python packages the app depends on |
| `.env.example` | Template showing which environment variables to set — copy this to `.env` |
| `README.md` | This file |

> `.env` itself is **not** included in this repo (it should be listed in `.gitignore`) because it holds your real database password. Create it locally using `.env.example` as a guide.

---

## Requirements

- Python 3.9+
- **Oracle Instant Client** — this app connects in *thick mode*, which requires the Instant Client libraries to be installed locally (see Setup step 2 below). This is different from the lightweight "thin mode" connection some other oracledb-based scripts use.
- Access to an Oracle database containing `RA_T_OCC_AGG` and `RA_T_MMG_AGG` (or equivalent tables with `START_DATE` and `NB_TAXATION` columns)
- Python packages, pinned in `requirements.txt`:
  - `Flask==3.1.1`
  - `oracledb==3.3.0`
  - `pandas==2.3.1` *(currently unused by `app.py` — kept in case it's needed later; safe to remove if you want a leaner install)*
  - `python-dotenv==1.2.2`

---

## Setup

### 1. Install dependencies

```bash
cd path\to\this\folder
pip install -r requirements.txt
```

### 2. Install Oracle Instant Client

Download the Instant Client package matching your Oracle version from Oracle's website, and unzip it somewhere on your machine.

Then open `app.py` and update this line near the top to point at wherever you extracted it:

```python
oracledb.init_oracle_client(
    lib_dir=r"C:YOUR-PATH"
)
```

⚠️ You **must** update this path, or the app will fail to start with a `DPI-1047` error (Oracle Client library not found).

### 3. Configure your database connection

Copy the provided template and fill in your real values:

```bash
copy .env.example .env
```

Then open `.env` and edit it:

```
DB_USER=your_username_here
DB_PASSWORD=your_password_here
DB_DSN=localhost:1521/XE
```

| Variable | What to put |
|---|---|
| `DB_USER` | Your Oracle username |
| `DB_PASSWORD` | Your Oracle password |
| `DB_DSN` | `host:port/service_name` — for a local Oracle XE install this is usually `localhost:1521/XE` |


---

## Running the app

```bash
python app.py
```

By default this runs in debug mode on:

```
http://localhost:5000
```

(It binds to `0.0.0.0`, so it's also reachable from other devices on your network at your machine's local IP, e.g. `http://192.168.x.x:5000`.)

To stop the server, go back to the terminal and press `Ctrl + C`.

---

## Using the dashboard

1. Open `http://localhost:5000` in a browser. The date pickers default to the **last 7 days**.
2. Adjust the **From** / **To** dates as needed.
3. Click **⚡ Run** to query the database and render results.

The page displays:

- **Three KPI cards** — OCC total, MMG total, and Match Rate
- **Daily comparison table** — Date, OCC, MMG, Difference, and Gap %, with Gap % color-coded (green ≤3%, amber 3–10%, red >10%) and Difference shown in red/green depending on direction
- **Grouped bar chart** — OCC vs MMG volumes per day (via Chart.js, loaded from CDN)

---

## API endpoint

The frontend calls a small JSON API internally, which you can also query directly:

```
GET /api/data?start=YYYY-MM-DD&end=YYYY-MM-DD
```

**Example:**
```
http://localhost:5000/api/data?start=2026-05-01&end=2026-05-07
```

**Response shape:**
```json
{
  "rows": [
    { "dt": "2026-05-01", "occ_nb": 432996, "mmg_nb": 438394, "diff": -5398, "gap_pct": 1.23 }
  ],
  "total_occ": 2945680,
  "total_mmg": 3114191,
  "total_diff": -168511,
  "match_rate": 94.59
}
```

Note that the underlying SQL query **inner-joins** OCC and MMG on matching dates — if a date exists in one table but not the other, that date is silently excluded from the results entirely (it won't show as a zero row).

---

