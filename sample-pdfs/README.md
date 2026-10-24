# Sample PDFs

Three small public documents used by the demo, the tests and the evaluation set.

| File | Pages | Source | Terms |
| --- | --- | --- | --- |
| `nasa-crawler-transporters.pdf` | 4 | NASA fact sheet, [nasa.gov](https://www.nasa.gov/wp-content/uploads/2021/04/combined_crawler-transporters_fact_sheet_final.pdf) | NASA material is generally not subject to copyright in the United States. The NASA insignia and logos are protected and may not be used to imply endorsement. Answers in this app describe what the document says and are never phrased as statements by NASA. |
| `rfc2324-htcpcp.pdf` | 10 | RFC 2324, Hyper Text Coffee Pot Control Protocol, [ietf.org](https://www.ietf.org/ietf-ftp/rfc/rfc2324.txt.pdf) | Reproduced unmodified under the RFC's Full Copyright Statement (Copyright (C) The Internet Society, 1998), which permits copying and distribution of the unmodified document. |
| `the-yellow-wallpaper.pdf` | 14 | "The Yellow Wallpaper" by Charlotte Perkins Gilman (1892), text from [Project Gutenberg #1952](https://www.gutenberg.org/ebooks/1952), rendered to PDF with `backend/scripts/make_sample_pdf.py` | The story is in the public domain. The Project Gutenberg header, footer and licence were removed, so this file is not a Project Gutenberg distribution and does not use the trademark. |

Regenerate the third file with:

```bash
cd backend
curl -sSL -o scripts/.cache/pg1952.txt https://www.gutenberg.org/cache/epub/1952/pg1952.txt
uv run scripts/make_sample_pdf.py scripts/.cache/pg1952.txt ../sample-pdfs/the-yellow-wallpaper.pdf --check
```
