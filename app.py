import os
from functools import wraps

import click
import psycopg2
import psycopg2.extras
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)


def load_env_file(filename=".env"):
    if not os.path.exists(filename):
        return
    with open(filename, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


load_env_file()

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:csh1q2w3e4r@localhost:5432/snickr"
)


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            app.config["DATABASE_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = query_one(
            "SELECT user_id, email, username, nickname FROM users WHERE user_id = %s",
            (user_id,),
        )


def database_has_schema():
    row = query_one("SELECT to_regclass('public.users') AS users_table")
    return row and row["users_table"] is not None


@app.cli.command("init-db")
@click.option("--reset", is_flag=True, help="Drop and recreate existing tables.")
def init_db_command(reset):
    db = get_db()
    if database_has_schema() and not reset:
        click.echo(
            "Database already has snickr tables. Nothing changed. "
            "Run `flask --app app init-db --reset` if you want to rebuild sample data."
        )
        return
    with db, db.cursor() as cur:
        for filename in ("schema.sql", "sample_data.sql"):
            with open(filename, encoding="utf-8") as f:
                cur.execute(f.read())
    click.echo("Initialized the snickr database with schema.sql and sample_data.sql.")


def verify_password(stored_hash, password):
    if stored_hash.startswith(("scrypt:", "pbkdf2:", "argon2:")):
        return check_password_hash(stored_hash, password)
    return stored_hash == password


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        username = request.form["username"].strip()
        nickname = request.form["nickname"].strip()
        password = request.form["password"]
        if not email or not username or not nickname or not password:
            flash("All fields are required.", "error")
        else:
            try:
                with get_db(), get_db().cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users(email, username, nickname, password_hash)
                        VALUES (%s, %s, %s, %s)
                        RETURNING user_id
                        """,
                        (email, username, nickname, generate_password_hash(password)),
                    )
                    user = cur.fetchone()
                session.clear()
                session["user_id"] = user["user_id"]
                flash("Your account is ready.", "success")
                return redirect(url_for("dashboard"))
            except psycopg2.IntegrityError:
                get_db().rollback()
                flash("That email or username is already in use.", "error")
    return render_template("register.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = query_one(
            """
            SELECT user_id, username, nickname, password_hash
            FROM users
            WHERE username = %s OR email = %s
            """,
            (username, username.lower()),
        )
        if user and verify_password(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["user_id"]
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid username/email or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard", methods=("GET", "POST"))
@login_required
def dashboard():
    if request.method == "POST":
        name = request.form["name"].strip()
        description = request.form["description"].strip()
        if not name:
            flash("Workspace name is required.", "error")
        else:
            try:
                with get_db(), get_db().cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO workspaces(name, description, created_by)
                        VALUES (%s, %s, %s)
                        RETURNING workspace_id
                        """,
                        (name, description, g.user["user_id"]),
                    )
                    workspace = cur.fetchone()
                    cur.execute(
                        """
                        INSERT INTO workspace_members(workspace_id, user_id, role)
                        VALUES (%s, %s, 'admin')
                        """,
                        (workspace["workspace_id"], g.user["user_id"]),
                    )
                flash("Workspace created.", "success")
                return redirect(url_for("workspace", workspace_id=workspace["workspace_id"]))
            except psycopg2.IntegrityError:
                get_db().rollback()
                flash("A workspace with that name already exists.", "error")

    workspaces = query_all(
        """
        SELECT w.workspace_id, w.name, w.description, wm.role,
               COUNT(DISTINCT cm.channel_id) AS joined_channels
        FROM workspace_members AS wm
        JOIN workspaces AS w ON w.workspace_id = wm.workspace_id
        LEFT JOIN channels AS c ON c.workspace_id = w.workspace_id
        LEFT JOIN channel_members AS cm
          ON cm.channel_id = c.channel_id AND cm.user_id = wm.user_id
        WHERE wm.user_id = %s
        GROUP BY w.workspace_id, w.name, w.description, wm.role
        ORDER BY w.name
        """,
        (g.user["user_id"],),
    )
    workspace_invites = query_all(
        """
        SELECT wi.workspace_invitation_id, w.name AS workspace, u.username AS invited_by,
               wi.invited_at
        FROM workspace_invitations AS wi
        JOIN workspaces AS w ON w.workspace_id = wi.workspace_id
        JOIN users AS u ON u.user_id = wi.invited_by
        WHERE wi.status = 'pending'
          AND (wi.invited_user_id = %s OR lower(wi.invited_email) = lower(%s))
        ORDER BY wi.invited_at
        """,
        (g.user["user_id"], g.user["email"]),
    )
    channel_invites = query_all(
        """
        SELECT ci.channel_invitation_id, c.name AS channel, w.name AS workspace,
               u.username AS invited_by, ci.invited_at
        FROM channel_invitations AS ci
        JOIN channels AS c ON c.channel_id = ci.channel_id
        JOIN workspaces AS w ON w.workspace_id = c.workspace_id
        JOIN users AS u ON u.user_id = ci.invited_by
        WHERE ci.status = 'pending' AND ci.invited_user_id = %s
        ORDER BY ci.invited_at
        """,
        (g.user["user_id"],),
    )
    return render_template(
        "dashboard.html",
        workspaces=workspaces,
        workspace_invites=workspace_invites,
        channel_invites=channel_invites,
    )


