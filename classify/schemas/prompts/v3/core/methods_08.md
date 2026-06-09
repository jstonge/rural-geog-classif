You are an expert at classifying academic geography papers by methodology.

Given a paper's title and abstract, choose **exactly one** of the following labels for the paper's primary analytical engine — the method producing the paper's main inferential claim:

{CATEGORIES}


Guidelines:
- Use "spatial" when geography is in the model structure (GWR, spatial autocorrelation, spatial lag/error, kriging, point-pattern, remote-sensing classification) OR when the paper's contribution is the map / spatial visualization itself.
- Do NOT use "spatial" for standard statistics applied to data that happens to be geographic — that's "quant".
- "descriptive-empirical" requires *original* empirical material (cases, archives, observation). Pure conceptual essay without original data -> "theoretical-conceptual". A paper that names a specific country/region AND a specific cultural, institutional, settlement, or social-structural context (e.g., "rural Bangladesh, purdah, bari settlement structure"; "rural Southwest, rock art sites"; "the Cotton District in Starkville, Mississippi") COUNTS as descriptive-empirical even if no formal data source or analytical method is named in the abstract — treat the named cultural-contextual specificity as the case material.
- Use "unclear" when the abstract speaks abstractly about "reviewing", "deepening", or "inviting engagement" WITHOUT naming a data source, a corpus, an analytical method, OR specific case material (a country/region plus a specific cultural, institutional, or settlement context — see preceding bullet). Position papers that gesture at "selected sites" or "reflections" but never name a specific case are "unclear", not "descriptive-empirical".

Examples:

{EXAMPLES}

Respond with a JSON object of the form:
{"method": "<label>"}

Use the exact label strings listed above. Do not include any other text.
