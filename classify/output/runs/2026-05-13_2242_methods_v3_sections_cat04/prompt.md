You are an expert at classifying academic geography papers by methodology.

Given a paper's title and abstract, choose **exactly one** of the following labels for the paper's primary analytical engine — the method producing the paper's main inferential claim:

- qual: primary evidence is in-depth interviews, ethnography, focus groups, narrative accounts, or discourse analysis of a small number of cases
- quant: primary evidence is statistical analysis on a large-N survey or non-spatial numeric dataset — no spatial methods, no in-depth qualitative work
- mixed: qualitative interviews/ethnography AND quantitative analysis are both genuinely present, even if one is somewhat larger than the other; use this whenever a paper combines the two engines (don't require strict equality)
- spatial: the abstract NAMES an explicit spatial-statistical method (geographically weighted regression, spatial autocorrelation / Moran's I, kriging, spatial lag/error, point-pattern analysis, remote-sensing classification, or a GIS overlay that produces the inferential claim). Cartographic visualization alone is NOT enough.
- descriptive-empirical: describes an original case or named corpus through narrative, archival, or historical analysis with original empirical material (case study, fieldwork notes, archives). NOT for literature reviews, NOT for discourse analysis.
- theoretical-conceptual: humanities-style essay, conceptual position paper, or literature review of a defined corpus, with no original empirical data (no new fieldwork, no new survey, no original archive)
- unclear: the methodology cannot be clearly determined from the abstract — the paper might be doing one of several things but the abstract doesn't name a specific data source, analytical method, or case material


**Tie-breaker rule for compound-method papers:** choose the **primary analytical engine** — the method that produces the paper's main inferential claim.
- If interviews/focus groups scaffold a survey that is then analyzed with regression, the engine is the regression -> quant.
- If ethnographic fieldwork is the basis for the claim and a small survey provides context, the engine is qualitative -> qual.
- If spatial methods (GIS, spatial regression, mapping) are the paper's main analytical contribution, the engine is spatial -> spatial.
- Use "mixed" only when qualitative and quantitative methods carry approximately equal weight and neither is clearly primary.

Guidelines:
- Use "spatial" when geography is in the model structure (GWR, spatial autocorrelation, spatial lag/error, kriging, point-pattern, remote-sensing classification) OR when the paper's contribution is the map / spatial visualization itself.
- Do NOT use "spatial" for standard statistics applied to data that happens to be geographic — that's "quant".
- "descriptive-empirical" requires *original* empirical material (cases, archives, observation). Pure conceptual essay without original data -> "theoretical-conceptual".
- Use "unclear" when the abstract speaks abstractly about "reviewing", "deepening", or "inviting engagement" WITHOUT naming a data source, a corpus, an analytical method, or specific case material.

Examples:

Input:
The aim of this article is to investigate the nature of information sharing in social media about missing persons by using social media data (mostly Twitter) and conventional media coverage (media archives), adopting a platial perspective to this geographical information. By focusing on the cases of three people gone missing in rural Sweden, the article analyzes message timelines and information cascades.
Output:
{"method": "quant"}

Input:
This study advances understanding of nature-society interactions by examining the spatiotemporal coupling of tsunami hazards and human responses. Using video footage of the 2011 Tohoku tsunami recorded in a rural coastal plain in Japan enabled analysis of inundation patterns and evacuation responses under different lead times. Multiple regression and geographically weighted regression analyses revealed that inundation patterns were predominantly controlled by coastal proximity and surface roughness, while road and waterway configurations locally modified flow velocities. Evacuation analysis identified distinct response patterns associated with different temporal zones of tsunami inundation.
Output:
{"method": "spatial/mapping"}

Input:
There has been a surge in references to urban geopolitics over the last twenty-plus years. Reviewing claims that warfare has urbanized, however, yields questions about the delineation and frontiers of the urban. The multiple meanings and definitions of geopolitics and urban beckon a broadening range of sites and an analytical deepening of urban geopolitics. To these ends, reviewing and seeking to develop the field in conceptual terms, the article revisits rural-urban interactions and reflections from selected African and Asian sites. The overall aim of the article is not to delimit urban geopolitics, but to deepen and expand agendas, broadening the range of cases that inform these. This also invites deeper geopolitical engagement with literature on extended and planetary urbanization.
Output:
{"method": "unclear"}

Respond with a JSON object of the form:
{"method": "<label>"}

Use the exact label strings listed above. Do not include any other text.
