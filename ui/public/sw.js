/* Worlds push service worker — docs/NOTIFICATIONS.md.
 *
 * Does exactly two jobs and nothing else: show a push, and open the
 * right window when it is clicked. NO fetch handling, NO caching, NO
 * offline: the app decides nothing about the network from here, and a
 * worker that meddles with requests is a support story nobody needs.
 *
 * Served at the site root with `Service-Worker-Allowed: /` (api.py),
 * so it controls every path of the app. Payloads come from Worlds
 * itself (push.py): {title, body, tier, tier_words, link, id, source}. */

self.addEventListener("push", (event) => {
  let note = {};
  try {
    note = event.data ? event.data.json() : {};
  } catch (err) {
    note = {};
  }
  // Heading: how loud it is, then who sent it (design: the sender is
  // named up top). The message's own title leads the body. A private
  // notification arrives with no title and a generic body, so nothing
  // private shows on the Lock Screen.
  const sender = note.sender || "Worlds";
  const heading = note.tier_words ? `${note.tier_words} · ${sender}` : sender;
  const body = note.title ? `${note.title}: ${note.body || ""}` : note.body || "";
  event.waitUntil(
    self.registration.showNotification(heading, {
      body,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      tag: note.id || "worlds",
      data: { link: note.link || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const link = (event.notification.data && event.notification.data.link) || "/";
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windows) => {
        // An open Worlds window takes the click (nobody wants a second
        // copy), and goes to the page the notification is about.
        for (const client of windows) {
          if ("focus" in client) {
            const go = "navigate" in client ? client.navigate(link) : Promise.resolve(client);
            return go.then((c) => (c || client).focus());
          }
        }
        return self.clients.openWindow(link);
      }),
  );
});
