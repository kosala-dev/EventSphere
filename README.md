# EventSphere

A Agent Based web app for booking events and venues, with QR code tickets. I built this project using FastAPI as a project for my IT degree at the University of Vavuniya.

People can browse events and book tickets. Organisers create venues and events, and gate staff scan the QR tickets at the entrance.

## Live demo

**Link:** https://eventsphere-2y9h.onrender.com/

The free Render plan sleeps when nobody uses it, so the first load can take about 30 seconds.

**Demo admin account** (made only for this demo, no real data):

| Username | Password |
| -------- | -------- |
| agentadmin | agentadmin123 |

Please don't delete the demo events. The data may get reset from time to time.

## Screenshots

<img width="1888" height="904" alt="home" src="https://github.com/user-attachments/assets/878fe165-fecc-4d52-952f-e6be8ccb37c9" />

<img width="1881" height="904" alt="ticket" src="https://github.com/user-attachments/assets/ff681059-b892-4c06-8d38-167e3e66a2ff" />

<img width="1894" height="910" alt="staff" src="https://github.com/user-attachments/assets/7f8e9268-4803-462d-ab1c-292d0e1e33f0" />


## What it does

- Three kinds of users: attendees, admins (organisers) and gate staff, each with their own access.
- Admins create venues and events, and an event can't be booked into a venue at a time that is already taken.
- Attendees register, book tickets and see their booking history.
- Booking checks how many tickets are left, so an event can't be oversold.
- Every booking gets a QR ticket.
- Gate staff scan the QR ticket and the ticket is marked as checked in.

## Built with

- Python and FastAPI
- SQLite for local use, PostgreSQL
- A browser-based frontend served from the `static` folder
- Deployed on Render

## Run it on your machine

You need Python 3.10 or newer.

1. Clone the repo and open the folder.

2. Create a virtual environment and install the packages.

   Windows (PowerShell):

   ```
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   macOS or Linux:

   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Make a `.env` file in the project folder with a secret key:

   ```
   SECRET_KEY=your_long_random_key_here
   ```

   You can generate one with:

   ```
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

4. Start the app:

   ```
   python -m uvicorn main:app --reload
   ```

5. Open http://127.0.0.1:8000/ for the app, or http://127.0.0.1:8000/docs for the API docs.

On the first run the tables are created automatically. If you don't set a database URL, it uses a local SQLite file called `eventsphere.db`.

## Settings (.env)

| Variable | Required | What it does |
| -------- | -------- | ------------ |
| `SECRET_KEY` | Yes | Used to sign login tokens. At least 32 characters. |
| `DATABASE_URL` | No | Database to use. Defaults to a local SQLite file. |
| `SQLALCHEMY_DATABASE_URL` | No | Same as above. If both are set, this one wins. |
| `ALGORITHM` | No | Token signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | How long a login lasts. |

## Making the first admin

There are no default accounts. After setting up your `.env`, run:

```
python bootstrap_admin.py
```

It asks for a username and password and creates the first admin. It only works if there is no admin yet. Then sign in as the admin and create accounts for gate staff. Attendees can sign up on their own.

## Trying it out by hand

I haven't written automated tests yet, so I check it like this:

1. Start the app and make sure `/docs` loads.
2. Create an admin and sign in.
3. Add a venue, then a published event with a ticket category.
4. Register as an attendee and book a ticket. The booking and QR ticket should show up.
5. Check that the number of available tickets went down.
6. Make a staff account, scan the ticket, and check it shows as checked in.

## Project layout

```
main.py             app entry point
routers/            API routes
agents/             [add one line on what this folder does]
static/             frontend files
models.py           database tables
schemas.py          request and response shapes
security.py         login and token code
database.py         database connection
config.py           settings
dependencies.py     shared route dependencies
bootstrap_admin.py  script to create the first admin
```

## What I'd like to add next

- Automated tests
- Email Notifications
- Live payment gateway rather than a simulated one

## License

MIT. See the `LICENSE` file.
