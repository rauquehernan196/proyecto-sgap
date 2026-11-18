(() => {
  const container = document.querySelector(".flash-messages[data-poll-url]");
  if (!container) return;

  const addNotification = ({ level, message, url, action }) => {
    const alert = document.createElement("div");
    const safeLevel = ["success", "error", "warning", "info"].includes(level)
      ? level
      : "info";
    alert.className = `alert ${safeLevel}`;
    alert.setAttribute("role", safeLevel === "error" ? "alert" : "status");

    const link = document.createElement("a");
    link.className = "notification-link";
    link.href = url;
    const text = document.createElement("span");
    text.textContent = message;
    const actionText = document.createElement("span");
    actionText.className = "notification-action";
    actionText.textContent = `${action} →`;
    link.append(text, actionText);

    const dismiss = document.createElement("button");
    dismiss.className = "notification-dismiss";
    dismiss.type = "button";
    dismiss.setAttribute("aria-label", "Cerrar notificación");
    dismiss.textContent = "×";
    dismiss.addEventListener("click", () => alert.remove());

    alert.append(link, dismiss);
    container.append(alert);
  };

  container.querySelectorAll(".notification-dismiss").forEach((button) => {
    button.addEventListener("click", () => button.closest(".alert").remove());
  });

  const poll = async () => {
    const csrfToken = document.cookie
      .split("; ")
      .find((cookie) => cookie.startsWith("csrftoken="))
      ?.split("=")[1];
    if (!csrfToken) {
      console.error("No se pudo consultar las notificaciones: falta el token CSRF.");
      return;
    }

    try {
      const response = await fetch(container.dataset.pollUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": decodeURIComponent(csrfToken),
        },
        body: "{}",
      });
      if (!response.ok) {
        throw new Error(`La consulta de notificaciones respondió ${response.status}.`);
      }
      const payload = await response.json();
      payload.notifications.forEach(addNotification);
    } catch (error) {
      console.error("No se pudieron consultar las notificaciones.", error);
    }
  };

  poll();
  window.setInterval(poll, 15000);
})();
