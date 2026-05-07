from app import app, query_one


with app.app_context():
    print("DATABASE_URL:", app.config["DATABASE_URL"])
    try:
        users = query_one("SELECT count(*) AS n FROM users")
        alice = query_one(
            "SELECT user_id, username, password_hash FROM users WHERE username = %s",
            ("alice",),
        )
        print("users count:", users["n"])
        print("alice row:", dict(alice) if alice else None)
    except Exception as exc:
        print("DATABASE CHECK FAILED:")
        print(type(exc).__name__ + ":", exc)
        raise SystemExit(1)

client = app.test_client()
response = client.post(
    "/login",
    data={"username": "alice", "password": "hash_alice"},
    follow_redirects=True,
)
print("alice login status:", response.status_code)
html = response.data.decode("utf-8", errors="replace")
title_start = html.find("<title>")
title_end = html.find("</title>")
if title_start != -1 and title_end != -1:
    print("page title snippet:", html[title_start : title_end + len("</title>")])
if response.status_code >= 400:
    print(html[:1200])
