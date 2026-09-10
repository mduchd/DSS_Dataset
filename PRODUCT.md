# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Confirmed: plain HTML, CSS and JavaScript for the interface; Python/Flask for the recommendation API.

## Users

Primary users are Vietnamese high-school students comparing university majors and schools after receiving or estimating their examination scores. They need a fast, understandable shortlist rather than an opaque prediction.

## Product Purpose

The application helps students explore majors and universities using their subject scores, admission combinations, historical cut-off scores, and job-market context. Success is a clear shortlist that distinguishes safe, suitable, and ambitious choices.

## Positioning

The recommendation is explainable: every result shows the score gap and the historical cut-off used to classify it, while job information is clearly presented as supporting context.

## Operating Context

Students enter subject scores, choose an admission combination, a preferred area and an optional major interest. The application filters and ranks choices, then lets users inspect historical cut-offs and labour-market context.

## Capabilities and Constraints

- The first build is a working interface and a Flask-backed demo recommendation flow.
- Raw admission, exam and job datasets are available locally under `data/raw/` but have not yet been cleaned or mapped into production recommendation tables.
- Recommendation labels are guidance only, not a guarantee of admission or employment.
- The public raw exam data includes `SBD`; the user interface must not expose individual records.

## Evidence on Hand

- Admission cut-off data for 2018–2024 in `data/raw/admission/`.
- Exam-score datasets for 2021–2025 in `data/raw/exam/`.
- VietJobs in `data/raw/jobs/VietJobs/VietJobs.csv`.
- No verified mapping between academic majors and job categories is available yet.

## Product Principles

1. Explain every recommendation with observable inputs and score differences.
2. Keep the first decision path short: scores in, shortlist out.
3. Separate historical evidence from future-looking guidance.
4. Protect individual exam records by showing aggregates only.

## Accessibility & Inclusion

The web interface supports keyboard use, visible focus states, readable Vietnamese labels and responsive layouts for phone and desktop.
