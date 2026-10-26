// Ranch page: countdown to the next arrival and the reveal dialog.

// --- Countdown: the next Pokémon arrives at the next full hour -------------
const countdown = document.querySelector("[data-next-arrival]");
if (countdown) {
  const target = new Date(countdown.dataset.nextArrival);
  const tick = () => {
    const seconds = Math.max(0, Math.round((target - Date.now()) / 1000));
    const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
    countdown.textContent = `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
    // A new hour started: reloading runs the catch-up on the server
    if (seconds === 0) setTimeout(() => location.reload(), 2000);
    else setTimeout(tick, 1000);
  };
  tick();
}

// --- Reveal dialog -----------------------------------------------------------
const dialog = document.querySelector("#reveal-dialog");
if (dialog) {
  if (dialog.hasAttribute("data-auto-open")) dialog.showModal();
  // Any [data-open-dialog] button opens it ("See who came", the tutorial gift)
  document.body.addEventListener("click", (event) => {
    if (event.target.closest("[data-open-dialog]")) dialog.showModal();
  });

  // Closing refreshes the page, so the Welcome area shows the right count
  dialog.addEventListener("close", () => location.reload());
  dialog.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-dialog]")) dialog.close();
  });

  // After each one-by-one reveal, play the cry when the Pokémon pops out
  // (1 s: the length of the Poké Ball animation, see input.css)
  document.body.addEventListener("htmx:afterSwap", (event) => {
    const cry = event.target.querySelector("audio[data-cry]");
    if (cry) setTimeout(() => cry.play().catch(() => {}), 1000);
  });
}
