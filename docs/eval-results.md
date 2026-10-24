# Eval results

Run on 2026-10-24 13:01 UTC at commit `b243bc7`. Provider: **anthropic**; answer / rewrite / judge models: claude-haiku-5-5 / claude-haiku-5-5 / claude-haiku-5-5; effort `low`; embedder: BAAI/bge-small-en-v1.5 @ 5c38ec7; retrieval top-k vector 20 + BM25 20 -> RRF top 8; 20 questions.

## Summary

| Metric | Value |
| --- | --- |
| Recall@8 (expected page among retrieved chunks) | 100% |
| Answers with at least one citation | 100% |
| Citation accuracy, any cited page correct (n=20) | 100% |
| Citation accuracy, all cited pages correct (n=20) | 80% |
| Faithfulness, mean of 1-5 (judge failures: 0) | 5.00 |
| Faithfulness distribution 1 / 2 / 3 / 4 / 5 | 0 / 0 / 0 / 0 / 20 |
| `max_tokens` stops | 0 |
| Latency median / p95 | 1.33 s / 2.13 s |
| Mean prompt tokens / output tokens / thinking tokens | 10056 / 129 / 14 |
| Answer cost, total / mean per question | $0.0198 / $0.00100 |
| Judge cost, total | $0.0134 |

Faithfulness is scored by the judge model from the retrieved excerpts and the reference answer. With the default configuration Haiku judges Haiku, so treat the score as a consistency check rather than an independent audit.

## Follow-up turns (query rewrite and prompt caching)

| # | Follow-up question | Rewritten query | Cache read tokens | Cache write tokens | Cit. any | $ turn 1 | $ turn 2 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| nasa-04 | How many pickup trucks is that equivalent to? | crawler-transporter 2 weight in equivalent pickup trucks | 7955 | 6903 | yes | $0.0001 | $0.0011 |
| rfc-01 | Which section number of the document defines that code? | Which section number of the document defines the "418 I'm a teapot" error code? | 10580 | 8418 | yes | $0.0012 | $0.0012 |
| yw-01 | Does he believe that she is sick? | Does John, the physician husband of the narrator, believe that the narrator is sick? | 11409 | 10424 | yes | $0.0013 | $0.0016 |

## Per question

