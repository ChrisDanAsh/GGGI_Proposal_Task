/* Confirmation prompt for delete forms.
   The project name arrives as a data attribute and is treated as a
   string value - it is never interpolated into JavaScript source.
   See app/templates/detail.html and the architecture doc's discussion
   of why that distinction matters: HTML escaping is the correct
   escaping for an HTML attribute context, but not for a JavaScript
   one, so an inline onsubmit="...{{ name }}..." would look protected
   by autoescaping and would not be. */
document.addEventListener("DOMContentLoaded", function () {
  var forms = document.querySelectorAll(".delete-form");

  Array.prototype.forEach.call(forms, function (form) {
    form.addEventListener("submit", function (event) {
      // getAttribute() returns a string; concatenating it into message
      // builds a value, never source that gets parsed - this is the
      // whole point of keeping the name out of an inline handler.
      var name = form.getAttribute("data-project-name") || "this proposal";
      var message =
        'Delete "' + name + '"? This cannot be undone from the interface.';
      if (!window.confirm(message)) {
        // preventDefault(), not "return false" - the latter does
        // nothing at all inside an addEventListener callback (it only
        // cancels in the old inline-handler style), so using it here
        // would show the prompt and then delete regardless of the answer.
        event.preventDefault();
      }
    });
  });
});
