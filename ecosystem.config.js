module.exports = {
  apps: [
    {
      name: 'familybot-api',
      script: 'main.py',
      interpreter: 'python',
      interpreter_args: '-m uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '.'
      },
      env_production: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '.'
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: 'logs/pm2-api-error.log',
      out_file: 'logs/pm2-api-out.log',
      pid_file: 'logs/pm2-api.pid',
      merge_logs: true,
      kill_timeout: 5000,
      wait_ready: true,
      listen_timeout: 10000
    },
    {
      name: 'familybot-bot',
      script: 'bot_polling.py',
      interpreter: 'python',
      cwd: './',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '.'
      },
      env_production: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '.'
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: 'logs/pm2-bot-error.log',
      out_file: 'logs/pm2-bot-out.log',
      pid_file: 'logs/pm2-bot.pid',
      merge_logs: true,
      kill_timeout: 5000,
      wait_ready: true,
      listen_timeout: 10000
    }
  ],

  deploy: {
    production: {
      user: 'ubuntu',
      host: 'your-server-ip',
      ref: 'origin/main',
      repo: 'git@github.com:yourusername/familybot.git',
      path: '/var/www/familybot',
      'post-deploy': `
        cp .env.example .env &&
        python -m pip install --upgrade pip &&
        pip install -r requirements.txt &&
        python migrate.py &&
        pm2 reload ecosystem.config.js --env production
      `,
      env: {
        NODE_ENV: 'production'
      }
    }
  }
};