| # | File | Question | Expected | Retrieved pages | Cited pages | Recall@8 | Cit. any | Cit. all | Faith. | s | $ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nasa-01 | nasa-crawler-transporters.pdf | When were the crawler-transporters built, and which rocket were they built to move? | [1] | [1, 3, 2, 4, 2, 2] | [1, 3] | yes | yes | no | 5 | 1.89 | 0.0011 |
| nasa-02 | nasa-crawler-transporters.pdf | How far does a crawler carry a rocket to reach Launch Pad 39B? | [1] | [1, 2, 3, 4, 2, 2] | [1, 2] | yes | yes | no | 5 | 1.29 | 0.0001 |
| nasa-03 | nasa-crawler-transporters.pdf | How many miles has crawler-transporter 2 (CT-2) traveled in total? | [1] | [1, 2, 3, 4, 2, 2] | [1] | yes | yes | yes | 5 | 1.07 | 0.0001 |
| nasa-04 | nasa-crawler-transporters.pdf | How much does crawler-transporter 2 weigh? | [2] | [2, 1, 3, 4, 2, 2] | [2] | yes | yes | yes | 5 | 1.52 | 0.0001 |
| nasa-05 | nasa-crawler-transporters.pdf | What is the uprated load carrying capacity of CT-2? | [2] | [2, 1, 2, 3, 2, 4] | [2] | yes | yes | yes | 5 | 2.13 | 0.0001 |
| nasa-06 | nasa-crawler-transporters.pdf | What is the fuel consumption of a crawler-transporter? | [2] | [1, 2, 2, 4, 3, 2] | [2] | yes | yes | yes | 5 | 1.12 | 0.0001 |
| nasa-07 | nasa-crawler-transporters.pdf | On what date did a crawler move space shuttle Columbia to the pad for the first time? | [3] | [3, 1, 4, 2, 2, 2] | [3] | yes | yes | yes | 5 | 1.58 | 0.0002 |
| rfc-01 | rfc2324-htcpcp.pdf | Which error code should a teapot return when asked to brew coffee? | [5] | [5, 4, 6, 2, 3, 7, 1, 8] | [5] | yes | yes | yes | 5 | 1.35 | 0.0012 |
| rfc-02 | rfc2324-htcpcp.pdf | In which year was the Internet Toaster debuted? | [1] | [1, 8, 9, 7, 10, 5, 2, 4] | [1] | yes | yes | yes | 5 | 1.19 | 0.0011 |
| rfc-03 | rfc2324-htcpcp.pdf | Which two request methods must a coffee pot server accept equivalently? | [2] | [2, 6, 7, 4, 3, 1, 5, 8] | [2] | yes | yes | yes | 5 | 1.3 | 0.0002 |
| rfc-04 | rfc2324-htcpcp.pdf | Which alcohol types can be requested as additions to coffee? | [4] | [4, 3, 5, 2, 1, 6, 8, 7] | [4] | yes | yes | yes | 5 | 1.34 | 0.0002 |
| rfc-05 | rfc2324-htcpcp.pdf | In how many languages can the coffee URL scheme be written? | [5] | [5, 6, 8, 2, 3, 1, 10, 7] | [5] | yes | yes | yes | 5 | 1.32 | 0.0012 |
| rfc-06 | rfc2324-htcpcp.pdf | What are the two possible values of the coffee message body? | [6] | [6, 2, 5, 3, 4, 1, 8, 7] | [6] | yes | yes | yes | 5 | 2.28 | 0.0002 |
| rfc-07 | rfc2324-htcpcp.pdf | Why is HTCPCP based on HTTP and port 80? | [7] | [2, 7, 10, 6, 1, 3, 5, 4] | [2, 7] | yes | yes | no | 5 | 1.68 | 0.0012 |
| yw-01 | the-yellow-wallpaper.pdf | What is the profession of the narrator's husband, John? | [1] | [1, 5, 4, 7, 3, 6, 9, 14] | [1] | yes | yes | yes | 5 | 1.21 | 0.0013 |
| yw-02 | the-yellow-wallpaper.pdf | What does the narrator take for her condition? | [1] | [1, 8, 9, 7, 2, 6, 11, 5] | [1, 7] | yes | yes | no | 5 | 1.19 | 0.0015 |
| yw-03 | the-yellow-wallpaper.pdf | How far is the house from the village? | [2] | [2, 5, 13, 4, 8, 3, 7, 10] | [2] | yes | yes | yes | 5 | 1.04 | 0.0015 |
| yw-04 | the-yellow-wallpaper.pdf | Where in the house is the narrator's room? | [2] | [2, 4, 5, 6, 3, 10, 13, 8] | [2] | yes | yes | yes | 5 | 0.99 | 0.0015 |
| yw-05 | the-yellow-wallpaper.pdf | Who takes care of the baby? | [3] | [3, 7, 5, 2, 6, 1, 10, 8] | [3] | yes | yes | yes | 5 | 1.99 | 0.0015 |
| yw-06 | the-yellow-wallpaper.pdf | To which doctor does John say he will send the narrator in the fall if she does not pick up faster? | [5] | [8, 5, 7, 1, 12, 11, 6, 3] | [5] | yes | yes | yes | 5 | 1.98 | 0.0014 |

## How to reproduce

```bash
cd backend
uv run evals/run.py                                       # real provider, needs ANTHROPIC_API_KEY in the repo-root .env
uv run evals/run.py --provider mock --embeddings fake --limit 3   # offline smoke run
```
