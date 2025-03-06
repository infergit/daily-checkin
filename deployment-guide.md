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

For a more robust production setup, consider:
- Using a reverse proxy like Nginx
- Setting up SSL/TLS for HTTPS
- Using environment variables for sensitive configuration (SECRET_KEY, etc.)
- Setting DEBUG=False in production

## Customization

- Application configuration can be modified in `config.py`
- Static files (CSS, JavaScript) are located in `app/static/`
- HTML templates are in `app/templates/`

## Backup

To backup your SQLite database, simply copy the `app.db` file which will be created in the project root directory.
