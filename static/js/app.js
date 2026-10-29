// Behaviour shared by every page of the game (loaded by templates/base.html).

// A game, not a web page: images (map, sprites, icons) can't be dragged away.
document.addEventListener("dragstart", (event) => {
  if (event.target instanceof HTMLImageElement) event.preventDefault();
});

// Dialogs: any [data-open="#id"] element opens that dialog; [data-close]
// closes its own. A click on the dimmed backdrop closes a .dialog-panel: such
// a click lands on the <dialog> element itself, but so does one in its
// padding, so only a click outside the dialog's box counts. (The reveal
// dialog of the Ranch has its own rules, in ranch.js.)
document.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-open]");
  if (opener) document.querySelector(opener.dataset.open)?.showModal();
  if (event.target.closest("[data-close]")) event.target.closest("dialog")?.close();
  const dialog = event.target;
  if (dialog instanceof HTMLDialogElement && dialog.classList.contains("dialog-panel")) {
    const box = dialog.getBoundingClientRect();
    const inside =
      box.left <= event.clientX && event.clientX <= box.right &&
      box.top <= event.clientY && event.clientY <= box.bottom;
    if (!inside) dialog.close();
  }
});
// A .dialog-panel marked data-auto-open opens by itself (a harvest summary...)
document.querySelectorAll("dialog.dialog-panel[data-auto-open]:not([open])").forEach((dialog) => {
  dialog.showModal();
});

// "i" bubbles (templates/_info_tip.html): the mouse shows them on hover (CSS);
// a click or a tap toggles them, and a click anywhere else closes them. Being
// focused is not enough: a dialog gives the focus to its first "i" on opening.
//
// The bubble is fixed to the screen (see .info-tip in input.css), placed here
// before it shows: under the "i", or above it in the lower half of the
// screen, and always inside the screen on the sides.
const TIP_WIDTH = 256; // w-64
const MARGIN = 8;

function placeTip(tip) {
  const box = tip.getBoundingClientRect();
  const left = Math.min(
    Math.max(box.left + box.width / 2 - TIP_WIDTH / 2, MARGIN),
    window.innerWidth - TIP_WIDTH - MARGIN,
  );
  tip.style.setProperty("--tip-left", `${left}px`);
  const below = box.bottom < window.innerHeight / 2;
  tip.style.setProperty("--tip-top", below ? `${box.bottom + MARGIN}px` : "auto");
  tip.style.setProperty("--tip-bottom", below ? "auto" : `${window.innerHeight - box.top + MARGIN}px`);
}

function toggleTip(tip) {
  placeTip(tip);
  tip.classList.toggle("is-open");
}

document.addEventListener("mouseover", (event) => {
  const tip = event.target.closest?.(".info-tip");
  if (tip) placeTip(tip);
});
document.addEventListener("click", (event) => {
  const tip = event.target.closest(".info-tip");
  document.querySelectorAll(".info-tip.is-open").forEach((open) => {
    if (open !== tip) open.classList.remove("is-open");
  });
  if (tip) toggleTip(tip);
});
document.addEventListener("keydown", (event) => {
  const tip = event.target.closest?.(".info-tip");
  if (tip && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    toggleTip(tip);
  }
});

