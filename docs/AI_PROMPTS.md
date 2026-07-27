# AI Prompt Usage Note

The process of creating this project was layered.

## 1. Understanding the problem space

Since most of my prior work was solely creating APIs, I had little
knowledge of how to build web applications. My first step was
therefore to understand exactly what a web app is and how one is
created.

This led to the creation of [climate-proposal-app-plan.md](climate-proposal-app-plan.md),
produced with Claude AI after several prompts. The first prompt used
was:

> I have experience in Python and building APIs using Docker and
> running them on GCP. Help me understand what tools would best fit
> me to solve the following task. Explain the tools that I would need
> and what the process would be in building a version of this task
> that would last in the long term, whose functionality could be
> incrementally added to over time. It must be built with
> production in mind and must be scalable.
>
> Task:
> {Task inserted here}

This conversation was carried out until I had a solid understanding of
what a web application is, how it works, and what steps are required
to build one.

## 2. Architecture and implementation planning

The next step was creating the architecture and detailed
implementation plan.

I know how to code, but my true strength is understanding how systems
work. I therefore spend most of my time on architectural documents to
ensure the logic behind the code is sound. 

[architecture-and-implementation-plan.md](architecture-and-implementation-plan.md)
details exactly what is going to be built and exactly how it should be
built.

It also serves as very detailed documentation for the code base ensuring that:
- The code can be full understood from the ground up (Logic --> actual code)
- Errors that occur can be easily traced and fixed
- Handing over goes smoothly since the entire system is well documented


I arrived at this method of working with AI after trial and error at
my last job, and found it to be one of the more effective ways to use
AI to write code: there is very little room for the AI to make
mistakes during implementation, since the context for the code is set
and all of the major decisions are made beforehand. All that is left
for the AI to do afterward is implement what is in the file, which
greatly reduces the chance of errors in the code.

Since this is a document style I have refined over time, I reuse
previous versions of this document to create new versions — so the
prompt used to create this plan included previous planning documents
alongside the task document.

The resulting plan is always read over and edited to ensure the
decisions being made match the goals of the project, using logic I
deem sound. It is rare for the first version to be exactly what is
necessary. Once the plan is built, however, there is rarely much work
left to do on it again.

### Cross-checking the plan with a second AI

I also double-check the plan against a second AI. I personally find
Codex produces more robust code and is better at finding coding-level
problems, whereas Claude is better at ideation. So once the plan has
been reviewed, the following prompt is used in Codex to find any flaws
that may exist:

> [CTAF_Coding_Assignment.pdf](CTAF_Coding_Assignment.pdf) — here is
> the assignment. Does the
> [architecture-and-implementation-plan.md](architecture-and-implementation-plan.md)
> fully meet all of the requirements of the task, and is the plan
> production-grade and scalable/upgradeable?

Any errors found in the plan are sent to Claude to review and fix.
This is an iterative process, repeated until no more major errors are
found. Note that not all errors found are chosen to be fixed only the one's deemed necessary for the current version of the web application as some errors found can be trivial or even intentional depending on the current needs of the system. 

## 3. Implementation

Once the plan is complete, most of the work is done, and the following
prompt is used for essentially the rest of development:

1. **"Implement module N of this plan"** / **"Implement Phase N"**

Also, the prompt below was used to ensure that the code is readable in
case any sections need to be reviewed in the future:

2. **"During coding ensure that all code is clearly commented so that
   someone reading the code would know what the code does and the
   purpose of the code as well"**

No modifications were made to the code developed by the AI, and all
testing was done using the created tests and live testing of the
actual application to ensure that it works as expected.
