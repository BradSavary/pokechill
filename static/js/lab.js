// Lab page: the node clicked becomes the selected one (its panel comes from HTMX).
document.body.addEventListener("click", (event) => {
  const node = event.target.closest("[data-skill-node]");
  if (!node) return;
  document.querySelectorAll("[data-skill-node].is-selected").forEach((n) => n.classList.remove("is-selected"));
  node.classList.add("is-selected");
});
