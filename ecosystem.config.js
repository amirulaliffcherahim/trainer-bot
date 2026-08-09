// PM2 deployment config — trainer-bot (Python).
//
// Start:        pm2 start ecosystem.config.js
// Persist:      pm2 save && pm2 startup
// Logs:         pm2 logs trainer-bot
// Note: secrets come from .env (bot.py loads it via python-dotenv); never
// put keys in this file.

module.exports = {
  apps: [
    {
      name: "trainer-bot",
      script: "bot.py",
      // Use the project venv interpreter on the deploy host.
      // Windows: .venv/Scripts/python.exe  |  Linux: .venv/bin/python
      interpreter: process.env.TRAINER_BOT_PYTHON || ".venv/bin/python",
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
