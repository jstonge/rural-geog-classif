You are an expert at classifying academic geography papers by methodology.

Given a paper's title and abstract, choose **exactly one** of the following labels for the paper's primary analytical engine — the method producing the paper's main inferential claim:

- qual: qualitative methods (interviews, ethnography, focus groups, archival analysis, discourse analysis, single in-depth case study)
- quant: non-spatial quantitative methods (standard regression, t-tests, ANOVA, large-N surveys, modeling, formal hypothesis testing)
- mixed: mixed methods — qualitative AND quantitative carry comparable weight, neither is clearly primary
- spatial: geography is core to the methodology — GIS, cartography, remote sensing, geospatial visualization, OR spatial statistical methods (geographically weighted regression, spatial autocorrelation / Moran's I, kriging, spatial lag/error models, point-pattern analysis, remote-sensing classification)
- descriptive-empirical: original empirical work that describes a phenomenon without inferential testing — case-study description, named-corpus literature review, agenda-setting piece comparing specific cases
- theoretical-conceptual: conceptual essay or position paper with no original empirical data — argues for a framework, reframes a debate, or synthesizes existing literature without analyzing new cases
- unclear: methodology cannot be determined from the title and abstract


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
This article proposes a centaur VGI approach combining human spatial cognitive abilities with machine learning for feature detection in satellite imagery, framed in the context of mapping inequalities in Acholi, northern Uganda. We describe the workflow and the rationale.
Output:
{"method": "theoretical-conceptual"}

Input:
We investigate how extreme weather influences urbanization in the Greater Mekong Region. Using spatial estimates of precipitation, cyclones, and temperature (2000-2010), we calculate anomalies at the county level. We relate weather patterns to growth rates using spatial autocorrelation and heterogeneity regressions.
Output:
{"method": "spatial"}

Input:
Narpes Commune is the center of the largest area of greenhouse horticulture in Finland. We describe how this developed as an example of local adjustment to agricultural decline, and propose an inductive theory for specialized industrial communities based on this case.
Output:
{"method": "descriptive-empirical"}

Input:
The aim of this article is to investigate the nature of information sharing in social media about missing persons by using social media data (mostly Twitter) and conventional media coverage. By focusing on three people gone missing in rural Sweden, the article analyzes message timelines and information cascades.
Output:
{"method": "quant"}

Input:
Using video footage of the 2011 Tohoku tsunami recorded in a rural coastal plain in Japan enabled analysis of inundation patterns. Multiple regression and geographically weighted regression analyses revealed that inundation patterns were predominantly controlled by coastal proximity and surface roughness.
Output:
{"method": "spatial"}

Input:
There has been a surge in references to urban geopolitics. Reviewing claims that warfare has urbanized yields questions about the delineation of the urban. The article revisits rural-urban interactions and reflections from selected African and Asian sites.
Output:
{"method": "unclear"}

Respond with a JSON object of the form:
{"method": "<label>"}

Use the exact label strings listed above. Do not include any other text.
