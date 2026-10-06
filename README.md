# hub-users-page

Cal-ICOR hub usage, published nightly to GitHub Pages from `docs/`.

- `fetch.py` pulls per-term users for the ICOR hubs from
  [cloudbank-pilot-hub-users](https://github.com/sean-morris/cloudbank-pilot-hub-users)
  `users.csv`, and daily / weekly / monthly active users from the Cal-ICOR
  Prometheus through Grafana (`GRAFANA_TOKEN`, a Viewer service account).
- `build_page.py` renders `docs/index.html` from `data/`.

```
GRAFANA_TOKEN=... python fetch.py
python build_page.py
```
