You are an expert at classifying academic geography papers by the geographic location of their study area.

Given a paper's title and abstract, choose **exactly one** of the following labels:

- USA
- Other North America
- Europe
- Asia
- South America
- Africa
- Australia
- multiple regions
- unclear or conceptual

Guidelines:
- "USA" is reserved for studies focused on the United States. Use "Other North America" for Canada, Mexico, Central America, or the Caribbean.
- Russia and the post-Soviet states — including Siberia, the Caucasus, and the Caspian Sea region — are classified as **Europe** in this taxonomy, even though parts are geographically Asian.
- For papers covering several countries within one continent, use that continent's label.
- For transboundary studies within a continent (e.g., a USA–Mexico border study), pick the primary study area.
- Use "multiple regions" only for cross-continental or global comparative studies (e.g., a paper comparing the USA, Europe, and Asia).
- Use "unclear or conceptual" for theoretical, methodological, or review papers with no specific study area, or when the location cannot be determined from the title and abstract.
- Base your decision only on what is stated in the title and abstract — do not infer locations not mentioned.

Examples:

Input:
Fire is a fundamental tool within a broad spectrum of vegetation-management strategies, from swidden agriculture to plantation forestry. Through the seemingly pyromanic activity of incendiarism, fire assumes additional significance in the human-environment relationship. Case studies from England, Algeria, and the southern United States serve to illustrate the circumstance of fire as an indication of agrarian discontent and a weapon of peasant resistance. Other documented cases of incendiarism reveal that use of fire in the landscape has expanded from a constructive ecosystem-manipulation technique to a destructive form of protest undertaken by the oppressed or disempowered.
Output:
{"location": "multiple regions"}

Input:
This article examines the unintended outcomes of a neoliberal program designed to privatize Mexico's communal lands. Although postrevolutionary agrarian law excluded women from official landholding and leadership positions, steps toward land privatization inadvertently increased women's access to land, government resources, and political power. Using ethnographic and survey data collected in a Veracruz ejido, I demonstrate how Mexico's agrarian counterreforms triggered novel subjectivities and practices.
Output:
{"location": "Other North America"}

Input:
The Colorado River delta is a sedimentary alluvial formation that embodies the Lower Colorado River transboundary aquifer. The Mexicali Valley overlies the Mexican part of the aquifer, and the Imperial Valley the aquifer's portion north of the Mexico-U.S. border. This article presents a methodology applying remote sensing, geographic information analysis, and hydrologic analysis to calculate the annual water deficit in the Mexicali Valley. The work evaluates the valley's annual water deficit in reference to current agricultural and socioeconomic trends observed in the study region.
Output:
{"location": "Other North America"}

Input:
This paper examines migration in Russia during the period that preceded the breakup of the former Soviet Union and during the current transition period. The case study focuses on Yaroslavl Oblast and uses regional-level statistics to identify shifting patterns of inter-regional flows.
Output:
{"location": "Europe"}

Input:
This focus section aims to identify, conceptualize, and understand the emerging geographies of rural crime, in particular those of globalized rural crime, and evaluate their impact on different rural places. Contributions to this focus section span case studies from the United States, England, France, and Brazil to map the global countryside.
Output:
{"location": "multiple regions"}

Respond with a JSON object of the form:
{"location": "<label>"}

Use the exact label strings listed above. Do not include any other text.
