"""
Production version.

Requires:
- Oracle Database
- Oracle Instant Client
- Proper DB credentials
"""
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template_string, request, jsonify
import oracledb
oracledb.init_oracle_client(
    lib_dir=r"C:\Users\Lenovo\Desktop\inclient\instantclient_23_0"
)
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# ─── DB CONFIG ────────────────────────────────────────────────────────────────
import os
DB_USER     = os.getenv("DB_USER", "maycem")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_DSN      = os.getenv("DB_DSN", "localhost:1521/XE")

def get_connection():
    return oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)


# ─── QUERY ────────────────────────────────────────────────────────────────────
def fetch_comparison(start_date: str, end_date: str):
    """
    Returns a list of dicts:
      { date, occ_nb, mmg_nb, difference, gap_pct }
    plus totals.
    """

    sql = """
    SELECT
        o.dt,
        o.occ_nb,
        m.mmg_nb,
        o.occ_nb - m.mmg_nb AS diff,
        ROUND(
            ABS(o.occ_nb - m.mmg_nb)
            / NULLIF(m.mmg_nb, 0) * 100,
            2
        ) AS gap_pct
    FROM (
        SELECT
            TRUNC(START_DATE) AS dt,
            SUM(NB_TAXATION) AS occ_nb
        FROM RA_T_OCC_AGG
        WHERE TRUNC(START_DATE)
              BETWEEN TO_DATE(:start_dt,'DD-MM-YYYY')
                  AND TO_DATE(:end_dt,'DD-MM-YYYY')
        GROUP BY TRUNC(START_DATE)
    ) o
    JOIN (
        SELECT
            TRUNC(START_DATE) AS dt,
            SUM(NB_TAXATION) AS mmg_nb
        FROM RA_T_MMG_AGG
        WHERE TRUNC(START_DATE)
              BETWEEN TO_DATE(:start_dt,'DD-MM-YYYY')
                  AND TO_DATE(:end_dt,'DD-MM-YYYY')
        GROUP BY TRUNC(START_DATE)
    ) m
      ON o.dt = m.dt
    ORDER BY o.dt
    """

    rows = []

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            print("=" * 60)
            print("START DATE:", start_date)
            print("END DATE:  ", end_date)

            # Show which DB and user we're connected to
            cur.execute("""
                SELECT
                    SYS_CONTEXT('USERENV','DB_NAME'),
                    SYS_CONTEXT('USERENV','SERVICE_NAME'),
                    USER
                FROM dual
            """)

            print("CONNECTED TO:", cur.fetchone())

            # Simple test on OCC
            cur.execute("""
                SELECT COUNT(*)
                FROM RA_T_OCC_AGG
                WHERE TRUNC(START_DATE)
                BETWEEN TO_DATE('01-05-2026','DD-MM-YYYY')
                    AND TO_DATE('31-05-2026','DD-MM-YYYY')
            """)

            print("OCC COUNT:", cur.fetchone()[0])

            # Simple test on MMG
            cur.execute("""
                SELECT COUNT(*)
                FROM RA_T_MMG_AGG
                WHERE TRUNC(START_DATE)
                BETWEEN TO_DATE('01-05-2026','DD-MM-YYYY')
                    AND TO_DATE('31-05-2026','DD-MM-YYYY')
            """)

            print("MMG COUNT:", cur.fetchone()[0])

            # Execute main query
            cur.execute(sql, start_dt=start_date, end_dt=end_date)

            all_rows = cur.fetchall()

            print("MAIN QUERY ROWS:", len(all_rows))

            if all_rows:
                print("FIRST ROW:", all_rows[0])

            print("=" * 60)

            cols = [d[0].lower() for d in cur.description]

            for row in all_rows:
                d = dict(zip(cols, row))

                d["dt"] = (
                    d["dt"].strftime("%Y-%m-%d")
                    if hasattr(d["dt"], "strftime")
                    else str(d["dt"])
                )

                d["occ_nb"] = int(d["occ_nb"] or 0)
                d["mmg_nb"] = int(d["mmg_nb"] or 0)
                d["diff"] = int(d["diff"] or 0)
                d["gap_pct"] = float(d["gap_pct"] or 0)

                rows.append(d)

    except Exception as e:
        print("ERROR:", e)
        return None, str(e)

    total_occ = sum(r["occ_nb"] for r in rows)
    total_mmg = sum(r["mmg_nb"] for r in rows)
    total_diff = total_occ - total_mmg

    match_rate = (
        round(min(total_occ, total_mmg) / max(total_occ, total_mmg) * 100, 2)
        if total_mmg else 0
    )

    return {
        "rows": rows,
        "total_occ": total_occ,
        "total_mmg": total_mmg,
        "total_diff": total_diff,
        "match_rate": match_rate,
    }, None
