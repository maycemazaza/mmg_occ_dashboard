"""
Demo version — uses CSV files instead of Oracle.
No Oracle Instant Client required.

"""

from flask import Flask, render_template_string, request, jsonify
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

app = Flask(__name__)

OCC_CSV = Path("sample_data/RA_T_OCC_AGG.csv")
MMG_CSV = Path("sample_data/RA_T_MMG_AGG.csv")


def fetch_comparison(start_date: str, end_date: str):
    """
    start_date / end_date: strings in DD-MM-YYYY format (same as Oracle version).
    Returns the same dict shape as the Oracle version.
    """
    try:
        start = datetime.strptime(start_date, "%d-%m-%Y")
        end   = datetime.strptime(end_date,   "%d-%m-%Y")

        occ = pd.read_csv(OCC_CSV, parse_dates=["START_DATE"], dayfirst=True)
        mmg = pd.read_csv(MMG_CSV, parse_dates=["START_DATE"], dayfirst=True)

        # Normalise column names to uppercase for safety
        occ.columns = occ.columns.str.upper()
        mmg.columns = mmg.columns.str.upper()

        # Truncate to date only, then group/sum
        occ["DT"] = occ["START_DATE"].dt.normalize()
        mmg["DT"] = mmg["START_DATE"].dt.normalize()

        occ_agg = (
            occ[(occ["DT"] >= start) & (occ["DT"] <= end)]
            .groupby("DT", as_index=False)["NB_TAXATION"]
            .sum()
            .rename(columns={"NB_TAXATION": "occ_nb"})
        )
        mmg_agg = (
            mmg[(mmg["DT"] >= start) & (mmg["DT"] <= end)]
            .groupby("DT", as_index=False)["NB_TAXATION"]
            .sum()
            .rename(columns={"NB_TAXATION": "mmg_nb"})
        )

        merged = pd.merge(occ_agg, mmg_agg, on="DT").sort_values("DT")

        rows = []
        for _, row in merged.iterrows():
            occ_nb = int(row["occ_nb"])
            mmg_nb = int(row["mmg_nb"])
            diff   = occ_nb - mmg_nb
            gap_pct = round(abs(diff) / mmg_nb * 100, 2) if mmg_nb else 0.0
            rows.append({
                "dt":      row["DT"].strftime("%Y-%m-%d"),
                "occ_nb":  occ_nb,
                "mmg_nb":  mmg_nb,
                "diff":    diff,
                "gap_pct": gap_pct,
            })

    except Exception as e:
        return None, str(e)

    total_occ  = sum(r["occ_nb"] for r in rows)
    total_mmg  = sum(r["mmg_nb"] for r in rows)
    total_diff = total_occ - total_mmg
    match_rate = (
        round(min(total_occ, total_mmg) / max(total_occ, total_mmg) * 100, 2)
        if total_mmg else 0
    )

    return {
        "rows":       rows,
        "total_occ":  total_occ,
        "total_mmg":  total_mmg,
        "total_diff": total_diff,
        "match_rate": match_rate,
    }, None


# ── Same HTML from app.py ────────────────────────────────────
from app import HTML   # single source of truth for the template


@app.route("/")
def index():
    today = datetime.today()
    default_end   = today.strftime("%Y-%m-%d")
    default_start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
    return render_template_string(HTML, default_start=default_start, default_end=default_end)


@app.route("/api/data")
def api_data():
    start = request.args.get("start", "")
    end   = request.args.get("end",   "")
    try:
        s = datetime.strptime(start, "%Y-%m-%d").strftime("%d-%m-%Y")
        e = datetime.strptime(end,   "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return jsonify({"error": "Invalid date format"})

    result, err = fetch_comparison(s, e)
    if err:
        return jsonify({"error": err})
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)