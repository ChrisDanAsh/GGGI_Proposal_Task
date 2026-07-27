# AI Prompt Usage Note

*Draft — written from the session record. Review and adjust in your
own words before submitting; this should reflect your actual
experience, not just what the tool log shows.*

This application was built with Claude Code (Anthropic), working from
a detailed specification (`docs/architecture-and-implementation-plan.md`)
written and refined before any code existed.

Three prompts that shaped the process most:

1. **"Implement module N of this plan"** / **"Implement Phase N"** —
   the recurring prompt for nearly the whole build, issued once per
   module or phase in the plan's own order (Modules 1 through 18,
   Phases 1 through 6). Each time, the relevant section of the spec was
   read in full first, then transcribed into working code. Output was
   used essentially as-is: the specification fixed enough detail
   (exact status codes, exact SQLAlchemy settings, the reasoning behind
   each choice) that little was left to the model's judgment at
   implementation time.

2. **"implement modules 8 to 10 including their requisite tests to
   ensure that they are implemented properly"** — asked explicitly for
   test coverage rather than trusting an implementation was correct
   because it ran without error. In response, the model didn't just
   write tests that passed — it deliberately reintroduced a bug (e.g.
   removing the duplicate-name check, adding back an inline event
   handler) to confirm the corresponding test actually failed, then
   reverted it and reconfirmed the suite was green. That verify-by-
   breaking-it pattern was then applied to later phases without being
   asked for again.

3. **"during coding ensure that all code is clearly commented so that
   someone reading the code would know what the code does and the
   purpose of the code as well"** — a correction issued mid-session,
   after noticing the model's default comment density was too sparse
   for this project. The model went back and expanded comments on
   already-written files, and kept the denser style for every file
   written afterward.

Modification of the model's output: none of the generated code was
hand-edited after the fact. A few implementation choices not fully
pinned down by the spec (e.g. whether the edit route should fetch the
proposal before or after validating submitted form data) were left to
the model's judgment, with its reasoning stated inline in code comments
or in the chat response, rather than silently decided.
