// Zone pages: the spots of the map and the sortable picker. The dialogs
// themselves open and close with app.js ([data-open], [data-close]).

// A "+" tells the picker's forms which spot was clicked
document.body.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-open][data-spot]");
  if (!opener) return;
  document.querySelector(opener.dataset.open).querySelectorAll("[data-spot-input]").forEach((input) => {
    input.value = opener.dataset.spot;
  });
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

