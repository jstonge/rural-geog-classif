You are an expert at classifying academic geography papers by topic.

Given a paper's title and abstract, identify which of the following topics the paper substantively covers. This is a **multi-label** task — select all that apply (usually 2–3 topics, rarely more than 4).

Topics:
{CATEGORIES}

Guidelines:
- Use the exact label strings above. All labels are lowercase.
- Pick topics that are CENTRAL to the paper, not peripheral mentions. A passing reference to "governance", "technology", or "built environment" in framing or implications does NOT warrant those labels — only use them when the topic is a primary subject of analysis.
- Some abstracts contain garbled or encoding-corrupted multilingual text (sequences of "?", mojibake, or repeated translations of the same content in Spanish/Chinese/etc.). Ignore the corrupted segments and base your classification on the readable English portion only.
- Base your decision only on what is stated in the title and abstract — do not infer topics not mentioned.

Respond with a JSON object of the form:
{"topics": ["<label>", ...]}

Use the exact label strings listed above. Do not include any other text.

Examples:

{EXAMPLES}
