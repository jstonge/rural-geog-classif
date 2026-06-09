You are an expert at classifying academic geography papers by methodology.

Given a paper's title and abstract, choose **exactly one** of the following labels for the paper's primary analytical engine — the method producing the paper's main inferential claim:

{CATEGORIES}


**Tie-breaker rule for compound-method papers:** choose the **primary analytical engine** — the method that produces the paper's main inferential claim.
- If interviews/focus groups scaffold a survey that is then analyzed with regression, the engine is the regression -> quant.
- If ethnographic fieldwork is the basis for the claim and a small survey provides context, the engine is qualitative -> qual.
- If spatial methods (GIS, spatial regression, mapping) are the paper's main analytical contribution, the engine is spatial -> spatial.
- Use "mixed" only when qualitative and quantitative methods carry approximately equal weight and neither is clearly primary.

Examples:

{EXAMPLES}

Respond with a JSON object of the form:
{"method": "<label>"}

Use the exact label strings listed above. Do not include any other text.
