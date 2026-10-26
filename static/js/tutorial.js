// Tutorial popup: pages of the intro, spotlight on the explained element,
// and closing after the gift. See ranch/templates/ranch/_tutorial.html.
const tutorial = document.querySelector("[data-tutorial]");

if (tutorial) {
  // --- Intro pages: "Next" shows the following page ------------------------
  tutorial.addEventListener("click", (event) => {
    if (!event.target.closest("[data-tutorial-next-page]")) return;
    const pages = [...tutorial.querySelectorAll("[data-tutorial-page]")];
    const current = pages.findIndex((page) => !page.hidden);
    pages[current].hidden = true;
    pages[current + 1].hidden = false;
  });

  // --- Spotlight: a box placed over the explained element ------------------
  // Its huge shadow (see .tutorial-spot in input.css) dims the rest of the
  // screen. It is positioned in JavaScript because the element may sit
  // inside scrolling panes that would clip a shadow drawn by the element.
  const spot = tutorial.querySelector(".tutorial-spot");
  const target = tutorial.dataset.spot && document.querySelector(tutorial.dataset.spot);
  if (spot && target) {
    const place = () => {
      const box = target.getBoundingClientRect();
      Object.assign(spot.style, {
        top: `${box.top - 6}px`,
        left: `${box.left - 6}px`,
        width: `${box.width + 12}px`,
        height: `${box.height + 12}px`,
      });
      spot.hidden = false;
    };
    place();
    window.addEventListener("resize", place);
  }

  // --- After the gift: "Done" reloads the page (the tutorial is over) ------
  tutorial.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-dialog]")) location.reload();
  });
}
