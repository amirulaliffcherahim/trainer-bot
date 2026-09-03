# Deploy runbook — trainer-bot (server: Fedora 44)

Server: `yuki@100.109.19.100` (Tailscale), Fedora 44, Node 22.23.1
(node:sqlite OK). App dir: `~/trainer-bot`, managed by pm2 as `trainer-bot`.

## Topology
- App listens on **port 4040** (localhost only — no firewalld change made).
- Public exposure: **Cloudflare Tunnel** (user's choice). cloudflared maps a
  domain → `http://localhost:4040`. No inbound port needed.
- Strava OAuth callback domain must equal the tunnel domain (see below).

## pm2 apps on this server (2026-09)
| name | port | dir | notes |
|---|---|---|---|
| trainer-bot | 4040 | ~/trainer-bot | SvelteKit app; runbook above |
| portfolio | 3000 | ~/code/Portfolio_Website | started via `pm2 start server.js --name portfolio` (its own ecosystem.config.js is ESM and pm2 can't parse it) |
| ocr-pipeline | 8001 | ~/code/ocr-pipeline | FastAPI; venv at .venv; started `pm2 start ./.venv/bin/uvicorn --name ocr-pipeline --interpreter none -- api:app --host 0.0.0.0 --port 8001` |
| OmniRoute | — | ~/code/OmniRoute | **deliberately not started / not in dump** |

- pm2 startup enabled: systemd unit `pm2-yuki` — resurrects the saved dump on boot.
  `pm2 save` currently stores trainer-bot + portfolio + ocr-pipeline (OmniRoute excluded).

## Deploy a new build
```bash
# local (repo root): build once, package, upload
npm run build
tar czf /tmp/tb-build.tgz build package.json
scp /tmp/tb-build.tgz yuki@100.109.19.100:trainer-bot/

# server:
cd ~/trainer-bot && tar xzf build.tgz && rm build.tgz
pm2 restart trainer-bot --update-env && pm2 save
```

## pm2 / env
- Config: `~/trainer-bot/ecosystem.config.cjs` (chmod 600).
- Env vars live there: `PORT=4040`, `APP_BASE_URL`,
  `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `DB_PATH=trainer.db`.
- Commands: `pm2 logs trainer-bot`, `pm2 restart trainer-bot`,
  `pm2 status`, `pm2 save` (already saved — restore on reboot needs
  `pm2 startup` + sudo, not yet enabled).
- DB: `~/trainer-bot/trainer.db` (SQLite; stop app before manual backup,
  or copy with WAL files together).

## Go-live checklist (Cloudflare)
1. Tunnel running: domain → `http://localhost:4040`.
2. `APP_BASE_URL=https://<domain>` in ecosystem.config.cjs →
   `pm2 restart trainer-bot --update-env`.
3. strava.com/settings/api → Authorization Callback Domain = `<domain>`.
4. Fill `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` in ecosystem.config.cjs →
   `pm2 restart trainer-bot --update-env`.
5. Open app in a mobile browser → Connect with Strava → Sync.

## Verify
```bash
curl -s http://localhost:4040/api/status   # on server or via ssh
```

## Git-based deploy (current, 2026-09)
- Local: commit → `git push origin main`.
- Server: `cd ~/trainer-src && git pull && npm ci && npm run build && pm2 restart trainer-bot`.
- `~/trainer-src` = repo checkout (build output inside); DB lives at the
  absolute path `/home/yuki/trainer-bot/trainer.db` (data dir kept separate
  from source); env lives in `~/trainer-src/ecosystem.config.cjs` (chmod 600).
