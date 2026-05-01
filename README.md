# snickr Project 2

This directory contains the Project 1 PostgreSQL schema and sample data plus a
Project 2 Flask web interface.

## Files

- `schema.sql`: PostgreSQL schema.
- `sample_data.sql`: demo data for users, workspaces, channels, invitations, and messages.
- `queries.sql`: Project 1 required SQL queries.
- `app.py`: Project 2 web application.
- `templates/`: server-rendered HTML templates.
- `static/style.css`: application styling.
- `snickr_part2_report.tex`: combined Project 1 and Project 2 documentation.

## Setup

Create a PostgreSQL database named `snickr`, then install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

The project includes a `.env` file and PowerShell scripts for this local
database account:

```powershell
$env:DATABASE_URL="postgresql://postgres:csh1q2w3e4r@localhost:5432/snickr"
```

Initialize the database from the existing SQL files:

```powershell
.\init_db.ps1
```

Running the initializer more than once will not rebuild existing tables. To
drop and reload the sample data on purpose, run:

```powershell
.\reset_db.ps1
```

Run the web app:

```powershell
.\start.ps1
```

If an old Flask process is still using port 5000, stop it first:

```powershell
.\stop_server.ps1
.\start.ps1
```

Open `http://127.0.0.1:5000`.

## Demo Accounts

The sample data uses legacy placeholder passwords so the demo can use:

- username `alice`, password `hash_alice`
- username `bob`, password `hash_bob`
- username `cara`, password `hash_cara`
- username `maya`, password `hash_maya`

Newly registered accounts store Werkzeug password hashes.

## Demo Checklist

1. Log in as `alice`.
2. Open Acme Lab and create a public channel.
3. Post a message in a joined channel.
4. Invite a user to a workspace or channel.
5. Log in as the invited user and accept or decline the invitation.
6. Search for `perpendicular` as `cara`; the private hiring-channel message is hidden.
