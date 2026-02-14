# Billing System

Simple billing application with:
- Product Master
- Customer Master
- Denomination Master
- Invoice transactions
- Previous purchase history (filters by customer name/email/date range)
- Asynchronous invoice email queue using Celery + Redis

## Prerequisites
- Python 3.13+
- PostgreSQL running locally
- Redis-compatible broker for Celery (Redis or Memurai on Windows)

## Setup
1. Create and activate virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\activate
```

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

3. Configure environment variables:
- Copy `.env.example` to `.env`
- Update email credentials and broker URL

4. Update database settings in `Billing_System/settings.py` if needed:
- `NAME`
- `USER`
- `PASSWORD`
- `HOST`
- `PORT`

5. Run migrations:
```powershell
.\venv\Scripts\python manage.py migrate
```

## Run the project
1. Start Django server:
```powershell
.\venv\Scripts\python manage.py runserver
```

2. Start Celery worker in another terminal:
```powershell
.\venv\Scripts\python -m celery -A Billing_System worker -l info --pool=solo --concurrency=1
```

## For Start Redis Service Memurai
sc start Memurai

## For Checking Redis Service Memurai
netstat -ano | findstr :6379

Why `--pool=solo`:
- On Windows, Celery multiprocessing pools can cause permission/lock issues (`WinError 5`).
- `--pool=solo` is stable and recommended for local Windows execution.

3. Ensure Redis broker is running on configured URL:
- Default: `redis://127.0.0.1:6379/0`

## Default data
- Migration seeds default denominations:
  - `500, 200, 100, 50, 20, 10, 5, 2, 1`

## Email behavior
- Invoice submission queues an async email task after transaction commit.
- Success updates:
  - `EMAILSENT=True`
- Failures are tracked:
  - `EMAILFAILCOUNT`
  - `EMAILLASTERROR`

If Redis is unavailable:
- Invoice still saves.
- Queue failure is tracked in invoice fields.

## Running tests
```powershell
.\venv\Scripts\python manage.py test
```

## Assumptions
- `ROUNDEDPAYABLE` is rounded down (`ROUND_DOWN`).
- Change denomination is generated using highest-to-lowest denomination order.
- If customer email is new during invoice creation, customer is auto-created in master.