def workspace_membership(workspace_id):
    return query_one(
        """
        SELECT role
        FROM workspace_members
        WHERE workspace_id = %s AND user_id = %s
        """,
        (workspace_id, g.user["user_id"]),
    )


@app.route("/workspaces/<int:workspace_id>", methods=("GET", "POST"))
@login_required
def workspace(workspace_id):
    membership = workspace_membership(workspace_id)
    if membership is None:
        flash("You are not a member of that workspace.", "error")
        return redirect(url_for("dashboard"))

    workspace_row = query_one(
        "SELECT workspace_id, name, description FROM workspaces WHERE workspace_id = %s",
        (workspace_id,),
    )
    if request.method == "POST":
        channel_name = request.form["channel_name"].strip()
        channel_type = request.form["channel_type"]
        invitees = [u.strip() for u in request.form.get("invitees", "").split(",") if u.strip()]
        if not channel_name:
            flash("Channel name is required.", "error")
        elif channel_type not in {"public", "private", "direct"}:
            flash("Invalid channel type.", "error")
        else:
            try:
                with get_db(), get_db().cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO channels(workspace_id, name, channel_type, created_by)
                        VALUES (%s, %s, %s, %s)
                        RETURNING channel_id
                        """,
                        (workspace_id, channel_name, channel_type, g.user["user_id"]),
                    )
                    channel = cur.fetchone()
                    cur.execute(
                        "INSERT INTO channel_members(channel_id, user_id) VALUES (%s, %s)",
                        (channel["channel_id"], g.user["user_id"]),
                    )
                    for username in invitees:
                        cur.execute(
                            """
                            INSERT INTO channel_invitations(channel_id, invited_user_id, invited_by)
                            SELECT %s, user_id, %s
                            FROM users
                            WHERE username = %s
                            ON CONFLICT (channel_id, invited_user_id) DO NOTHING
                            """,
                            (channel["channel_id"], g.user["user_id"], username),
                        )
                flash("Channel created.", "success")
                return redirect(url_for("channel", channel_id=channel["channel_id"]))
            except psycopg2.IntegrityError:
                get_db().rollback()
                flash("That channel name already exists in this workspace.", "error")

    channels = query_all(
        """
        SELECT c.channel_id, c.name, c.channel_type, c.created_at,
               COUNT(m.message_id) AS message_count
        FROM channels AS c
        JOIN channel_members AS cm
          ON cm.channel_id = c.channel_id AND cm.user_id = %s
        LEFT JOIN messages AS m ON m.channel_id = c.channel_id
        WHERE c.workspace_id = %s
        GROUP BY c.channel_id, c.name, c.channel_type, c.created_at
        ORDER BY c.channel_type, c.name
        """,
        (g.user["user_id"], workspace_id),
    )
    members = query_all(
        """
        SELECT u.username, u.nickname, wm.role
        FROM workspace_members AS wm
        JOIN users AS u ON u.user_id = wm.user_id
        WHERE wm.workspace_id = %s
        ORDER BY wm.role, u.username
        """,
        (workspace_id,),
    )
    return render_template(
        "workspace.html",
        workspace=workspace_row,
        membership=membership,
        channels=channels,
        members=members,
    )


@app.route("/workspaces/<int:workspace_id>/invite", methods=("POST",))
@login_required
def invite_workspace(workspace_id):
    membership = workspace_membership(workspace_id)
    if membership is None or membership["role"] != "admin":
        flash("Only workspace admins can invite workspace members.", "error")
        return redirect(url_for("workspace", workspace_id=workspace_id))
    email = request.form["email"].strip().lower()
    invitee = query_one("SELECT user_id FROM users WHERE lower(email) = lower(%s)", (email,))
    try:
        with get_db(), get_db().cursor() as cur:
            cur.execute(
                """
                INSERT INTO workspace_invitations(
                    workspace_id, invited_email, invited_user_id, invited_by
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (workspace_id, invited_email) DO NOTHING
                """,
                (
                    workspace_id,
                    email,
                    invitee["user_id"] if invitee else None,
                    g.user["user_id"],
                ),
            )
        flash("Workspace invitation recorded.", "success")
    except psycopg2.Error:
        get_db().rollback()
        flash("Could not create that invitation.", "error")
    return redirect(url_for("workspace", workspace_id=workspace_id))


@app.route("/workspace-invitations/<int:invitation_id>/<decision>", methods=("POST",))
@login_required
def respond_workspace_invitation(invitation_id, decision):
    if decision not in {"accepted", "declined"}:
        flash("Invalid invitation response.", "error")
        return redirect(url_for("dashboard"))
    invitation = query_one(
        """
        SELECT workspace_invitation_id, workspace_id
        FROM workspace_invitations
        WHERE workspace_invitation_id = %s
          AND status = 'pending'
          AND (invited_user_id = %s OR lower(invited_email) = lower(%s))
        """,
        (invitation_id, g.user["user_id"], g.user["email"]),
    )
    if invitation is None:
        flash("Invitation not found.", "error")
        return redirect(url_for("dashboard"))
    with get_db(), get_db().cursor() as cur:
        cur.execute(
            """
            UPDATE workspace_invitations
            SET status = %s, responded_at = CURRENT_TIMESTAMP
            WHERE workspace_invitation_id = %s
            """,
            (decision, invitation_id),
        )
        if decision == "accepted":
            cur.execute(
                """
                INSERT INTO workspace_members(workspace_id, user_id, role)
                VALUES (%s, %s, 'member')
                ON CONFLICT (workspace_id, user_id) DO NOTHING
                """,
                (invitation["workspace_id"], g.user["user_id"]),
            )
    flash("Invitation response saved.", "success")
    return redirect(url_for("dashboard"))


@app.route("/channels/<int:channel_id>", methods=("GET", "POST"))
@login_required
def channel(channel_id):
    channel_row = query_one(
        """
        SELECT c.channel_id, c.name, c.channel_type, c.workspace_id, w.name AS workspace
        FROM channels AS c
        JOIN workspaces AS w ON w.workspace_id = c.workspace_id
        JOIN channel_members AS cm
          ON cm.channel_id = c.channel_id AND cm.user_id = %s
        WHERE c.channel_id = %s
        """,
        (g.user["user_id"], channel_id),
    )
    if channel_row is None:
        flash("You are not a member of that channel.", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        body = request.form["body"].strip()
        if not body:
            flash("Message body cannot be blank.", "error")
        else:
            with get_db(), get_db().cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO messages(channel_id, sender_id, body)
                    VALUES (%s, %s, %s)
                    """,
                    (channel_id, g.user["user_id"], body),
                )
            flash("Message posted.", "success")
            return redirect(url_for("channel", channel_id=channel_id))
    messages = query_all(
        """
        SELECT m.message_id, m.body, m.posted_at, u.username, u.nickname
        FROM messages AS m
        JOIN users AS u ON u.user_id = m.sender_id
        WHERE m.channel_id = %s
        ORDER BY m.posted_at, m.message_id
        """,
        (channel_id,),
    )
    members = query_all(
        """
        SELECT u.username, u.nickname
        FROM channel_members AS cm
        JOIN users AS u ON u.user_id = cm.user_id
        WHERE cm.channel_id = %s
        ORDER BY u.username
        """,
        (channel_id,),
    )
    return render_template(
        "channel.html", channel=channel_row, messages=messages, members=members
    )


