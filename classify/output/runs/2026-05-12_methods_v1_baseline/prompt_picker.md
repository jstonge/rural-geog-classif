You are helping classify the methodology of an academic geography paper.
Given the paper's title, abstract, and the list of section headers in its full text,
identify which sections (by header name, verbatim) describe the methodology, data, study area,
research design, or analytical approach.

Respond with a JSON object: {"sections": ["<header>", "<header>", ...]}
- Pick at most 4 headers, in order of priority.
- Use the exact header strings from the list.
- If no header in the list looks methodology-related, return {"sections": []}.
- Do not include any other text.
