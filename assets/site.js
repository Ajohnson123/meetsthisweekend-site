// Filter chips for scene and day. No frameworks, one init, no globals beyond it.
(function initFilters() {
  var grid = document.getElementById("meet-grid");
  if (!grid) return;
  var cards = Array.prototype.slice.call(grid.querySelectorAll(".meet"));
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
  var count = document.getElementById("count");
  var empty = document.getElementById("empty");
  var state = { scene: "all", day: "all" };

  function apply() {
    var shown = 0;
    cards.forEach(function (c) {
      var sceneOk = state.scene === "all" || c.getAttribute("data-scene") === state.scene;
      var days = (c.getAttribute("data-days") || "").split(" ");
      var dayOk = state.day === "all" || days.indexOf(state.day) !== -1;
      var show = sceneOk && dayOk;
      c.hidden = !show;
      if (show) shown += 1;
    });
    if (count) count.textContent = shown + (shown === 1 ? " meet" : " meets");
    if (empty) empty.hidden = shown !== 0;
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var group = chip.getAttribute("data-group");
      state[group] = chip.getAttribute("data-value");
      chips.forEach(function (o) {
        if (o.getAttribute("data-group") === group) {
          o.setAttribute("aria-pressed", String(o === chip));
        }
      });
      apply();
    });
  });
})();
