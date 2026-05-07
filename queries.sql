-- Placeholder convention:
-- :name means a value supplied by the application or by psql variables.

-- (1) Create a new user account.
INSERT INTO users(email, username, nickname, password_hash)
VALUES (:email, :username, :nickname, :password_hash)
RETURNING user_id, email, username, nickname, created_at;

-- (2) Create a new public channel inside a workspace by an authorized user.
-- The creator must already be a member of the workspace.
BEGIN;
WITH created_channel AS (
    INSERT INTO channels(workspace_id, name, channel_type, created_by)
    SELECT :workspace_id, :channel_name, 'public', :creator_id
    WHERE EXISTS (
        SELECT 1
        FROM workspace_members
        WHERE workspace_id = :workspace_id
          AND user_id = :creator_id
    )
    RETURNING channel_id
)
INSERT INTO channel_members(channel_id, user_id)
SELECT channel_id, :creator_id
FROM created_channel
RETURNING channel_id, user_id;
COMMIT;

-- (3) For each workspace, list all current administrators.
SELECT w.workspace_id, w.name AS workspace, u.user_id, u.username, u.email
FROM workspaces AS w
JOIN workspace_members AS wm ON wm.workspace_id = w.workspace_id
JOIN users AS u ON u.user_id = wm.user_id
WHERE wm.role = 'admin'
ORDER BY w.name, u.username;

-- (4) For each public channel in a given workspace, count users invited
-- more than 5 days ago who have not yet joined.
SELECT c.channel_id,
       c.name AS channel,
       COUNT(ci.invited_user_id) AS pending_invites_older_than_5_days
FROM channels AS c
LEFT JOIN channel_invitations AS ci
  ON ci.channel_id = c.channel_id
 AND ci.status = 'pending'
 AND ci.invited_at < (:as_of::timestamptz - INTERVAL '5 days')
 AND NOT EXISTS (
     SELECT 1
     FROM channel_members AS cm
     WHERE cm.channel_id = c.channel_id
       AND cm.user_id = ci.invited_user_id
 )
WHERE c.workspace_id = :workspace_id
  AND c.channel_type = 'public'
GROUP BY c.channel_id, c.name
ORDER BY c.name;

-- (5) For a particular channel, list all messages in chronological order.
SELECT m.message_id, m.posted_at, u.username AS sender, m.body
FROM messages AS m
JOIN users AS u ON u.user_id = m.sender_id
WHERE m.channel_id = :channel_id
ORDER BY m.posted_at, m.message_id;

-- (6) For a particular user, list all messages they have posted in any channel.
SELECT m.message_id, w.name AS workspace, c.name AS channel, m.posted_at, m.body
FROM messages AS m
JOIN channels AS c ON c.channel_id = m.channel_id
JOIN workspaces AS w ON w.workspace_id = c.workspace_id
WHERE m.sender_id = :user_id
ORDER BY m.posted_at, m.message_id;

-- (7) For a particular user, list all accessible messages containing a keyword.
-- Accessible means that the user is a member of both the workspace and the channel.
SELECT m.message_id,
       w.name AS workspace,
       c.name AS channel,
       u.username AS sender,
       m.posted_at,
       m.body
FROM messages AS m
JOIN channels AS c ON c.channel_id = m.channel_id
JOIN workspaces AS w ON w.workspace_id = c.workspace_id
JOIN users AS u ON u.user_id = m.sender_id
JOIN workspace_members AS wm
  ON wm.workspace_id = w.workspace_id
 AND wm.user_id = :user_id
JOIN channel_members AS cm
  ON cm.channel_id = c.channel_id
 AND cm.user_id = :user_id
WHERE m.body ILIKE '%' || :keyword || '%'
ORDER BY m.posted_at, m.message_id;
