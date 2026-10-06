"""Render docs/index.html from data/ (run fetch.py first)."""

import datetime
import json
import zoneinfo
from pathlib import Path

import pandas as pd

PT = zoneinfo.ZoneInfo("America/Los_Angeles")
BASE = Path(__file__).parent
DATA = BASE / "data"
DAILY_DAYS = 90
INSTITUTION_THRESHOLD = 5


def term_label(term):
    season, year = term.split("_", 1)
    return f"{season.title()} {year}"


sem = pd.read_csv(DATA / "semesters.csv")
term_cols = [c for c in sem.columns if c not in ("college", "all-users", "all-users-ever-active")]
semesters = [{"label": term_label(c), "users": int(sem[c].sum())} for c in term_cols]
while semesters and semesters[-1]["users"] == 0:  # drop future, all-zero terms
    semesters.pop()
while semesters and semesters[0]["users"] == 0:  # and terms before the first hub
    semesters.pop(0)

# Institutions: more than 5 users in any term of the current academic year
# (Fall Y, Spring Y+1, Summer Y+1), the same rule the pilot-hub page uses.
today = datetime.datetime.now(PT).date()
ay = today.year if today.month >= 8 else today.year - 1
ay_terms = [t for t in (f"fall_{ay}", f"spring_{ay + 1}", f"summer_{ay + 1}") if t in sem.columns]
institutions = int((sem[ay_terms].max(axis=1) > INSTITUTION_THRESHOLD).sum()) if ay_terms else 0
current = next((c for c in reversed(term_cols) if sem[c].sum() > 0), None)

monthly = pd.read_csv(DATA / "monthly.csv")
weekly = pd.read_csv(DATA / "weekly.csv")
daily = pd.read_csv(DATA / "daily.csv").tail(DAILY_DAYS)

monthly_rows = [
    {"label": datetime.date.fromisoformat(m + "-01").strftime("%b %Y"), "users": int(u)}
    for m, u in zip(monthly["month"], monthly["users"])
]
weekly_rows = [
    {"label": datetime.date.fromisoformat(w).strftime("%b %-d"), "users": int(u)}
    for w, u in zip(weekly["week_start"], weekly["users"])
]
daily_rows = [
    {"label": datetime.date.fromisoformat(d).strftime("%b %-d"), "users": int(u)}
    for d, u in zip(daily["date"], daily["users"])
]

summary = [
    {
        "label": "Institutions",
        "value": institutions,
        "detail": f"more than {INSTITUTION_THRESHOLD} users in AY {ay}–{str(ay + 1)[2:]} · {len(sem)} hubs",
    },
    {
        "label": f"Users, {term_label(current)}" if current else "Users this term",
        "value": int(sem[current].sum()) if current else 0,
        "detail": "active this term, all hubs",
    },
    {
        "label": "Monthly active users",
        "value": monthly_rows[-1]["users"] if monthly_rows else 0,
        "detail": monthly_rows[-1]["label"] if monthly_rows else "",
    },
]

updated = datetime.datetime.now(PT).strftime("%Y-%m-%d %H:%M %Z")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Cal-ICOR Hub Users</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #f5f5f5; color: #222; padding: 2rem; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
    .updated {{ color: #888; font-size: 0.85rem; margin-bottom: 2rem; }}
    .card {{ background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    h2 {{ font-size: 1.1rem; margin-bottom: 0.25rem; }}
    .sub {{ color: #888; font-size: 0.85rem; margin-bottom: 1rem; }}
    canvas {{ max-height: 320px; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
    .summary-card {{ background: #fff; border-radius: 8px; padding: 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    .summary-label {{ color: #666; font-size: 0.85rem; margin-bottom: 0.5rem; }}
    .summary-value {{ font-size: 1.8rem; font-weight: 700; line-height: 1.1; }}
    .summary-detail {{ color: #888; font-size: 0.8rem; margin-top: 0.35rem; }}
    @media (max-width: 600px) {{ body {{ padding: 1rem; }} }}
  </style>
</head>
<body>
  <h1>Cal-ICOR Hub Users</h1>
  <p class="updated">Last updated: {updated}</p>

  <div class="summary-grid" id="summary-grid"></div>

  <div class="card">
    <h2>Active Users by Semester</h2>
    <p class="sub">Users active on a Cal-ICOR hub during each term.</p>
    <canvas id="semesterChart"></canvas>
  </div>

  <div class="card">
    <h2>Monthly Active Users</h2>
    <p class="sub">Users active in the 30 days to the end of each month, all production hubs.</p>
    <canvas id="monthlyChart"></canvas>
  </div>

  <div class="card">
    <h2>Weekly Active Users</h2>
    <p class="sub">Users active each week (Monday to Sunday), all production hubs.</p>
    <canvas id="weeklyChart"></canvas>
  </div>

  <div class="card">
    <h2>Daily Active Users</h2>
    <p class="sub">Users active each day, last {DAILY_DAYS} days, all production hubs.</p>
    <canvas id="dailyChart"></canvas>
  </div>

  <script>
    const summaries = {json.dumps(summary)};
    const series = {{
      semesterChart: {json.dumps(semesters)},
      monthlyChart:  {json.dumps(monthly_rows)},
      weeklyChart:   {json.dumps(weekly_rows)},
      dailyChart:    {json.dumps(daily_rows)},
    }};

    document.getElementById("summary-grid").innerHTML = summaries.map(item => `
      <div class="summary-card">
        <div class="summary-label">${{item.label}}</div>
        <div class="summary-value">${{Number(item.value).toLocaleString()}}</div>
        <div class="summary-detail">${{item.detail}}</div>
      </div>
    `).join("");

    for (const [id, rows] of Object.entries(series)) {{
      new Chart(document.getElementById(id), {{
        type: "bar",
        data: {{
          labels: rows.map(r => r.label),
          datasets: [{{ label: "Active users", data: rows.map(r => r.users), backgroundColor: "#f28e2b" }}],
        }},
        options: {{
          responsive: true,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{ y: {{ beginAtZero: true, ticks: {{ precision: 0 }} }} }},
        }},
      }});
    }}
  </script>
</body>
</html>
"""

(BASE / "docs").mkdir(exist_ok=True)
(BASE / "docs" / "index.html").write_text(html, encoding="utf-8")
print(f"  docs/index.html written ({len(html):,} bytes)")
