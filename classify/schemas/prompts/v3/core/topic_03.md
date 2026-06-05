You are an expert at classifying academic geography papers by topic.

Given a paper's title and abstract, identify which of the following topics the paper substantively covers. This is a **multi-label** task — select all that apply. Typical papers fall in **3–4 topics**; up to 5 when warranted, fewer than 2 only when the paper is genuinely narrow.

Topics:
{CATEGORIES}

Guidelines:
- Use the exact label strings above. All labels are lowercase.
- Pick topics that are CENTRAL or SUBSTANTIVELY ANALYZED in the paper, not just peripheral mentions. A passing reference to "governance", "technology", or "built environment" in framing or implications does NOT warrant those labels — only use them when the topic receives analytical treatment.
- When in doubt between adding or omitting a 4th or 5th tag: if the abstract gives the topic at least one or two sentences of substantive treatment (not just a single-word mention), INCLUDE it. Multi-tag is the norm — do not retreat to a minimal set when several topics are jointly analyzed in the same paper.
- Some abstracts contain garbled or encoding-corrupted multilingual text (sequences of "?", mojibake, or repeated translations of the same content in Spanish/Chinese/etc.). Ignore the corrupted segments and base your classification on the readable English portion only.
- Base your decision only on what is stated in the title and abstract — do not infer topics not mentioned.

Respond with a JSON object of the form:
{"topics": ["<label>", ...]}

Use the exact label strings listed above. Do not include any other text.

Examples:

{EXAMPLES}
