# Daily Check-in Application Deployment Guide

This guide explains how to set up, initialize, and run the Daily Check-in application.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. **Clone or download the project**

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Database Initialization

Before running the application, you need to initialize the database:

```bash
python scripts/init_db.py
```

If you want to create a demo user for testing, run:

```bash
python scripts/init_db.py --with-demo-data
```

This will create a user with:
- Username: demo
- Password: password123

## Running the Application

To start the application in development mode:

```bash
python run.py
```

The application will be available at `http://127.0.0.1:5000/`

## Production Deployment

For production deployment, it's recommended to use a proper WSGI server such as Gunicorn:

1. **Install Gunicorn**
   ```bash
   pip install gunicorn
   ```

2. **Run with Gunicorn**
   ```bash
   gunicorn -w 4 "app:create_app()"
   ```

### Nginx Setup

1. **Install Nginx**
   ```bash
   # On macOS with Homebrew
   brew install nginx
   
   # On Ubuntu/Debian
   sudo apt update
   sudo apt install nginx
   ```

2. **Create Nginx Configuration**
   
   Create a new configuration file:
   ```bash
   # On macOS
   sudo nano /usr/local/etc/nginx/servers/daily-checkin.conf
   
   # On Ubuntu/Debian
   sudo nano /etc/nginx/sites-available/daily-checkin
   ```

   Add the following configuration:
   ```nginx
   server {
       listen 80;
       server_name your_domain.com;  # Replace with your domain or IP
       
       access_log /var/log/nginx/daily-checkin.access.log;
       error_log /var/log/nginx/daily-checkin.error.log;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /static {
           alias /path/to/your/daily-checkin/app/static;  # Replace with actual path
           expires 30d;
       }
   }
   ```

3. **Enable the Configuration**
   ```bash
   # On macOS
   sudo nginx -t
   sudo brew services restart nginx
   
   # On Ubuntu/Debian
   sudo ln -s /etc/nginx/sites-available/daily-checkin /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

4. **Run Gunicorn Behind Nginx**
   ```bash
   gunicorn -w 4 -b 127.0.0.1:8000 "app:create_app()"
   ```

5. **Set Up Systemd Service (Linux only)**
   
   Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/daily-checkin.service
   ```

   Add the following content:
   ```ini
   [Unit]
   Description=Daily Check-in Gunicorn daemon
   After=network.target

   [Service]
   User=your_user  # Replace with your username
   Group=your_group  # Replace with your group
   WorkingDirectory=/path/to/daily-checkin
   Environment="PATH=/path/to/daily-checkin/venv/bin"
   ExecStart=/path/to/daily-checkin/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 "app:create_app()"

   [Install]
   WantedBy=multi-user.target
   ```

   Enable and start the service:
   ```bash
   sudo systemctl enable daily-checkin
   sudo systemctl start daily-checkin
   ```

### Setting up HTTPS with Let's Encrypt

1. **Install Certbot**
   ```bash
   # On Ubuntu/Debian
   sudo apt install certbot python3-certbot-nginx

   # On macOS
   brew install certbot
   ```

2. **Obtain SSL Certificate**
   ```bash
   # On Ubuntu/Debian with Nginx
   sudo certbot --nginx -d yourdomain.com

   # On macOS
   sudo certbot --nginx -d yourdomain.com
   ```

3. **Update Nginx Configuration**
   
   Your Nginx configuration will be automatically updated, but it should look similar to this:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;
       return 301 https://$server_name$request_uri;  # Redirect HTTP to HTTPS
   }

   server {
       listen 443 ssl;
       server_name yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
       
       # Modern SSL configuration
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_prefer_server_ciphers off;

       # HSTS (uncomment if you're sure)
       # add_header Strict-Transport-Security "max-age=63072000" always;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /static {
           alias /path/to/your/daily-checkin/app/static;
           expires 30d;
       }
   }
   ```

4. **Auto-renewal Setup**
   ```bash
   # Test auto-renewal
   sudo certbot renew --dry-run

   # On Ubuntu/Debian, renewal is automatically configured
   # On macOS, add to crontab:
   echo "0 0,12 * * * root python -c 'import random; import time; time.sleep(random.random() * 3600)' && certbot renew -q" | sudo tee -a /etc/crontab > /dev/null
   ```

5. **Verify HTTPS Setup**
   - Visit https://yourdomain.com
   - Test SSL configuration at https://www.ssllabs.com/ssltest/

### Security Considerations

1. **Configure Flask for HTTPS**
   Update your config.py:
   ```python
   class ProductionConfig(Config):
       SESSION_COOKIE_SECURE = True
       REMEMBER_COOKIE_SECURE = True
       SESSION_COOKIE_HTTPONLY = True
   ```

2. **Enable HSTS** (HTTP Strict Transport Security)
   Uncomment the HSTS header in Nginx config after confirming everything works.

3. **Regular Updates**
   ```bash
   # Update system packages
   sudo apt update && sudo apt upgrade
   
   # Update certbot
   sudo certbot update
   ```

Note: Make sure your domain's DNS records are properly configured before obtaining SSL certificates.

Now your application should be accessible through Nginx on port 80. For additional security:
- Consider setting up SSL/TLS with Let's Encrypt
- Configure firewall rules
- Set appropriate file permissions
- Regular security updates

## Customization

- Application configuration can be modified in `config.py`
- Static files (CSS, JavaScript) are located in `app/static/`
- HTML templates are in `app/templates/`

## Backup

To backup your SQLite database, simply copy the `app.db` file which will be created in the project root directory.
