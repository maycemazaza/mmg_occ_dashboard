# NB Taxation Dashboard

Comparison dashboard for OCC and MMG NB_TAXATION data.

## Production Version (Oracle)

Requirements:

- Python 3.12+
- Oracle Instant Client
- Oracle XE
- Correct database credentials

Run:

```bash
python app.py
```

---

## Demo Version (CSV)

No Oracle installation required.

The demo uses:

- sample_data/RA_T_OCC_AGG.csv
- sample_data/RA_T_MMG_AGG.csv

Run:

```bash
python app_demo.py
```

Open:

http://127.0.0.1:5000