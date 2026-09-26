# Case Study: RubricSmith

**A small, offline tool that grades LLM answers against answers I know are right, and tells me why each one failed.**

## The problem

When you build a chatbot with an LLM, you change things all the time. You edit the prompt, switch to a cheaper model, or change the settings. After each change you have to ask: did the answers get better or worse?

Most people check by reading some answers by hand. That is slow, and it is easy to miss a small mistake, like a refund time that changed from 5 days to 7 days.

Another option is to use a second LLM as the judge. But that costs money, needs an API key, and can give a different score for the same answer on a different day. I wanted something that was:

- free and fast, so I can run it after every change,
- repeatable, so the same answer always gets the same score,
- clear, so it says *why* a case failed, not just a number.

## What I built

RubricSmith takes three files:

1. **A golden dataset.** Questions with good reference answers, plus optional keywords that must appear.
2. **Model answers.** What the bot actually said.
3. **A rubric.** Which checks to run, how much each one counts, and what it takes to pass.

It gives back a pass or fail for each case, a Markdown scorecard, a saved run history, and a dashboard to explore the results. The CLI can also fail a CI build if too few cases pass.

To test it, I made 12 support questions for a made-up delivery app called ParcelPal, plus answers from a strong model and a weaker one.

## How it works

![Architecture diagram](architecture.png)

Each metric is a small function that takes an answer and a case and returns a score from 0 to 1. I wrote five metrics from scratch:

- **Exact match.** For short answers like a city name.
- **Keyword recall.** Are the important words there?
- **ROUGE-L.** How much of the reference appears in the answer, in the same order. This uses the longest common subsequence, which I built with dynamic programming.
- **Length ratio.** Is the answer too short or way too long?
- **No forbidden phrases.** Catches lines like "As an AI language model".

Metrics are added with a `@register` decorator. The rubric picks them by name. This means adding a new metric never needs a change in the grading code. To prove it, I wrote a sixth metric, `numbers_match`, as a separate plugin file.

## Key decisions

**Weights plus hard minimums.** A plain weighted average was not enough. An answer with good wording but the wrong refund time still got a decent average. So each metric can have a minimum. If a metric is below its minimum, the case fails, no matter how good the average is. This one idea made the results match my own judgment much better.

**"Not applicable" is not zero.** Some cases have no keywords. If keyword recall gave them 0, good answers would fail. If it gave them 1, they would get free points. So a metric can return "n/a", and it is left out of that case's average.

**Memory-light LCS.** The full DP table needs n × m cells. For the score, I only need the length, so that version keeps just two rows. For the dashboard, I need to know *which* words matched, so a second version builds the full table and walks back through it. I tested both against a slow brute force version on 200 random inputs.

**Standard library only.** The server, the database (SQLite) and all metrics use only Python's standard library. The project runs right after `git clone`, and every part is easy to explain.

## Results

| | Model A | Model B |
|---|---|---|
| Cases passed | 11 of 12 (92%) | 4 of 12 (33%) |
| Mean score | 0.90 | 0.51 |

For Model B, the scorecard pointed to the main problems right away: missing keywords (5 cases), wrong or missing numbers (5 cases), and one "As an AI language model" reply. That is much more useful than one number.

The tool also found a real mistake that is easy to miss when reading: Model B said refunds take **7** business days instead of **5**. The sentence reads fine. ROUGE-L gave it a medium score. `numbers_match` caught it.

The project has 91 automated tests.

## What was hard

**Word-based metrics can be wrong.** Model A failed one case where it said "if delivery fails twice" and the reference said "after 2 failed attempts". A human sees the same meaning. My metrics don't. I decided to keep this failure in the sample data and show it in the dashboard, instead of hiding it. It is a good example of what this kind of tool can and can't do.

**Plurals.** My first version said "refund" was missing from "Refunds take 5 days". I added a simple plural check (refund and refunds, box and boxes). I did not add full word stemming, because "refund" and "refunded" can mean different things in a support answer.

## What I would do next

- Turn number words into digits ("twice" to 2, "five" to 5) before comparing numbers.
- Add an optional LLM judge metric for meaning, with the answer cached so scores stay repeatable.
- Compare two runs side by side and show which cases got better or worse.

