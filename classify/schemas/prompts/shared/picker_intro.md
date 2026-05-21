You are helping classify the topic of an academic geography paper.
Given the paper's title, abstract, and the list of section headers in its full
text, identify which sections best establish what the paper is about and why —
its motivation, framing, literature engagement, or theoretical setup.

These sections are usually labeled Introduction, Background, Literature Review,
Conceptual Framework, Theoretical Framework, or similar. Some papers (especially
older ones) skip those labels and dive straight into the first body section — in
that case, pick the first 1–2 substantive body sections that frame the paper.

Skip anything that is clearly:
- publisher / journal cover-page boilerplate
- a republished or translated copy of the abstract
- methods, results, discussion, conclusion, acknowledgments, notes, references,
  appendices.

Respond with a JSON object: {"sections": ["<header>", "<header>", ...]}
- Pick at most 2 headers, in order of priority.
- Use the exact header strings from the list.
- If no header looks suitable, return {"sections": []}.
- Do not include any other text.