@app.route("/channels/<int:channel_id>/invite", methods=("POST",))
@login_required
def invite_channel(channel_id):
    channel_row = query_one(
        """
        SELECT c.channel_id, c.workspace_id
        FROM channels AS c
        JOIN channel_members AS cm
          ON cm.channel_id = c.channel_id AND cm.user_id = %s
        WHERE c.channel_id = %s
        """,
        (g.user["user_id"], channel_id),
    )
    if channel_row is None:
        flash("You must belong to a channel before inviting others.", "error")
        return redirect(url_for("dashboard"))
    username = request.form["username"].strip()
    invitee = query_one(
        """
        SELECT u.user_id
        FROM users AS u
        JOIN workspace_members AS wm ON wm.user_id = u.user_id
        WHERE u.username = %s AND wm.workspace_id = %s
        """,
        (username, channel_row["workspace_id"]),
    )
    if invitee is None:
        flash("That user is not a member of this workspace.", "error")
    else:
        with get_db(), get_db().cursor() as cur:
            cur.execute(
                """
                INSERT INTO channel_invitations(channel_id, invited_user_id, invited_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (channel_id, invited_user_id) DO NOTHING
                """,
                (channel_id, invitee["user_id"], g.user["user_id"]),
            )
        flash("Channel invitation recorded.", "success")
    return redirect(url_for("channel", channel_id=channel_id))


