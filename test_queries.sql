\set ON_ERROR_STOP on
\i schema.sql
\i sample_data.sql

\echo 'Task 1: create a new user account'
INSERT INTO users(email, username, nickname, password_hash)
VALUES ('frank@example.com', 'frank', 'Frank', 'hash_frank')
RETURNING user_id, email, username, nickname;

\echo 'Task 2: create a public channel by authorized workspace member Cara'
BEGIN;
WITH created_channel AS (
    INSERT INTO channels(workspace_id, name, channel_type, created_by)
    SELECT 1, 'announcements', 'public', 3
    WHERE EXISTS (
        SELECT 1 FROM workspace_members
        WHERE workspace_id = 1 AND user_id = 3
    )
    RETURNING channel_id, workspace_id, name, channel_type, created_by
),
added_member AS (
    INSERT INTO channel_members(channel_id, user_id)
    SELECT channel_id, 3 FROM created_channel
    RETURNING channel_id, user_id
)
SELECT created_channel.channel_id,
       created_channel.workspace_id,
       created_channel.name,
       created_channel.channel_type,
       created_channel.created_by,
       added_member.user_id AS initial_member
FROM created_channel
JOIN added_member USING (channel_id);
COMMIT;

\echo 'Task 3: current administrators per workspace'
SELECT w.name AS workspace, u.username, u.email
FROM workspaces AS w
JOIN workspace_members AS wm ON wm.workspace_id = w.workspace_id
JOIN users AS u ON u.user_id = wm.user_id
WHERE wm.role = 'admin'
ORDER BY w.name, u.username;

\echo 'Task 4: old pending invitations to public channels in Acme Lab as of 2026-04-26'
SELECT c.name AS channel,
       COUNT(ci.invited_user_id) AS pending_invites_older_than_5_days
FROM channels AS c
LEFT JOIN channel_invitations AS ci
  ON ci.channel_id = c.channel_id
 AND ci.status = 'pending'
 AND ci.invited_at < (TIMESTAMPTZ '2026-04-26 00:00:00-04' - INTERVAL '5 days')
 AND NOT EXISTS (
     SELECT 1 FROM channel_members AS cm
     WHERE cm.channel_id = c.channel_id
       AND cm.user_id = ci.invited_user_id
 )
WHERE c.workspace_id = 1
  AND c.channel_type = 'public'
GROUP BY c.channel_id, c.name
ORDER BY c.name;

\echo 'Task 5: all messages in #general'
SELECT m.message_id, to_char(m.posted_at, 'YYYY-MM-DD HH24:MI') AS posted_at, u.username, m.body
FROM messages AS m
JOIN users AS u ON u.user_id = m.sender_id
WHERE m.channel_id = 1
ORDER BY m.posted_at, m.message_id;

\echo 'Task 6: all messages posted by Bob'
SELECT m.message_id, w.name AS workspace, c.name AS channel, to_char(m.posted_at, 'YYYY-MM-DD HH24:MI') AS posted_at, m.body
FROM messages AS m
JOIN channels AS c ON c.channel_id = m.channel_id
JOIN workspaces AS w ON w.workspace_id = c.workspace_id
WHERE m.sender_id = 2
ORDER BY m.posted_at, m.message_id;

\echo 'Task 7: messages accessible to Cara containing perpendicular'
SELECT m.message_id, w.name AS workspace, c.name AS channel, u.username AS sender,
       to_char(m.posted_at, 'YYYY-MM-DD HH24:MI') AS posted_at, m.body
FROM messages AS m
JOIN channels AS c ON c.channel_id = m.channel_id
JOIN workspaces AS w ON w.workspace_id = c.workspace_id
JOIN users AS u ON u.user_id = m.sender_id
JOIN workspace_members AS wm
  ON wm.workspace_id = w.workspace_id
 AND wm.user_id = 3
JOIN channel_members AS cm
  ON cm.channel_id = c.channel_id
 AND cm.user_id = 3
WHERE m.body ILIKE '%perpendicular%'
ORDER BY m.posted_at, m.message_id;
