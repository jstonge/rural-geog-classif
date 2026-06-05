# Physical geography — collaborator spot-check

We collapsed the previous 17 categories into 12, with **physical geography** absorbing
the old *natural environment*, *weather*, and *climate and natural hazards*. Six papers
on our 90-paper annotated sample produce a stable disagreement between the current GT
annotations (made under the old 17-category scheme) and the new model running on the
12-category prompt. We want your call on each paper: **under the new physical-geography
definition, should this paper be tagged `physical geography`? (yes / no / unsure)**

The new definition treats `physical geography` as: *physical environment, landscape change,
ecosystem change, soils, hydrological or marine ecosystems, geomorphology, natural resources,
plants, animals, water, forests, desert; meteorology, weather systems, El Niño, La Niña,
weather prediction; climate change, hazards, natural disaster, climate science, human impacts
of climate change, resilience, climate mitigation, climate adaptation, flooding, drought,
hazards prediction, hurricanes, tornadoes, earthquakes, tsunamis, cyclone.*

---

## Group A — Model tags `physical geography`; current GT does not (3 papers)

These are cases where the model fires the new physical-geography label but the existing
annotations don't include it. Should they?

### A1. Human-Induced Resource Scarcity in the Colorado River Basin and Its Implications for Water Supply and the Environment in the Mexicali Valley Transboundary Aquifer

**DOI:** 10.1080/24694452.2022.2162477

**Current GT (the labels annotators chose):** built environment, governance, human-environment, place-based study

**Model's predicted labels:** agriculture/food, human-environment, physical geography, place-based study

**Abstract:**

> The Colorado River delta is a sedimentary alluvial formation that embodies the Lower Colorado River transboundary aquifer. The Mexicali Valley overlies the Mexican part of the aquifer, and the Imperial Valley the aquifer's portion north of the Mexico-U.S. border. Mexico receives an annual water allocation from the Colorado River stipulated by an international treaty between Mexico and the United States. The Colorado River water allocation to Mexico is shared by farmers in the Mexicali Valley and by several border cities, rural communities, and industries in the northern region of the State of Baja California. Farmers withdraw groundwater from the Mexicali Valley's aquifer to make up for insufficient Colorado River water to grow their crops. Groundwater withdrawal has created overdraft of the Mexicali Valley aquifer with associated adverse impacts: sea water intrusion, declining groundwater levels, upwelling of brackish groundwater, land subsidence, degradation of groundwater-dependent ecosystems, and emigration of displaced farmers. This article reviews the natural and human histories in the Colorado River basin and the Mexicali Valley, and presents a methodology applying remote sensing, geographic information analysis, and hydrologic analysis to calculate the annual water deficit in the Mexicali Valley. Finally, this work evaluates the valley's annual water deficit in reference to current agricultural and socioeconomic trends observed in the study region. Aquifer and related environmental degradation have adversely affected small-scale farming and exacerbated demographic instability.

**Q: Under the new physical-geography definition, should this paper be tagged `physical geography`?**  ☐ yes  ☐ no  ☐ unsure

---

### A2. Environmental discourses and the Ivorian Savanna

**DOI:** 10.1111/0004-5608.00184

**Current GT (the labels annotators chose):** governance, human-environment, scale/location

**Model's predicted labels:** governance, human-environment, physical geography, scale/location

**Abstract:**

> The African continent is portrayed in development texts as experiencing environmental crises of staggering proportions. Despite a lack of reliable data, the World Bank considers environmental degradation to be so widespread that the business of environmental planning and regulation is now seen as a global affair. It currently requires low-income countries receiving its financial assistance to develop National Environmental Action Plans (NEAPs) which, in assembly line fashion, are bring produced according to a blueprint. Taking the West African case study of Cote d'Ivoire, this paper argues that the planning process, specifically the identification of environmental problems, is based on a poor understanding of the nature and direction of environmental change. We confront this data problem by contrasting the image of a deforested savanna landscape found in the Cote d'Ivoire NEAP with the more wooded landscape experienced by farmers and herders and confirmed by our analysis of aerial photographs. Our second objective is to address thr policy implications of two geographical issues rising from this paper: the disjointed scale problem between local/regional environmental-change patterns and global environmental discourses, and the human-environmental consequences of ignoring actual versus imagined environmental problems. A third goal is to contribute to the growing convergence in cultural and political ecology around the use of multiple research methods to explain environmental-change dynamics. Our discussion of environmental change is informed by intensive data collection in two rural communities in the Korhogo region of northern Cote d'Ivoire. Research methods included focus-group discussions and household surveys to record local perceptions of environmental change. Aerial photo analysis, GIS mapping, and vegetation transects were used to interpret land-cover changes. Finally, interviews with individuals involved in the NEAP process in the Cote d'Ivoire government, World Bank, and NGOs illuminated the received ideas and institutional interests of various players in environmental planning.

**Q: Under the new physical-geography definition, should this paper be tagged `physical geography`?**  ☐ yes  ☐ no  ☐ unsure

---

### A3. LANDSCAPES OF CULTIVATION IN MESOAMERICA ON THE EVE OF THE CONQUEST

**DOI:** 10.1111/j.1467-8306.1992.tb01967.x

**Current GT (the labels annotators chose):** agriculture/food, governance, human-environment, identity

**Model's predicted labels:** agriculture/food, built environment, human-environment, physical geography

**Abstract:**

