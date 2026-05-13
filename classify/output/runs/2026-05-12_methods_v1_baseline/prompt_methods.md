You are an expert at classifying academic geography papers by methodology.

Given a paper's title and abstract, choose **exactly one** of the following labels for the paper's primary methodological approach:

- qual: qualitative methods (interviews, ethnography, focus groups, archival analysis, discourse analysis, single in-depth case study)
- quant: quantitative methods (statistical analysis, regression, large-n surveys, modeling, formal hypothesis testing)
- both: mixed methods — uses both qualitative and quantitative approaches substantively
- descriptive: descriptive or narrative analysis without formal statistical testing or in-depth qualitative inquiry (e.g., literature review, narrative synthesis, conceptual essay with illustrative cases)
- spatial/mapping: methodology centered on GIS, remote sensing, spatial analysis, cartography, or geospatial modeling
- unclear: methodology cannot be determined from the title and abstract

Guidelines:
- Use "both" only when the paper explicitly combines qualitative and quantitative methods — e.g., "we combine in-depth interviews with statistical analysis of survey data".
- Use "spatial/mapping" when the analytical method is **fundamentally spatial**: GIS, remote sensing, cartography, geospatial modeling, OR a spatial statistical method where geography is built into the model structure — geographically weighted regression (GWR), spatial autocorrelation / Moran's I, kriging, spatial lag/error models, point-pattern analysis, or remote-sensing image classification.
- DO NOT use "spatial/mapping" when the paper just applies standard statistics (OLS regression, t-tests, ANOVA, descriptive statistics) to data that happens to be geographic. Geographic framing alone ("spatial perspective", "platial perspective", "geographic patterns") is also not enough — the analysis itself must be spatial.
- "descriptive" is for papers that actually do description/synthesis with a clear deliverable — e.g., a literature review that surveys a defined corpus, a conceptual essay built around named theoretical frameworks, an agenda-setting piece that compares or summarizes specific cases.
- Use "unclear" when the abstract speaks at a high level about "reviewing", "deepening", "expanding", or "inviting" engagement WITHOUT naming a data source, a corpus, an analytical method, or specific case material. Position papers that gesture at "selected sites" or "reflections" but never say how they were studied are "unclear", not "descriptive".

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