# ─── HTML TEMPLATE ────────────────────────────────────────────────────────────
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>NB Taxation — OCC vs MMG</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  /* ── reset & base ── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --navy:   #1a2744;
    --blue:   #2e6db4;
    --blue-lt:#4a90d9;
    --salmon: #e8897a;
    --green:  #3a9e6e;
    --red:    #c0392b;
    --bg:     #f0f4fa;
    --card:   #ffffff;
    --text:   #1e2a3a;
    --muted:  #6b7a90;
    --border: #dce4f0;
    --mono: 'JetBrains Mono', 'Fira Mono', 'Courier New', monospace;
    --sans: 'Inter', system-ui, sans-serif;
  }
  body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* ── header ── */
  header {
    background: var(--navy);
    padding: 0 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 60px;
    position: sticky; top: 0; z-index: 100;
    box-shadow: 0 2px 12px rgba(0,0,0,.35);
  }
  header h1 {
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #fff;
    display: flex; align-items: center; gap: .6rem;
  }
  header h1 span.accent { color: var(--blue-lt); }

  /* ── date bar ── */
  .date-bar {
    background: var(--card);
    border-bottom: 1px solid var(--border);
    padding: .9rem 2rem;
    display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
  }
  .date-bar label { font-size: .78rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing:.05em; }
  .date-bar input[type=date] {
    border: 1.5px solid var(--border);
    border-radius: 6px;
    padding: .45rem .75rem;
    font-family: var(--sans);
    font-size: .88rem;
    color: var(--text);
    background: var(--bg);
    outline: none;
    transition: border-color .2s;
  }
  .date-bar input[type=date]:focus { border-color: var(--blue-lt); }
  .date-bar button {
    background: var(--blue);
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: .48rem 1.4rem;
    font-size: .88rem;
    font-weight: 600;
    cursor: pointer;
    transition: background .2s, transform .1s;
  }
  .date-bar button:hover { background: var(--blue-lt); }
  .date-bar button:active { transform: scale(.97); }
  #status { font-size: .82rem; color: var(--muted); margin-left: auto; }

  /* ── main layout ── */
  main { padding: 1.6rem 2rem 3rem; max-width: 1300px; margin: 0 auto; }

  /* ── KPI cards ── */
  .kpi-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.2rem; margin-bottom: 1.6rem; }
  .kpi {
    border-radius: 10px;
    padding: 1.4rem 1.6rem;
    color: #fff;
    position: relative;
    overflow: hidden;
  }
  .kpi.occ { background: linear-gradient(135deg, #2e6db4 0%, #1a4a80 100%); }
  .kpi.mmg { background: linear-gradient(135deg, #c0694a 0%, #a04030 100%); }
  .kpi.match { background: linear-gradient(135deg, #3a9e6e 0%, #267350 100%); }
  .kpi-label { font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; opacity: .8; margin-bottom: .6rem; }
  .kpi-value { font-size: 2.2rem; font-weight: 800; font-family: var(--mono); letter-spacing: -.02em; }
  .kpi::after {
    content: '';
    position: absolute; right: -20px; bottom: -20px;
    width: 100px; height: 100px;
    border-radius: 50%;
    background: rgba(255,255,255,.08);
  }

  /* ── content row ── */
  .content-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1.4rem; }

  /* ── card ── */
  .card {
    background: var(--card);
    border-radius: 10px;
    border: 1px solid var(--border);
    overflow: hidden;
  }
  .card-header {
    background: var(--navy);
    color: #fff;
    font-size: .78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
    padding: .75rem 1.2rem;
  }

  /* ── table ── */
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: .82rem; }
  thead th {
    background: #edf2fb;
    color: var(--muted);
    font-weight: 700;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .06em;
    padding: .65rem 1rem;
    text-align: right;
    border-bottom: 1.5px solid var(--border);
  }
  thead th:first-child { text-align: left; }
  tbody tr { border-bottom: 1px solid var(--border); transition: background .15s; }
  tbody tr:hover { background: #f4f8ff; }
  tbody td { padding: .6rem 1rem; text-align: right; font-family: var(--mono); font-size: .8rem; }
  tbody td:first-child { text-align: left; font-family: var(--sans); font-weight: 600; font-size: .82rem; color: var(--text); }
  .diff-cell { font-weight: 700; }
  .diff-pos { color: var(--red); }
  .diff-neg { color: var(--green); }
  tfoot td {
    background: var(--navy);
    color: #fff;
    font-weight: 800;
    padding: .7rem 1rem;
    text-align: right;
    font-family: var(--mono);
  }
  tfoot td:first-child { text-align: left; font-family: var(--sans); }
  .gap-high { color: #ff6b6b; font-weight: 700; }
  .gap-mid  { color: #f0a500; font-weight: 700; }
  .gap-low  { color: #3a9e6e; font-weight: 700; }

  /* ── chart card ── */
  .chart-wrap { padding: 1.2rem; height: 310px; }

  /* ── empty / error ── */
  .placeholder {
    padding: 3rem;
    text-align: center;
    color: var(--muted);
    font-size: .9rem;
  }

  /* ── loader ── */
  #loader {
    display: none;
    position: fixed; inset: 0;
    background: rgba(15,25,45,.55);
    z-index: 999;
    align-items: center; justify-content: center;
  }
  #loader.active { display: flex; }
  .spinner {
    width: 42px; height: 42px;
    border: 4px solid rgba(255,255,255,.2);
    border-top-color: var(--blue-lt);
    border-radius: 50%;
    animation: spin .7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  @media(max-width:900px) {
    .kpi-row { grid-template-columns: 1fr; }
    .content-row { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<div id="loader"><div class="spinner"></div></div>

<header>
  <h1>📡 NB Taxation — <span class="accent">OCC</span> vs <span class="accent">MMG</span></h1>
</header>

<div class="date-bar">
  <label for="startDate">From</label>
  <input type="date" id="startDate" value="{{ default_start }}"/>
  <label for="endDate">To</label>
  <input type="date" id="endDate" value="{{ default_end }}"/>
  <button onclick="loadData()">⚡ Run</button>
  <span id="status"></span>
</div>

<main>
  <!-- KPIs -->
  <div class="kpi-row">
    <div class="kpi occ">
      <div class="kpi-label">OCC Total NB_Taxation</div>
      <div class="kpi-value" id="kpiOCC">—</div>
    </div>
    <div class="kpi mmg">
      <div class="kpi-label">MMG Total NB_Taxation</div>
      <div class="kpi-value" id="kpiMMG">—</div>
    </div>
    <div class="kpi match">
      <div class="kpi-label">Match Rate</div>
      <div class="kpi-value" id="kpiMatch">—</div>
    </div>
  </div>

  <!-- Table + Chart -->
  <div class="content-row">
    <div class="card">
      <div class="card-header">Daily NB_Taxation Comparison</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>OCC NB_Taxation</th>
              <th>MMG NB_Taxation</th>
              <th>Difference</th>
              <th>Gap %</th>
            </tr>
          </thead>
          <tbody id="tableBody">
            <tr><td colspan="5" class="placeholder">Select a date range and click Run.</td></tr>
          </tbody>
          <tfoot id="tableFoot"></tfoot>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-header">OCC NB_Taxation &amp; MMG NB_Taxation</div>
      <div class="chart-wrap">
        <canvas id="barChart"></canvas>
      </div>
    </div>
  </div>
</main>

<script>
let chart = null;

function fmt(n) {
  return n == null ? '—' : n.toLocaleString('en-US');
}
function gapClass(p) {
  if (p > 10) return 'gap-high';
  if (p > 3)  return 'gap-mid';
  return 'gap-low';
}

async function loadData() {
  const start = document.getElementById('startDate').value;
  const end   = document.getElementById('endDate').value;
  if (!start || !end) { alert('Please select both dates.'); return; }
  if (start > end)    { alert('Start date must be before end date.'); return; }

  document.getElementById('loader').classList.add('active');
  document.getElementById('status').textContent = 'Querying…';

  try {
    const resp = await fetch(`/api/data?start=${start}&end=${end}`);
    const data = await resp.json();

    if (data.error) {
      document.getElementById('status').textContent = '⚠ ' + data.error;
      document.getElementById('loader').classList.remove('active');
      return;
    }

    renderKPIs(data);
    renderTable(data.rows, data.total_occ, data.total_mmg, data.total_diff);
    renderChart(data.rows);
    document.getElementById('status').textContent =
      `✔ ${data.rows.length} day(s) loaded`;
  } catch(e) {
    document.getElementById('status').textContent = '⚠ Network error';
  } finally {
    document.getElementById('loader').classList.remove('active');
  }
}

function renderKPIs(data) {
  document.getElementById('kpiOCC').textContent   = fmt(data.total_occ);
  document.getElementById('kpiMMG').textContent   = fmt(data.total_mmg);
  document.getElementById('kpiMatch').textContent = data.match_rate.toFixed(2) + '%';
}

function renderTable(rows, totOcc, totMmg, totDiff) {
  const tbody = document.getElementById('tableBody');
  const tfoot = document.getElementById('tableFoot');

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="placeholder">No data for the selected range.</td></tr>';
    tfoot.innerHTML = '';
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const cls = r.diff > 0 ? 'diff-pos' : r.diff < 0 ? 'diff-neg' : '';
    const sign = r.diff > 0 ? '+' : '';
    return `<tr>
      <td>${r.dt}</td>
      <td>${fmt(r.occ_nb)}</td>
      <td>${fmt(r.mmg_nb)}</td>
      <td class="diff-cell ${cls}">${sign}${fmt(r.diff)}</td>
      <td class="${gapClass(r.gap_pct)}">${r.gap_pct.toFixed(2)}%</td>
    </tr>`;
  }).join('');

  const diffSign = totDiff > 0 ? '+' : '';
  tfoot.innerHTML = `<tr>
    <td>TOTAL</td>
    <td>${fmt(totOcc)}</td>
    <td>${fmt(totMmg)}</td>
    <td>${diffSign}${fmt(totDiff)}</td>
    <td></td>
  </tr>`;
}

function renderChart(rows) {
  const labels  = rows.map(r => r.dt);
  const occData = rows.map(r => r.occ_nb);
  const mmgData = rows.map(r => r.mmg_nb);

  if (chart) { chart.destroy(); }

  chart = new Chart(document.getElementById('barChart'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'OCC NB_Taxation',
          data: occData,
          backgroundColor: '#2e6db4cc',
          borderColor: '#2e6db4',
          borderWidth: 1.5,
          borderRadius: 4,
        },
        {
          label: 'MMG NB_Taxation',
          data: mmgData,
          backgroundColor: '#e8897acc',
          borderColor: '#c0694a',
          borderWidth: 1.5,
          borderRadius: 4,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { font: { size: 11 }, boxWidth: 14, padding: 16 }
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString('en-US')}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 10 }, maxRotation: 45 }
        },
        y: {
          grid: { color: '#e8edf5' },
          ticks: {
            font: { size: 10 },
            callback: v => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v
          }
        }
      }
    }
  });
}
</script>
</body>
</html>
"""


# ─── ROUTES ───────────────────────────────────────────────────────────────────
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
    # convert YYYY-MM-DD → DD-MM-YYYY for Oracle TO_DATE
    try:
        s = datetime.strptime(start, "%Y-%m-%d").strftime("%d-%m-%Y")
        e = datetime.strptime(end,   "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return jsonify({"error": "Invalid date format"})

    result, err = fetch_comparison(s, e)
    if err:
        return jsonify({"error": err})
    return jsonify(result)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