> Pre-Columbian Amerindian agriculturalists developed technologies and management practices with which to crop a wide range of ecological conditions, giving rise to a multiplicity of cultivated landscapes. This variety was particularly evident in Mesoamerica, where agricultural practices ranged from swiddening to multicropped, hydraulically transformed wetlands. Here we explore these indigenous cultivated landscapes as they existed about the time of the Columbian Encounter. We illustrate them through the examination of three transects approximating the courses of the initial Spanish entradas through this diverse region: the first extends from the Gulf coast to central Mexico; the second traverses the Yucatan peninsula from north to south; and the third climbs into highland Guatemala from the Pacific coastal plain. Second, we broadly sketch the major changes that took place in these landscapes during the first phase of Spanish domination and some of the forces that shaped these changes. Three processes were especially significant: the Amerindian depopulation, the introduction of exotic biota and technologies, and the reordering of land and the rural economy. Ultimately, however, reconfigured hybrid landscapes resulted that reflected the union of cultures. Last, we argue that the scale of environmental transformation of Amerindian agriculture has not always been fully appreciated, the scale of environmental degradation associated with Spanish introductions has been overstated at times, and the contrasting ideologies of nature between the two cultures has been over-simplified.

**Q: Under the new physical-geography definition, should this paper be tagged `physical geography`?**  ☐ yes  ☐ no  ☐ unsure

---

## Group B — Current GT tags `physical geography`; model does not (3 papers)

These are cases where the existing annotations include `physical geography` (collapsed from
the old `climate and natural hazards` label) but the new model didn't tag it. Should it?

### B1. Rural Ruins in America's Climate Change Story: Photojournalism, Perception, and Agency in Shishmaref, Alaska

**DOI:** 10.1080/24694452.2018.1525272

**Current GT (the labels annotators chose):** emotion, physical geography, place-based study

**Model's predicted labels:** built environment, emotion, human-environment, place-based study

**Abstract:**

> This article provides a visual analysis of a set of peopleless photographs taken in 2006 of a falling home erosion in the village of Shishmaref, Alaska, that have been widely circulated in reporting about the relocation of the village due to climate change. It asks whether the visual contract between spectator and absent climate change victim extends beyond an empathetic response to action toward restoring the lost home. The article explores the relationship of contemporary scholarship on postmodern ruination in U.S. Rust Belt cities and the Shishmaref fallen home photograph as a means to analyze the work done by rural ruination.

**Q: Under the new physical-geography definition, should this paper be tagged `physical geography`?**  ☐ yes  ☐ no  ☐ unsure

---

### B2. The Rise and Fall of a Timber Baron: Political Forests and Unruly Coalitions in the Carpathian Mountains of Romania

**DOI:** 10.1080/24694452.2020.1723399

**Current GT (the labels annotators chose):** governance, human-environment, physical geography, place-based study, social power

**Model's predicted labels:** governance, human-environment, place-based study, social power

**Abstract:**

> Concerns over deforestation are growing along with the climate crisis. This is particularly unsettling in relation to the rise of populist authoritarian regimes. In this article I reveal the connections between forests, neoliberalism, authoritarianism, and cronyism, through an in-depth ethnographic study of the Romanian Carpathian forests after the fall of socialism in 1989. The study examines the intricate entanglements between forest extraction, party politics, and informal territorial governance that emerged over the last thirty years. It argues that unruly coalitions shaped forest history. It focuses on the central figure of the timber baron, who ran businesses in connection with state office politics and maintained provincial authoritarian control over resources by tapping into paternalist dependencies of rural mountain dwellers. The article uses the analytic tools of political ecology and the conceptual framework developed by studies on resource frontiers and political forests combined with the anthropology of postsocialism. I draw on field research from 2004 to 2016, in which I collected data through systematic fieldwork, interviews, and surveys, complemented with official reports and media coverage. The article uses a narrative ethnographic writing approach.

**Q: Under the new physical-geography definition, should this paper be tagged `physical geography`?**  ☐ yes  ☐ no  ☐ unsure

---

### B3. Cumulative Socionatural Displacements: Reconceptualizing Climate Displacements in a World Already on the Move

**DOI:** 10.1080/24694452.2021.1960144

**Current GT (the labels annotators chose):** human-environment, mobility, physical geography, social power

**Model's predicted labels:** agriculture/food, human-environment, mobility, social power

**Abstract:**

> Climate-induced displacement is attracting increasing media, state, and scholarly attention, albeit often in a way that situates migration as either an example of climate adaptation or a failure thereof. Whether depicted as success or failure, both framings can invisibilize the preexisting socioenvironmental processes that render climate-induced migrations necessary-or, conversely, that can inhibit them entirely. Perspectives on displacement and environmental migration from within political ecology and human geography offer an alternative register, looking beyond unidirectional socioeconomic or environmental drivers to document how uneven development reproduces displacements relationally and historically. Drawing on these theorizations, as well as empirical research from agrarian Southeast Asia, this article develops the notion of cumulative socionatural displacements as one approach for conceptualizing socioecologically driven displacement in a world already on the move. We demonstrate this approach through an analysis of displacement in Southeast Asia that begins by tracing the evolving state, market, and agroecological relations that have made mobility integral to agrarian viability while setting the stage for more intense climate impacts. In doing so, we also center the long-term (nonclimatic) environmental changes that are often sidelined in both anthropocentric debates on rural displacements and climate doomsday scenarios. We argue that examining climate-induced migration as just one facet of cumulative socionatural displacements is necessary for overcoming the ontological and political impasses engendered by prevailing narratives that collapse climate migration into convenient but misleading binaries.

**Q: Under the new physical-geography definition, should this paper be tagged `physical geography`?**  ☐ yes  ☐ no  ☐ unsure

---
