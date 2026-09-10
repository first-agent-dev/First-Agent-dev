# Reproduce the numbers in Q17-Q18-DECISION-BRIEF.md

Each script drives the real controller. No mocked internals; only the LLM
stage is replaced by a stub returning a fixed judge message.

    python3 worklogs/reviews/q17-q18-demos/demo_q17_the_bug.py     # 4 of 5 steps unjudged -> DONE, exit 0
    python3 worklogs/reviews/q17-q18-demos/demo_q17_options.py     # cost of each Q17 option
    python3 worklogs/reviews/q17-q18-demos/demo_q18_evidence.py    # what the judge sees, block off vs on

    python3 worklogs/reviews/q17-q18-demos/demo_q20_regex_drift.py  # judge-output regex brittleness (Q20)
