/* Live character counter for the project summary textarea.
   Runs entirely in the browser and sends nothing over the network -
   it just watches the textarea and rewrites a number on screen. */
document.addEventListener("DOMContentLoaded", function () {
  var textarea = document.getElementById("summary");
  var counter = document.getElementById("summary-counter");
  if (!textarea || !counter) {
    // Guard clause: harmless on any page that has no summary textarea.
    return;
  }

  // Read the limit from the maxlength attribute rather than hard-coding
  // it, so the number that matters lives in exactly one place - the
  // template - and this script cannot drift out of step with what the
  // browser actually enforces.
  var limit = parseInt(textarea.getAttribute("maxlength"), 10) || 300;

  function update() {
    var used = textarea.value.length;
    counter.textContent =
      used + " / " + limit + " · " + (limit - used) + " remaining";
  }

  textarea.addEventListener("input", update);
  // Called once on load, not only on input, so an edit form opened with
  // an existing summary shows its real remaining count immediately
  // rather than starting from zero.
  update();
});