@app.route("/channel-invitations/<int:invitation_id>/<decision>", methods=("POST",))
@login_required
def respond_channel_invitation(invitation_id, decision):
    if decision not in {"accepted", "declined"}:
        flash("Invalid invitation response.", "error")
        return redirect(url_for("dashboard"))
    invitation = query_one(
        """
        SELECT ci.channel_invitation_id, ci.channel_id, c.workspace_id
        FROM channel_invitations AS ci
        JOIN channels AS c ON c.channel_id = ci.channel_id
        WHERE ci.channel_invitation_id = %s
          AND ci.status = 'pending'
          AND ci.invited_user_id = %s
        """,
        (invitation_id, g.user["user_id"]),
    )
    if invitation is None:
        flash("Invitation not found.", "error")
        return redirect(url_for("dashboard"))
    if decision == "accepted" and workspace_membership(invitation["workspace_id"]) is None:
        flash("Join the workspace before accepting that channel invitation.", "error")
        return redirect(url_for("dashboard"))
    with get_db(), get_db().cursor() as cur:
        cur.execute(
            """
            UPDATE channel_invitations
            SET status = %s, responded_at = CURRENT_TIMESTAMP
            WHERE channel_invitation_id = %s
            """,
            (decision, invitation_id),
        )
        if decision == "accepted":
            cur.execute(
                """
                INSERT INTO channel_members(channel_id, user_id)
                VALUES (%s, %s)
                ON CONFLICT (channel_id, user_id) DO NOTHING
                """,
                (invitation["channel_id"], g.user["user_id"]),
            )
    flash("Invitation response saved.", "success")
    return redirect(url_for("dashboard"))


@app.route("/search")
@login_required
def search():
    keyword = request.args.get("q", "").strip()
    results = []
    if keyword:
        results = query_all(
            """
            SELECT m.message_id, m.body, m.posted_at, u.username,
                   c.channel_id, c.name AS channel, w.name AS workspace
            FROM messages AS m
            JOIN channels AS c ON c.channel_id = m.channel_id
            JOIN workspaces AS w ON w.workspace_id = c.workspace_id
            JOIN users AS u ON u.user_id = m.sender_id
            JOIN workspace_members AS wm
              ON wm.workspace_id = w.workspace_id AND wm.user_id = %s
            JOIN channel_members AS cm
              ON cm.channel_id = c.channel_id AND cm.user_id = %s
            WHERE m.body ILIKE '%%' || %s || '%%'
            ORDER BY m.posted_at DESC, m.message_id DESC
            """,
            (g.user["user_id"], g.user["user_id"], keyword),
        )
    return render_template("search.html", keyword=keyword, results=results)


if __name__ == "__main__":
    app.run(debug=True)
