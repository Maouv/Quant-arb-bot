// PM2 process config for quant-arb-bot Phase 4 (paper trading)
// Run:   pm2 start ecosystem.config.js
// Stop:  pm2 stop all
// Logs:  pm2 logs
// Status: pm2 status

module.exports = {
  apps: [
    {
      name: "trading-bot",
      script: ".venv/bin/python3",
      args: "-m src.bot.main",
      cwd: "/root/quant-arb-bot",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 5,
      restart_delay: 10000,
      min_uptime: 30000,
      env: {
        PYTHONPATH: "/root/quant-arb-bot",
        PYTHONUNBUFFERED: "1",
      },
      log_file: "logs/pm2-trading-bot.log",
      error_file: "logs/pm2-trading-bot-error.log",
      merge_logs: true,
      time: true,
    },
    {
      name: "discord-bot",
      script: ".venv/bin/python3",
      args: "-m src.discord_ui",
      cwd: "/root/quant-arb-bot",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 5,
      restart_delay: 10000,
      min_uptime: 30000,
      env: {
        PYTHONPATH: "/root/quant-arb-bot",
        PYTHONUNBUFFERED: "1",
      },
      log_file: "logs/pm2-discord-bot.log",
      error_file: "logs/pm2-discord-bot-error.log",
      merge_logs: true,
      time: true,
    },
  ],
};
