// PM2 deployment config — trainer-bot (Python).
//
// Start:        pm2 start ecosystem.config.js
// Persist:      pm2 save && pm2 startup
// Logs:         pm2 logs trainer-bot
// Note: secrets come from .env (bot.py loads it via python-dotenv); never
// put keys in this file.

const fs = require("fs");
const path = require("path");

// Interpreter resolution, in priority order:
// 1. TRAINER_BOT_PYTHON env override
// 2. project venv (absolute path — pm2 cannot run a RELATIVE interpreter,
//    ".venv/bin/python" fails with "NOT AVAILABLE in PATH")
// 3. system python3 (no-venv setups)
const venvPython =
  process.platform === "win32"
    ? path.join(__dirname, ".venv", "Scripts", "python.exe")
    : path.join(__dirname, ".venv", "bin", "python");

const interpreter =
  process.env.TRAINER_BOT_PYTHON ||
  (fs.existsSync(venvPython) ? venvPython : "python3");

module.exports = {
  apps: [
    {
      name: "trainer-bot",
      script: "bot.py",
      interpreter: interpreter,
      cwd: __dirname,
      env: {
        PYTHONUNBUFFERED: "1",
      },
      log_file: "logs/pm2.log",
      out_file: "logs/pm2-out.log",
      error_file: "logs/pm2-error.log",
      max_restarts: 10,
      restart_delay: 5000,
      time: true,
      autorestart: true,
    },
  ],
};
