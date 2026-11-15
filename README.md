# EventSphere

This project is created as a role-based event & venue booking digital platform built with FastAPI and a browser based frontend

## Features

- Roled based authentication(Attendee, Admin & the Staff)
- Event & Venue management once at a particular time
- Ticket booking with availability checks, QR tickets, and booking history.
- QR ticket scanning and check-in for gate staff.
- Live database server

## Requirements

- Python 3.10 or later.
- pip.
- SQLite for the default local setup, or PostgreSQL if you configure a PostgreSQL database.

## Run locally

From the repository root, create and activate a virtual environment, then install the dependencies.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file in the repository root and set a secret key. Generate a suitable value with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Sample `.env`:

```dotenv
SECRET_KEY=replace_with_a_generated_secret_at_least_32_characters_long
# DATABASE_URL="Database_URL_Here"
# ALGORITHM=""
# ACCESS_TOKEN_EXPIRE_MINUTES=""
```

Start the application:

```bash
python -m uvicorn main:app --reload
```

Open:

- App: <http://127.0.0.1:8000/>
- Documentation: <http://127.0.0.1:8000/docs>
- API status: <http://127.0.0.1:8000/api-status>

On first startup, the application creates the database tables. With no database URL configured, it uses the local SQLite file `eventsphere.db`.

## Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Secret used to sign authentication tokens. Must be at least 32 characters. |
| `SQLALCHEMY_DATABASE_URL` | No | Database URL. If set, this takes precedence over `DATABASE_URL`. |
| `DATABASE_URL` | No | Database URL used when `SQLALCHEMY_DATABASE_URL` is not set. Defaults to `sqlite:///./eventsphere.db`. |
| `ALGORITHM` | No | Token-signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Token lifetime in minutes. |


## Accounts and demo credentials

The repository does not include seeded demo accounts or default passwords.

To create the first local admin/organiser account, make sure your `.env` is configured and run this from the repository root:

```bash
python bootstrap_admin.py
```

The script prompts for the account details and password; it does not print or store a default password. It only creates an admin if one does not already exist. After signing in as admin, create gate-staff accounts from the organiser interface. Attendees can register through the app.

## Tests and verification

For a manual test:

1. Start the app and confirm `/api-status` responds and `/docs` loads.
2. Create an admin with `bootstrap_admin.py`, then sign in through the app.
3. Create a venue and a published event with a ticket category.
4. Register an attendee, book a ticket, and confirm the booking and QR ticket appear.
5. Confirm the available ticket count decreases after booking.
6. Create a staff account, scan the ticket, and confirm it is marked as checked in.

