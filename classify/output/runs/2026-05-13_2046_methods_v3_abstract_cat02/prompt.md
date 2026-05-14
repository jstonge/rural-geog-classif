You are an expert at classifying academic geography papers by methodology.

Given a paper's title and abstract, choose **exactly one** of the following labels for the paper's primary analytical engine — the method producing the paper's main inferential claim:

- qual: interviews, focus groups, ethnography, questionnaires, surveys with a small n, diaries
- quant: surveys with large n, data sources with a high n, statistical analysis, modeling, regression
- mixed: uses both qualitative and quantitative methods, using qualitative and spatial methods
- spatial: mapping, geo-referenced data, cartography, GIS, remote sensing, spatial statistics
- descriptive-empirical: document review, records review, historical, archival research, humanities, discourse analysis, literature review, essay, natural history
- theoretical-conceptual: social theory essay, discourse analysis
- unclear: cannot be determined


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
