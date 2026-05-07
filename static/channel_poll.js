(function () {
  const list = document.querySelector(".messages[data-poll-url]");
  if (!list) {
    return;
  }

  const pollUrl = list.dataset.pollUrl;
  const currentUserId = Number(list.dataset.currentUserId);
  let latestMessageId = 0;

  function refreshLatestMessageId() {
    list.querySelectorAll("[data-message-id]").forEach((message) => {
      latestMessageId = Math.max(latestMessageId, Number(message.dataset.messageId));
    });
  }

  function appendMessage(message) {
    if (list.querySelector(`[data-message-id="${message.message_id}"]`)) {
      return;
    }

    const emptyState = list.querySelector("[data-empty-state]");
    if (emptyState) {
      emptyState.remove();
    }

    const article = document.createElement("article");
    article.className = "message";
    article.dataset.messageId = String(message.message_id);

    const header = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = message.nickname;
    const meta = document.createElement("small");
    meta.textContent = `@${message.username} · ${message.posted_at}`;
    header.append(name, " ", meta);
    article.appendChild(header);

    const body = document.createElement("p");
    if (message.withdrawn) {
      body.className = "muted";
      body.textContent = "This message was withdrawn.";
      article.appendChild(body);
    } else {
      body.textContent = message.body;
      article.appendChild(body);

      if (Number(message.sender_id) === currentUserId) {
        const form = document.createElement("form");
        form.className = "inline-form";
        form.method = "post";
        form.action = `/messages/${message.message_id}/withdraw`;
        const button = document.createElement("button");
        button.type = "submit";
        button.textContent = "Withdraw";
        form.appendChild(button);
        article.appendChild(form);
      }
    }

    list.appendChild(article);
    latestMessageId = Math.max(latestMessageId, Number(message.message_id));
  }

  async function pollMessages() {
    if (document.hidden) {
      return;
    }

    try {
      const response = await fetch(`${pollUrl}?after=${latestMessageId}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      payload.messages.forEach(appendMessage);
    } catch (_error) {
      // The next polling tick will try again.
    }
  }

  refreshLatestMessageId();
  window.setInterval(pollMessages, 3000);
})();
