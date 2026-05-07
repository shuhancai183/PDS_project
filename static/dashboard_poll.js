(function () {
  const root = document.querySelector("[data-invitations-poll-url]");
  if (!root) {
    return;
  }

  const pollUrl = root.dataset.invitationsPollUrl;

  function createButtonForm(action, label) {
    const form = document.createElement("form");
    form.method = "post";
    form.action = action;

    const button = document.createElement("button");
    button.type = "submit";
    button.textContent = label;
    form.appendChild(button);
    return form;
  }

  function createInviteItem(invite, type) {
    const item = document.createElement("div");
    item.className = "item";

    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent =
      type === "workspace" ? invite.workspace : `${invite.workspace} / #${invite.channel}`;
    const small = document.createElement("small");
    small.textContent = `Invited by ${invite.invited_by}`;
    text.append(title, small);

    const actions = document.createElement("span");
    actions.className = "actions";
    actions.append(
      createButtonForm(invite.accept_url, "Accept"),
      createButtonForm(invite.decline_url, "Decline")
    );

    item.append(text, actions);
    return item;
  }

  function renderInviteList(type, invites, emptyText) {
    const container = root.querySelector(`[data-invite-list="${type}"] [data-invite-items]`);
    if (!container) {
      return;
    }

    container.replaceChildren();
    if (invites.length === 0) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.dataset.emptyState = "";
      empty.textContent = emptyText;
      container.appendChild(empty);
      return;
    }

    invites.forEach((invite) => {
      container.appendChild(createInviteItem(invite, type));
    });
  }

  async function pollInvitations() {
    if (document.hidden) {
      return;
    }

    try {
      const response = await fetch(pollUrl, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      renderInviteList(
        "workspace",
        payload.workspace_invites || [],
        "No pending workspace invitations."
      );
      renderInviteList(
        "channel",
        payload.channel_invites || [],
        "No pending channel invitations."
      );
    } catch (_error) {
      // The next polling tick will try again.
    }
  }

  window.setInterval(pollInvitations, 3000);
})();
