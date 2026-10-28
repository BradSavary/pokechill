// Zone pages: dialogs (the harvest summary, the Pokémon picker, a worker's card).
// Any [data-open="#id"] element opens that dialog; [data-close] closes its own.

document.body.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-open]");
  if (opener) {
    const dialog = document.querySelector(opener.dataset.open);
    // A "+" tells the picker's forms which spot was clicked
    if (opener.dataset.spot !== undefined) {
      dialog.querySelectorAll("[data-spot-input]").forEach((input) => {
        input.value = opener.dataset.spot;
      });
    }
    dialog?.showModal();
  }
  if (event.target.closest("[data-close]")) event.target.closest("dialog")?.close();
  // A click on the dimmed backdrop closes the dialog. Such a click lands on the
  // <dialog> element itself, but so does one in its padding: only a click
  // outside the dialog's box is a click on the backdrop.
  if (event.target instanceof HTMLDialogElement) {
    const box = event.target.getBoundingClientRect();
    const inside =
      box.left <= event.clientX && event.clientX <= box.right &&
      box.top <= event.clientY && event.clientY <= box.bottom;
    if (!inside) event.target.close();
  }
});

// Sortable tables (the Pokémon picker): a [data-sort] button sorts the rows
// of its [data-list] by their data-<key>: names A to Z first, numbers (level,
// rate) highest first; clicking it again reverses the order. Ties keep their
// original order. ⇅ marks the other sortable columns.
document.querySelectorAll("[data-sort]").forEach((button) => {
  button.addEventListener("click", () => {
    const list = document.querySelector(button.dataset.list);
    const key = button.dataset.sort;
    const first = key === "name" ? "asc" : "desc";
    const direction = button.dataset.direction === first ? (first === "asc" ? "desc" : "asc") : first;
    const sign = direction === "asc" ? 1 : -1;
    const rows = [...list.children].sort((a, b) => {
      const order =
        key === "name"
          ? a.dataset.name.localeCompare(b.dataset.name)
          : Number(a.dataset[key]) - Number(b.dataset[key]);
      return sign * order || a.dataset.order - b.dataset.order;
    });
    list.append(...rows); // moving the existing rows puts them in the new order
    document.querySelectorAll(`[data-list="${button.dataset.list}"]`).forEach((other) => {
      delete other.dataset.direction;
      other.querySelector("[data-arrow]").textContent = "⇅";
    });
    button.dataset.direction = direction;
    button.querySelector("[data-arrow]").textContent = direction === "asc" ? "▲" : "▼";
  });
});

// The harvest summary opens by itself, right after a collection
document.querySelectorAll("dialog[data-auto-open]").forEach((dialog) => dialog.showModal());
