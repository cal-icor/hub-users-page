"""Fetch Cal-ICOR hub usage into data/.

Two sources:

  users.csv    per-term active users for every pilot hub, written nightly by
               sean-morris/cloudbank-pilot-hub-users. Only the `icor` rows are
               kept, as data/semesters.csv.

  Prometheus   jupyterhub_active_users from the Cal-ICOR cluster, read through
               Grafana with a Viewer service-account token (GRAFANA_TOKEN).
               JupyterHub reports, at each moment, how many users were active
               in the trailing 24h / 7d / 30d. Sampling those at the end of
               each day / week / month gives real daily, weekly and monthly
               active users, summed over the production hubs.

Each run upserts into the CSVs, so history outlives Prometheus retention.
"""

import datetime
import io
import os
import sys
import zoneinfo
from pathlib import Path

import pandas as pd
import requests

PT = zoneinfo.ZoneInfo("America/Los_Angeles")
DATA = Path(__file__).parent / "data"
USERS_CSV = "https://raw.githubusercontent.com/sean-morris/cloudbank-pilot-hub-users/main/users.csv"
GRAFANA = "https://grafana.jupyter.cal-icor.org"
DATASOURCE = "P1809F7CD0C75ACF3"  # the cluster's Prometheus, as Grafana names it
QUERY = 'sum(jupyterhub_active_users{{namespace=~".*-prod", period="{period}"}})'
HISTORY_START = datetime.date(2026, 3, 9)  # first day the cluster's Prometheus has data


def upsert(name, df, key):
    path = DATA / name
    if path.is_file():
        df = pd.concat([pd.read_csv(path), df]).drop_duplicates(subset=key, keep="last")
    df.sort_values(key).to_csv(path, index=False)
    print(f"  {name}: {len(df)} rows")


def semesters():
    resp = requests.get(USERS_CSV, timeout=60)
    resp.raise_for_status()
    users = pd.read_csv(io.StringIO(resp.text))
    icor = users[(users["where"] == "icor") & ~users["college"].astype(str).str.startswith("Total")]
    icor.drop(columns=["where"]).to_csv(DATA / "semesters.csv", index=False)
    print(f"  semesters.csv: {len(icor)} hubs")


def active_users(period, ends):
    """{date: users} sampling the trailing-`period` count at 23:59 PT of each date."""
    token = os.environ.get("GRAFANA_TOKEN")
    if not token:
        sys.exit("GRAFANA_TOKEN is not set")
    url = f"{GRAFANA}/api/datasources/proxy/uid/{DATASOURCE}/api/v1/query"
    out = {}
    for day in ends:
        at = datetime.datetime.combine(day, datetime.time(23, 59), PT).timestamp()
        resp = requests.get(
            url,
            params={"query": QUERY.format(period=period), "time": at},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()["data"]["result"]
        if result:
            out[day] = int(float(result[0]["value"][1]))
    return out


def main():
    DATA.mkdir(exist_ok=True)
    semesters()

    today = datetime.datetime.now(PT).date()
    yesterday = today - datetime.timedelta(days=1)
    start = HISTORY_START

    days = [start + datetime.timedelta(days=i) for i in range((yesterday - start).days + 1)]
    sundays = [d for d in days if d.weekday() == 6]
    month_ends = [d for d in days if (d + datetime.timedelta(days=1)).day == 1]

    daily = active_users("24h", days)
    upsert("daily.csv", pd.DataFrame({"date": [str(d) for d in daily], "users": list(daily.values())}), "date")

    weekly = active_users("7d", sundays)
    upsert("weekly.csv", pd.DataFrame({
        "week_start": [str(d - datetime.timedelta(days=6)) for d in weekly],
        "users": list(weekly.values()),
    }), "week_start")

    monthly = active_users("30d", month_ends)
    upsert("monthly.csv", pd.DataFrame({
        "month": [d.strftime("%Y-%m") for d in monthly],
        "users": list(monthly.values()),
    }), "month")


if __name__ == "__main__":
    main()
