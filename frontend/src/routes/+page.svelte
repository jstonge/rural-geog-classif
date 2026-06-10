<script lang="ts">
  import { scaleLinear, scaleOrdinal, scaleBand } from 'd3-scale';
  import { schemeTableau10, schemeSet3 } from 'd3-scale-chromatic';
  import { SvelteMap } from 'svelte/reactivity';
  import data from '$lib/data/methods_viz.json';
  import locationsData from '$lib/data/locations_viz.json';
  import topicsData from '$lib/data/topics_viz.json';
  import topicCompare from '$lib/data/topic_compare.json';
  import { exportPng } from '$lib/exportPng';

  // Refs for PNG export
  let overviewRef!: SVGSVGElement;
  let methodsStackedRef!: SVGSVGElement;
  let regionsStackedRef!: SVGSVGElement;
  let methodsUsVsNonUsBarRef!: SVGSVGElement;
  let topicsStackedRef!: SVGSVGElement;
  let topicsUsVsNonUsBarRef!: SVGSVGElement;
  let upsetRef!: SVGSVGElement;
  let coocRef!: SVGSVGElement;
  let methodsStackedHeaderRef!: HTMLDivElement;
  let regionsStackedHeaderRef!: HTMLDivElement;
  let methodsUsVsNonUsBarHeaderRef!: HTMLDivElement;
  let topicsStackedHeaderRef!: HTMLDivElement;
  let topicsUsVsNonUsBarHeaderRef!: HTMLDivElement;
  let methodsFacetsRef!: HTMLElement;
  let regionsFacetsRef!: HTMLElement;
  let methodsUsVsNonUsFacetsRef!: HTMLElement;
  let topicsFacetsRef!: HTMLElement;
  let topicsUsVsNonUsFacetsRef!: HTMLElement;
  let anchorFacetsRef!: HTMLElement;

  type Paper = {
    doi: string;
    title: string;
    authors: string;
    pub_year: string;
    source: string;
    keywords: string;
    abstract: string;
    method: string;
  };

  type MethodModelDef = {
    key: string;
    label: string;
    description: string;
    categories: { value: string; definition: string }[];
  };

  type RawMethodPaper = {
    doi: string;
    title: string;
    authors: string;
    pub_year: string;
    source: string;
    keywords: string;
    abstract: string;
    methods: Record<string, string>;
  };

  const methodsViz = data as unknown as { models: MethodModelDef[]; papers: RawMethodPaper[] };
  const methodModels = methodsViz.models;

  // Selector state: which methods-model view to render. Defaults to the first
  // model in the JSON (currently sections_baseline).
  let methodModel: string = $state(
    methodModels.find((m) => m.key === 'abstract_production')?.key ?? methodModels[0].key
  );

  const currentMethodModel: MethodModelDef = $derived(
    methodModels.find((m) => m.key === methodModel) ?? methodModels[0]
  );

  // Ordered by empirical frequency for the selected model (most common first).
  const methodCategories: string[] = $derived(
    currentMethodModel.categories.map((c) => c.value)
  );

  // Per-category definitions from the model JSON.
  const methodDescriptions: Record<string, string> = $derived(
    Object.fromEntries(
      currentMethodModel.categories.map((c) => [c.value, c.definition])
    ) as Record<string, string>
  );

  const papers: Paper[] = $derived(
    methodsViz.papers
      .filter((p) => p.methods[methodModel] != null && p.methods[methodModel] !== '')
      .map((p) => ({
        doi: p.doi,
        title: p.title,
        authors: p.authors,
        pub_year: p.pub_year,
        source: p.source,
        keywords: p.keywords,
        abstract: p.abstract,
        method: p.methods[methodModel]!
      }))
  );

  const color = $derived(
    scaleOrdinal<string, string>().domain(methodCategories).range(schemeTableau10)
  );

  // Bar chart dimensions
  const barWidth = 600;
  const barHeight = 500;
  const barMargin = { top: 20, right: 20, bottom: 50, left: 60 };

  // 5-year bucketing (data range ~1986–2026). 8 buckets; the first (1987) folds
  // in the sparse 1986 papers, so it covers 1986–1991. Bucket-start years are
  // used as keys; bucketLabel formats display ranges.
  const decades = ['1987', '1992', '1997', '2002', '2007', '2012', '2017', '2022'] as const;
  const bucketWidth = 5;
  const bucketAnchor = 1987;
  const lastBucketStart = 2022;
  const dataMaxYear = 2026;
  const firstBucketMinYear = 1986;
  const lowConfidenceBuckets = new Set<string>(['1987']);
  const lowConfidenceTitle = '1986–1991: only ~8 papers — proportions are unreliable';

  function getDecade(year: string): string {
    const y = parseInt(year, 10);
    const clamped = Math.max(bucketAnchor, Math.min(lastBucketStart + bucketWidth - 1, y));
    return String(bucketAnchor + Math.floor((clamped - bucketAnchor) / bucketWidth) * bucketWidth);
  }

  type DecadeData = {
    decade: string;
    total: number;
    segments: {
      method: string;
      y0: number;
      y1: number;
      proportion: number;
      count: number;
    }[];
  };

  const decadeProportions: DecadeData[] = $derived(
    decades.map((decade) => {
      const decadePapers = papers.filter((d) => getDecade(d.pub_year) === decade);
      const total = decadePapers.length;
      let cumulative = 0;
      const segments = methodCategories.map((method) => {
        const count = decadePapers.filter((d) => d.method === method).length;
        const proportion = total > 0 ? count / total : 0;
        const y0 = cumulative;
        cumulative += proportion;
        return { method, y0, y1: cumulative, proportion, count };
      });
      return { decade, total, segments };
    })
  );

  // Bar chart scales
  const xBand = scaleBand<string>()
    .domain([...decades])
    .range([barMargin.left, barWidth - barMargin.right])
    .padding(0.2);

  const yBar = scaleLinear()
    .domain([0, 1])
    .range([barHeight - barMargin.bottom, barMargin.top]);

  let selectedMethod: string | null = $state(null);

  function toggleMethod(method: string) {
    selectedMethod = selectedMethod === method ? null : method;
  }

  // Facet (small multiples) configuration
  const facetWidth = 300;
  const facetHeight = 80;
  const facetMargin = { top: 14, right: 8, bottom: 16, left: 30 };
  const facetInnerWidth = facetWidth - facetMargin.left - facetMargin.right;
  const facetInnerHeight = facetHeight - facetMargin.top - facetMargin.bottom;

  const facetX = scaleBand<string>()
    .domain([...decades])
    .range([0, facetInnerWidth])
    .padding(0.1);

  type MethodSeries = {
    method: string;
    max: number;
    points: { decade: string; proportion: number; count: number }[];
  };

  const methodSeries: MethodSeries[] = $derived.by(() => {
    return methodCategories.map((method) => {
      const points = decadeProportions.map((d) => {
        const seg = d.segments.find((s) => s.method === method);
        return {
          decade: d.decade,
          proportion: seg ? seg.proportion : 0,
          count: seg ? seg.count : 0,
        };
      });
      const max = points.reduce((m, p) => (p.proportion > m ? p.proportion : m), 0);
      return { method, max, points };
    });
  });

  // Shared y-domain across all facets so trends are visually comparable.
  // Round the global max up to the nearest 0.1 for a clean tick.
  const facetYMax = $derived(
    Math.min(1, Math.ceil(methodSeries.reduce((m, s) => (s.max > m ? s.max : m), 0) * 10) / 10)
  );
  const facetY = $derived(
    scaleLinear().domain([0, facetYMax]).range([facetInnerHeight, 0])
  );
  const facetYTicks = $derived([0, facetYMax / 2, facetYMax]);

  function bucketLabel(decade: string): string {
    const start = parseInt(decade, 10);
    const displayStart = start === bucketAnchor ? firstBucketMinYear : start;
    const end = start === lastBucketStart ? dataMaxYear : start + bucketWidth - 1;
    return `${displayStart}–${end}`;
  }

  function peakBucket(points: { decade: string; proportion: number }[]): string {
    let best = points[0];
    for (const p of points) {
      if (p.proportion > best.proportion) best = p;
    }
    return bucketLabel(best.decade);
  }

  function facetCx(decade: string): number {
    return (facetX(decade) ?? 0) + facetX.bandwidth() / 2;
  }

  // ---------------------------------------------------------------
  // Locations section
  // ---------------------------------------------------------------

  type Location = {
    doi: string;
    title: string;
    authors: string;
    pub_year: string;
    source: string;
    abstract: string;
    region: string;
  };

  const locations: Location[] = locationsData as Location[];

  const locationCategories = [
    'USA',
    'Asia',
    'Africa',
    'Europe',
    'South America',
    'Other North America',
    'multiple regions',
    'unclear or conceptual',
    'Australia/New Zealand/Pacific'
  ] as const;

  const locationColor = scaleOrdinal<string, string>()
    .domain(locationCategories as unknown as string[])
    .range(schemeTableau10);

  type DecadeRegionData = {
    decade: string;
    total: number;
    segments: {
      region: string;
      y0: number;
      y1: number;
      proportion: number;
      count: number;
    }[];
  };

  const decadeRegionProportions: DecadeRegionData[] = decades.map((decade) => {
    const decadeLocations = locations.filter((d) => getDecade(d.pub_year) === decade);
    const total = decadeLocations.length;
    let cumulative = 0;
    const segments = locationCategories.map((region) => {
      const count = decadeLocations.filter((d) => d.region === region).length;
      const proportion = total > 0 ? count / total : 0;
      const y0 = cumulative;
      cumulative += proportion;
      return { region, y0, y1: cumulative, proportion, count };
    });
    return { decade, total, segments };
  });

  let selectedRegion: string | null = $state(null);

  function toggleRegion(region: string) {
    selectedRegion = selectedRegion === region ? null : region;
  }

  type RegionSeries = {
    region: string;
    max: number;
    points: { decade: string; proportion: number; count: number }[];
  };

  const regionSeries: RegionSeries[] = $derived.by(() => {
    return locationCategories.map((region) => {
      const points = decadeRegionProportions.map((d) => {
        const seg = d.segments.find((s) => s.region === region);
        return {
          decade: d.decade,
          proportion: seg ? seg.proportion : 0,
          count: seg ? seg.count : 0,
        };
      });
      const max = points.reduce((m, p) => (p.proportion > m ? p.proportion : m), 0);
      return { region, max, points };
    });
  });

  const regionFacetYMax = $derived(
    Math.min(1, Math.ceil(regionSeries.reduce((m, s) => (s.max > m ? s.max : m), 0) * 10) / 10)
  );
  const regionFacetY = $derived(
    scaleLinear().domain([0, regionFacetYMax]).range([facetInnerHeight, 0])
  );
  const regionFacetYTicks = $derived([0, regionFacetYMax / 2, regionFacetYMax]);

  function peakRegionBucket(points: { decade: string; proportion: number }[]): string {
    let best = points[0];
    for (const p of points) {
      if (p.proportion > best.proportion) best = p;
    }
    return bucketLabel(best.decade);
  }

  // ---------------------------------------------------------------
  // Methods by region: USA vs non-USA
  // ---------------------------------------------------------------

  const nonUsRegions = new Set<string>([
    'Asia',
    'Africa',
    'Europe',
    'South America',
    'Other North America',
    'Australia/New Zealand/Pacific'
  ]);

  const regionByDoi: SvelteMap<string, string> = $derived.by(() => {
    const m = new SvelteMap<string, string>();
    for (const l of locations) m.set(l.doi, l.region);
    return m;
  });

  type Bucket = 'us' | 'nonUs' | 'excluded';

  function classifyBucket(doi: string): Bucket {
    const region = regionByDoi.get(doi);
    if (!region) return 'excluded';
    if (region === 'USA') return 'us';
    if (nonUsRegions.has(region)) return 'nonUs';
    return 'excluded';
  }

  const usPapers = $derived(papers.filter((p) => classifyBucket(p.doi) === 'us'));
  const nonUsPapers = $derived(papers.filter((p) => classifyBucket(p.doi) === 'nonUs'));

  function computeMethodSeries(subset: Paper[]): MethodSeries[] {
    const byDecade = decades.map((decade) => {
      const decadePapers = subset.filter((d) => getDecade(d.pub_year) === decade);
      const total = decadePapers.length;
      const counts = methodCategories.map((method) => ({
        method,
        count: decadePapers.filter((d) => d.method === method).length,
        total
      }));
      return { decade, counts };
    });
    return methodCategories.map((method) => {
      const points = byDecade.map((d) => {
        const entry = d.counts.find((c) => c.method === method);
        const count = entry ? entry.count : 0;
        const total = entry ? entry.total : 0;
        const proportion = total > 0 ? count / total : 0;
        return { decade: d.decade, proportion, count };
      });
      const max = points.reduce((m, p) => (p.proportion > m ? p.proportion : m), 0);
      return { method, max, points };
    });
  }

  const usMethodSeries: MethodSeries[] = $derived(computeMethodSeries(usPapers));
  const nonUsMethodSeries: MethodSeries[] = $derived(computeMethodSeries(nonUsPapers));

  const usColor = '#e15759';
  const nonUsColor = '#4e79a7';

  type CombinedMethodSeries = {
    method: string;
    us: MethodSeries;
    nonUs: MethodSeries;
  };

  const combinedMethodSeries: CombinedMethodSeries[] = $derived(
    methodCategories.map((method) => ({
      method,
      us: usMethodSeries.find((s) => s.method === method) as MethodSeries,
      nonUs: nonUsMethodSeries.find((s) => s.method === method) as MethodSeries
    }))
  );

  const compareYMax = $derived(
    Math.min(
      1,
      Math.ceil(
        Math.max(
          usMethodSeries.reduce((m, s) => (s.max > m ? s.max : m), 0),
          nonUsMethodSeries.reduce((m, s) => (s.max > m ? s.max : m), 0)
        ) * 10
      ) / 10
    )
  );
  const compareY = $derived(
    scaleLinear().domain([0, compareYMax]).range([facetInnerHeight, 0])
  );
  const compareYTicks = $derived([0, compareYMax / 2, compareYMax]);
  const compareTotal = $derived(usPapers.length + nonUsPapers.length);

  type UsNonUsBucket = 'USA' | 'Non-USA';

  type DecadeUsNonUs = {
    decade: string;
    total: number;
    segments: {
      bucket: UsNonUsBucket;
      y0: number;
      y1: number;
      proportion: number;
      count: number;
    }[];
  };

  const decadeUsNonUsProportions: DecadeUsNonUs[] = $derived(
    decades.map((decade) => {
      const usCount = usPapers.filter((d) => getDecade(d.pub_year) === decade).length;
      const nonUsCount = nonUsPapers.filter((d) => getDecade(d.pub_year) === decade).length;
      const total = usCount + nonUsCount;
      const usProp = total > 0 ? usCount / total : 0;
      const nonUsProp = total > 0 ? nonUsCount / total : 0;
      const segments: DecadeUsNonUs['segments'] = [
        { bucket: 'USA', y0: 0, y1: usProp, proportion: usProp, count: usCount },
        { bucket: 'Non-USA', y0: usProp, y1: usProp + nonUsProp, proportion: nonUsProp, count: nonUsCount }
      ];
      return { decade, total, segments };
    })
  );

  // ---------------------------------------------------------------
  // Topics section (multi-label)
  // ---------------------------------------------------------------

  type TopicPaper = {
    doi: string;
    title: string;
    authors: string;
    pub_year: string;
    source: string;
    keywords: string;
    abstract: string;
    topics: string[];
  };

  type ModelDef = {
    key: string;
    label: string;
    description: string;
    categories: { value: string; definition: string }[];
  };

  type RawPaper = {
    doi: string;
    title: string;
    authors: string;
    pub_year: string;
    source: string;
    keywords: string;
    abstract: string;
    topics: Record<string, string[]>;
  };

  const topicsViz = topicsData as unknown as { models: ModelDef[]; papers: RawPaper[] };
  const topicModels = topicsViz.models;

  // Selector state: which topic-model view to render. Defaults to the first
  // model in the JSON (currently cat14_granular).
  let topicModel: string = $state(topicModels[0].key);

  const currentModel: ModelDef = $derived(
    topicModels.find((m) => m.key === topicModel) ?? topicModels[0]
  );

  // Ordered by empirical frequency for the selected model (most common first).
  const topicCategories: string[] = $derived(
    currentModel.categories.map((c) => c.value)
  );

  // Per-category definitions from the model JSON.
  const topicDescriptions: Record<string, string> = $derived(
    Object.fromEntries(
      currentModel.categories.map((c) => [c.value, c.definition])
    ) as Record<string, string>
  );

  const topicPapers: TopicPaper[] = $derived(
    topicsViz.papers
      .filter((p) => (p.topics[topicModel] ?? []).length > 0)
      .map((p) => ({
        doi: p.doi,
        title: p.title,
        authors: p.authors,
        pub_year: p.pub_year,
        source: p.source,
        keywords: p.keywords,
        abstract: p.abstract,
        topics: p.topics[topicModel] ?? []
      }))
  );

  // Combine schemeTableau10 (10) + first 7 of schemeSet3 (pastel) — enough
  // distinct colours for the 17-category model and pleasant overflow for
  // smaller models.
  const topicColorRange = [...schemeTableau10, ...schemeSet3.slice(0, 7)];
  const topicColor = $derived(
    scaleOrdinal<string, string>().domain(topicCategories).range(topicColorRange)
  );

  // For each decade, segments stack the SHARE of all topic-instances assigned
  // to each topic. (Sums to 1.0 across topics in that decade.)
  // For facets, the per-decade y-value is the share of PAPERS in that decade
  // tagged with the topic — intuitive trend interpretation.

  type TopicDecadeData = {
    decade: string;
    n_papers: number;
    n_topic_instances: number;
    segments: {
      topic: string;
      y0: number;
      y1: number;
      proportion: number;
      count: number;
    }[];
  };

  const decadeTopicProportions: TopicDecadeData[] = $derived(
    decades.map((decade) => {
      const decadePapers = topicPapers.filter((d) => getDecade(d.pub_year) === decade);
      const counts = new Map<string, number>();
      for (const p of decadePapers) {
        for (const t of p.topics) counts.set(t, (counts.get(t) ?? 0) + 1);
      }
      const total_instances = [...counts.values()].reduce((a, b) => a + b, 0);
      let cumulative = 0;
      const segments = topicCategories.map((topic) => {
        const count = counts.get(topic) ?? 0;
        const proportion = total_instances > 0 ? count / total_instances : 0;
        const y0 = cumulative;
        cumulative += proportion;
        return { topic, y0, y1: cumulative, proportion, count };
      });
      return {
        decade,
        n_papers: decadePapers.length,
        n_topic_instances: total_instances,
        segments
      };
    })
  );

  let selectedTopic: string | null = $state(null);

  function toggleTopic(topic: string) {
    selectedTopic = selectedTopic === topic ? null : topic;
  }

  type CombinedPaper = {
    doi: string;
    title: string;
    authors: string;
    pub_year: string;
    source: string;
    abstract: string;
    method?: string;
    region?: string;
    topics: string[];
  };

  const combinedPapers: CombinedPaper[] = $derived.by(() => {
    const byDoi = new SvelteMap<string, CombinedPaper>();
    for (const p of papers) {
      byDoi.set(p.doi, {
        doi: p.doi,
        title: p.title,
        authors: p.authors,
        pub_year: p.pub_year,
        source: p.source,
        abstract: p.abstract,
        method: p.method,
        topics: []
      });
    }
    for (const l of locations) {
      const existing = byDoi.get(l.doi);
      if (existing) {
        existing.region = l.region;
      } else {
        byDoi.set(l.doi, {
          doi: l.doi,
          title: l.title,
          authors: l.authors,
          pub_year: l.pub_year,
          source: l.source,
          abstract: l.abstract,
          region: l.region,
          topics: []
        });
      }
    }
    for (const t of topicPapers) {
      const existing = byDoi.get(t.doi);
      if (existing) {
        existing.topics = t.topics;
      } else {
        byDoi.set(t.doi, {
          doi: t.doi,
          title: t.title,
          authors: t.authors,
          pub_year: t.pub_year,
          source: t.source,
          abstract: t.abstract,
          topics: t.topics
        });
      }
    }
    return [...byDoi.values()];
  });

  const filteredCombined: CombinedPaper[] = $derived.by(() => {
    if (selectedMethod === null && selectedRegion === null && selectedTopic === null) {
      return [];
    }
    return combinedPapers.filter((p) => {
      if (selectedMethod !== null && p.method !== selectedMethod) return false;
      if (selectedRegion !== null && p.region !== selectedRegion) return false;
      if (selectedTopic !== null && !p.topics.includes(selectedTopic)) return false;
      return true;
    });
  });

  function clearAllFilters() {
    selectedMethod = null;
    selectedRegion = null;
    selectedTopic = null;
  }

  let yearSortDir: 'asc' | 'desc' | null = $state(null);

  const sortedFiltered: CombinedPaper[] = $derived.by(() => {
    if (yearSortDir === null) return filteredCombined;
    const sign = yearSortDir === 'asc' ? 1 : -1;
    return [...filteredCombined].sort((a, b) => {
      const ay = parseInt(a.pub_year, 10);
      const by = parseInt(b.pub_year, 10);
      return (ay - by) * sign;
    });
  });

  function toggleYearSort() {
    yearSortDir = yearSortDir === 'asc' ? 'desc' : 'asc';
  }

  const yearSortIndicator = $derived(
    yearSortDir === 'asc' ? ' ▲' : yearSortDir === 'desc' ? ' ▼' : ''
  );

  type TopicSeries = {
    topic: string;
    max: number;
    points: { decade: string; proportion: number; count: number; n_papers: number }[];
  };

  // Per-paper proportion (= papers tagged with this topic in this decade /
  // total papers in this decade). Used for the facet trend lines.
  const topicSeries: TopicSeries[] = $derived.by(() => {
    return topicCategories.map((topic) => {
      const points = decades.map((decade) => {
        const decadePapers = topicPapers.filter((d) => getDecade(d.pub_year) === decade);
        const count = decadePapers.filter((d) => d.topics.includes(topic)).length;
        const n_papers = decadePapers.length;
        const proportion = n_papers > 0 ? count / n_papers : 0;
        return { decade, proportion, count, n_papers };
      });
      const max = points.reduce((m, p) => (p.proportion > m ? p.proportion : m), 0);
      return { topic, max, points };
    });
  });

  const topicFacetYMax = $derived(
    Math.min(1, Math.ceil(topicSeries.reduce((m, s) => (s.max > m ? s.max : m), 0) * 10) / 10)
  );
  const topicFacetY = $derived(
    scaleLinear().domain([0, topicFacetYMax]).range([facetInnerHeight, 0])
  );
  const topicFacetYTicks = $derived([0, topicFacetYMax / 2, topicFacetYMax]);

  // Toggle: when false, each topic facet auto-scales to its own max so small
  // labels (energy, weather, recreation) become readable. When true, all
  // facets share a global y-axis so cross-topic magnitudes are comparable.
  let topicSharedY: boolean = $state(true);

  function localYMax(seriesMax: number): number {
    // Round up to nearest 0.1 with a 0.1 floor so empty/near-empty series
    // don't render a 0-height plot.
    return Math.max(0.1, Math.min(1, Math.ceil(seriesMax * 10) / 10));
  }
  function localY(seriesMax: number) {
    return scaleLinear().domain([0, localYMax(seriesMax)]).range([facetInnerHeight, 0]);
  }
  function localYTicks(seriesMax: number): number[] {
    const m = localYMax(seriesMax);
    return [0, m / 2, m];
  }

  // ---------------------------------------------------------------
  // Topics by region: USA vs non-USA
  // ---------------------------------------------------------------

  const usTopicPapers = $derived(topicPapers.filter((p) => classifyBucket(p.doi) === 'us'));
  const nonUsTopicPapers = $derived(topicPapers.filter((p) => classifyBucket(p.doi) === 'nonUs'));

  function computeTopicSeriesFor(subset: TopicPaper[]): TopicSeries[] {
    return topicCategories.map((topic) => {
      const points = decades.map((decade) => {
        const decadePapers = subset.filter((d) => getDecade(d.pub_year) === decade);
        const count = decadePapers.filter((d) => d.topics.includes(topic)).length;
        const n_papers = decadePapers.length;
        const proportion = n_papers > 0 ? count / n_papers : 0;
        return { decade, proportion, count, n_papers };
      });
      const max = points.reduce((m, p) => (p.proportion > m ? p.proportion : m), 0);
      return { topic, max, points };
    });
  }

  const usTopicSeries: TopicSeries[] = $derived(computeTopicSeriesFor(usTopicPapers));
  const nonUsTopicSeries: TopicSeries[] = $derived(computeTopicSeriesFor(nonUsTopicPapers));

  type CombinedTopicSeries = {
    topic: string;
    us: TopicSeries;
    nonUs: TopicSeries;
  };

  const combinedTopicSeries: CombinedTopicSeries[] = $derived(
    topicCategories.map((topic) => ({
      topic,
      us: usTopicSeries.find((s) => s.topic === topic) as TopicSeries,
      nonUs: nonUsTopicSeries.find((s) => s.topic === topic) as TopicSeries
    }))
  );

  const compareTopicYMax = $derived(
    Math.min(
      1,
      Math.ceil(
        Math.max(
          usTopicSeries.reduce((m, s) => (s.max > m ? s.max : m), 0),
          nonUsTopicSeries.reduce((m, s) => (s.max > m ? s.max : m), 0)
        ) * 10
      ) / 10
    )
  );
  const compareTopicY = $derived(
    scaleLinear().domain([0, compareTopicYMax]).range([facetInnerHeight, 0])
  );
  const compareTopicYTicks = $derived([0, compareTopicYMax / 2, compareTopicYMax]);
  const compareTopicTotal = $derived(usTopicPapers.length + nonUsTopicPapers.length);

  const decadeUsNonUsTopicProportions: DecadeUsNonUs[] = $derived(
    decades.map((decade) => {
      const usCount = usTopicPapers.filter((d) => getDecade(d.pub_year) === decade).length;
      const nonUsCount = nonUsTopicPapers.filter((d) => getDecade(d.pub_year) === decade).length;
      const total = usCount + nonUsCount;
      const usProp = total > 0 ? usCount / total : 0;
      const nonUsProp = total > 0 ? nonUsCount / total : 0;
      const segments: DecadeUsNonUs['segments'] = [
        { bucket: 'USA', y0: 0, y1: usProp, proportion: usProp, count: usCount },
        { bucket: 'Non-USA', y0: usProp, y1: usProp + nonUsProp, proportion: nonUsProp, count: nonUsCount }
      ];
      return { decade, total, segments };
    })
  );

  // UpSet plot: which topic combinations (sets) recur most often.
  // Each paper has a unique topic-set (sorted, deduplicated); we count
  // occurrences of each unique set and rank by frequency.
  type IntersectionRow = {
    setKey: string;
    members: Set<string>;
    count: number;
  };

  const topicIntersections: IntersectionRow[] = $derived.by(() => {
    const buckets = new Map<string, { members: Set<string>; count: number }>();
    for (const p of topicPapers) {
      const validTopics = p.topics.filter((t) => topicCategories.includes(t));
      if (validTopics.length === 0) continue;
      const sorted = [...validTopics].sort();
      const key = sorted.join('|');
      const entry = buckets.get(key);
      if (entry) entry.count += 1;
      else buckets.set(key, { members: new Set(sorted), count: 1 });
    }
    return [...buckets.entries()]
      .map(([setKey, v]) => ({ setKey, members: v.members, count: v.count }))
      .sort((a, b) => b.count - a.count);
  });

  // Top 25 intersections (hardcoded)
  const UPSET_TOP_N = 25;
  const topIntersections = $derived(
    topicIntersections.slice(0, Math.min(UPSET_TOP_N, topicIntersections.length))
  );

  const upsetMaxCount = $derived(
    topIntersections.length > 0 ? topIntersections[0].count : 1
  );

  // Topic totals (set sizes): how many papers have each topic at all
  const topicSetTotals = $derived.by(() => {
    const m = new Map<string, number>();
    for (const p of topicPapers) {
      for (const t of p.topics) m.set(t, (m.get(t) ?? 0) + 1);
    }
    return m;
  });

  const setTotalMax = $derived(
    Math.max(...topicCategories.map((t) => topicSetTotals.get(t) ?? 0), 1)
  );

  // Click an intersection bar → filter papers to that exact topic set
  let upsetSelected: string | null = $state(null);

  const upsetSelectedPapers = $derived(
    upsetSelected !== null
      ? topicPapers.filter((p) => {
          const validTopics = p.topics.filter((t) => topicCategories.includes(t));
          return [...validTopics].sort().join('|') === upsetSelected;
        })
      : []
  );

  const upsetSelectedMembers = $derived(
    upsetSelected !== null
      ? topicIntersections.find((r) => r.setKey === upsetSelected)?.members
      : null
  );

  function toggleUpset(setKey: string) {
    upsetSelected = upsetSelected === setKey ? null : setKey;
  }

  // UpSet geometry
  const upsetCellSize = 22;
  const upsetIntersectionBarHeight = 120;
  const upsetSetBarWidth = 80;
  const upsetTopicLabelWidth = 160;
  const upsetMargin = { top: 12, right: 16, bottom: 20, left: 8 };
  const upsetMatrixWidth = $derived(upsetCellSize * topIntersections.length);
  const upsetMatrixHeight = $derived(upsetCellSize * topicCategories.length);
  const upsetWidth = $derived(
    upsetMargin.left + upsetTopicLabelWidth + upsetSetBarWidth + upsetMatrixWidth + upsetMargin.right
  );
  const upsetHeight = $derived(
    upsetMargin.top + upsetIntersectionBarHeight + 8 + upsetMatrixHeight + upsetMargin.bottom
  );
  const upsetMatrixLeft = $derived(upsetMargin.left + upsetTopicLabelWidth + upsetSetBarWidth);
  const upsetMatrixTop = upsetMargin.top + upsetIntersectionBarHeight + 8;

  function upsetBarHeight(count: number): number {
    return (count / upsetMaxCount) * upsetIntersectionBarHeight;
  }
  function upsetSetBarWidthScale(count: number): number {
    return (count / setTotalMax) * upsetSetBarWidth;
  }

  // Pairwise co-occurrence matrix: cell (i, j) = papers tagged with BOTH
  // topicCategories[i] AND topicCategories[j]. Diagonal = topic frequency.
  type CoocCell = {
    rowTopic: string;
    colTopic: string;
    count: number;
  };

  const topicCooccurrence: CoocCell[][] = $derived.by(() => {
    const idx = new Map<string, number>(
      topicCategories.map((t, i) => [t as string, i])
    );
    const n = topicCategories.length;
    const grid: number[][] = Array.from({ length: n }, () => Array(n).fill(0));
    for (const p of topicPapers) {
      const validIdxs = p.topics
        .map((t) => idx.get(t))
        .filter((i): i is number => typeof i === 'number');
      for (const i of validIdxs) for (const j of validIdxs) grid[i][j] += 1;
    }
    const out: CoocCell[][] = [];
    for (let i = 0; i < n; i++) {
      const row: CoocCell[] = [];
      for (let j = 0; j < n; j++) {
        row.push({
          rowTopic: topicCategories[i],
          colTopic: topicCategories[j],
          count: grid[i][j]
        });
      }
      out.push(row);
    }
    return out;
  });

  // Heatmap intensity is driven by off-diagonal max so the diagonal
  // (which equals total topic frequency) doesn't compress the off-diagonal
  // color range.
  const coocOffDiagMax: number = $derived.by(() => {
    let m = 0;
    for (let i = 0; i < topicCategories.length; i++) {
      for (let j = 0; j < topicCategories.length; j++) {
        if (i === j) continue;
        if (topicCooccurrence[i][j].count > m) m = topicCooccurrence[i][j].count;
      }
    }
    return m === 0 ? 1 : m;
  });

  // Phi coefficient (Pearson correlation for binary variables).
  // For 2×2 contingency: φ = (ad - bc) / √((a+b)(c+d)(a+c)(b+d))
  // where a = both, b = i only, c = j only, d = neither.
  // Range [-1, 1]. Positive = tags appear together more than chance;
  // negative = tags appear together less than chance.
  const topicPhi: number[][] = $derived.by(() => {
    const n = topicCategories.length;
    const N = topicPapers.length;
    const totals = topicCategories.map((t) => topicSetTotals.get(t) ?? 0);
    const m: number[][] = Array.from({ length: n }, () => Array(n).fill(0));
    for (let i = 0; i < n; i++) {
      m[i][i] = 1;
      for (let j = 0; j < n; j++) {
        if (i === j) continue;
        const a = topicCooccurrence[i][j].count;
        const ni = totals[i];
        const nj = totals[j];
        const b = ni - a;
        const c = nj - a;
        const d = N - a - b - c;
        const denom = Math.sqrt((a + b) * (c + d) * (a + c) * (b + d));
        m[i][j] = denom === 0 ? 0 : (a * d - b * c) / denom;
      }
    }
    return m;
  });

  let coocMode: 'count' | 'phi' = $state('count');

  // Heatmap row/column ordering — only affects the cooc heatmap, not the
  // other charts. "cluster" runs agglomerative hierarchical clustering on
  // (1 − phi) with average linkage and uses the resulting leaf order so
  // strongly-associated topics land adjacent — surfaces block structure.
  let coocSort: 'frequency' | 'alphabetical' | 'cluster' = $state('frequency');

  const heatmapOrder: number[] = $derived.by(() => {
    const n = topicCategories.length;
    if (coocSort === 'frequency') return topicCategories.map((_, i) => i);
    if (coocSort === 'alphabetical') {
      return topicCategories
        .map((t, i) => ({ t, i }))
        .sort((a, b) => a.t.localeCompare(b.t))
        .map((x) => x.i);
    }
    // cluster: agglomerative hierarchical (average linkage) on 1 − φ
    const distance: number[][] = topicPhi.map((row) => row.map((v) => 1 - v));
    let clusters: number[][] = topicCategories.map((_, i) => [i]);
    while (clusters.length > 1) {
      let bestD = Infinity;
      let bestA = 0;
      let bestB = 1;
      for (let a = 0; a < clusters.length; a++) {
        for (let b = a + 1; b < clusters.length; b++) {
          let total = 0;
          let pairs = 0;
          for (const i of clusters[a]) {
            for (const j of clusters[b]) {
              total += distance[i][j];
              pairs += 1;
            }
          }
          const d = pairs > 0 ? total / pairs : Infinity;
          if (d < bestD) {
            bestD = d;
            bestA = a;
            bestB = b;
          }
        }
      }
      const merged = [...clusters[bestA], ...clusters[bestB]];
      clusters = [
        ...clusters.filter((_, k) => k !== bestA && k !== bestB),
        merged
      ];
    }
    return clusters[0] ?? topicCategories.map((_, i) => i);
  });

  type CoocSelection = { rowTopic: string; colTopic: string };
  let coocSelected: CoocSelection | null = $state(null);

  const coocSelectedPapers = $derived(
    coocSelected !== null
      ? topicPapers.filter(
          (d) =>
            d.topics.includes(coocSelected!.rowTopic) &&
            d.topics.includes(coocSelected!.colTopic)
        )
      : []
  );

  function toggleCooc(rowTopic: string, colTopic: string, count: number) {
    if (count === 0) return;
    if (
      coocSelected &&
      coocSelected.rowTopic === rowTopic &&
      coocSelected.colTopic === colTopic
    ) {
      coocSelected = null;
      return;
    }
    coocSelected = { rowTopic, colTopic };
  }

  // Stats for the selected cell: contingency (a/b/c/d), point φ, χ² with 1 df,
  // two-sided p-value, and a 95% bootstrap CI for φ. Bootstrap resamples paper
  // indices with replacement and recomputes φ each draw, then takes the
  // 2.5/97.5 percentiles. Chi-square with 1 df has p = 2·Φ̄(√χ²), where Φ̄ is
  // the standard normal survival function (Abramowitz & Stegun 26.2.17).
  type CoocStats = {
    n: number;
    a: number; b: number; c: number; d: number;
    phi: number;
    chi2: number;
    pValue: number;
    ciLow: number;
    ciHigh: number;
  };

  function phiFromCounts(a: number, b: number, c: number, d: number): number {
    const denom = Math.sqrt((a + b) * (c + d) * (a + c) * (b + d));
    return denom === 0 ? 0 : (a * d - b * c) / denom;
  }

  function normalSF(z: number): number {
    if (z < 0) return 1 - normalSF(-z);
    const t = 1 / (1 + 0.2316419 * z);
    const d = 0.3989422804 * Math.exp(-0.5 * z * z);
    return (
      d *
      t *
      (0.319381530 +
        t *
          (-0.356563782 +
            t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    );
  }

  function chi2pValue1df(chi2: number): number {
    if (chi2 <= 0) return 1;
    return 2 * normalSF(Math.sqrt(chi2));
  }

  const BOOTSTRAP_N = 1000;

  const coocSelectedStats: CoocStats | null = $derived.by(() => {
    if (coocSelected === null) return null;
    const row = coocSelected.rowTopic;
    const col = coocSelected.colTopic;
    const N = topicPapers.length;
    const inRow = new Uint8Array(N);
    const inCol = new Uint8Array(N);
    for (let i = 0; i < N; i++) {
      const t = topicPapers[i].topics;
      inRow[i] = t.includes(row) ? 1 : 0;
      inCol[i] = t.includes(col) ? 1 : 0;
    }
    let a = 0, b = 0, c = 0, d = 0;
    for (let i = 0; i < N; i++) {
      if (inRow[i] && inCol[i]) a++;
      else if (inRow[i]) b++;
      else if (inCol[i]) c++;
      else d++;
    }
    const phi = phiFromCounts(a, b, c, d);
    const chi2 = N * phi * phi;
    const pValue = chi2pValue1df(chi2);
    const phis = new Float64Array(BOOTSTRAP_N);
    for (let it = 0; it < BOOTSTRAP_N; it++) {
      let ba = 0, bb = 0, bc = 0, bd = 0;
      for (let i = 0; i < N; i++) {
        const idx = (Math.random() * N) | 0;
        if (inRow[idx] && inCol[idx]) ba++;
        else if (inRow[idx]) bb++;
        else if (inCol[idx]) bc++;
        else bd++;
      }
      phis[it] = phiFromCounts(ba, bb, bc, bd);
    }
    phis.sort();
    const ciLow = phis[Math.floor(BOOTSTRAP_N * 0.025)];
    const ciHigh = phis[Math.floor(BOOTSTRAP_N * 0.975)];
    return { n: N, a, b, c, d, phi, chi2, pValue, ciLow, ciHigh };
  });

  function fmtP(p: number): string {
    if (p < 1e-7) return '< 10⁻⁷';
    if (p < 1e-4) return p.toExponential(1);
    if (p < 0.001) return '< 0.001';
    if (p < 0.01) return p.toFixed(3);
    return p.toFixed(3);
  }

  function coocCellFill(i: number, j: number, count: number): string {
    if (i === j) return '#e8e8e8'; // diagonal de-emphasized
    if (coocMode === 'count') {
      if (count === 0) return '#fafafa';
      const opacity = Math.max(0.08, Math.min(1, count / coocOffDiagMax));
      return `rgba(46, 92, 158, ${opacity})`;
    }
    // phi mode — diverging colour: blue for positive, red for negative
    const phi = topicPhi[i][j];
    if (phi === 0) return '#fafafa';
    // amplify since |phi| is usually < 0.5 even for strong associations
    const opacity = Math.max(0.08, Math.min(1, Math.abs(phi) * 2.5));
    return phi >= 0
      ? `rgba(46, 92, 158, ${opacity})`
      : `rgba(190, 70, 70, ${opacity})`;
  }

  function coocCellLabel(i: number, j: number, count: number): string {
    if (i === j) return String(count);
    if (coocMode === 'count') return count > 0 ? String(count) : '';
    const phi = topicPhi[i][j];
    return Math.abs(phi) >= 0.05 ? phi.toFixed(2) : '';
  }

  function coocCellTextFill(i: number, j: number, count: number): string {
    if (i === j) return '#666';
    if (coocMode === 'count') {
      return count / coocOffDiagMax > 0.55 ? 'white' : '#222';
    }
    const phi = topicPhi[i][j];
    return Math.abs(phi) * 2.5 > 0.55 ? 'white' : '#222';
  }

  // Heatmap geometry
  const coocCellSize = 34;
  const coocMargin = { top: 140, right: 16, bottom: 16, left: 160 };
  const coocInnerSize = $derived(coocCellSize * topicCategories.length);
  const coocWidth = $derived(coocMargin.left + coocInnerSize + coocMargin.right);
  const coocHeight = $derived(coocMargin.top + coocInnerSize + coocMargin.bottom);

  // ---------------------------------------------------------------
  // Anchor-topic co-occurrence over time
  // ---------------------------------------------------------------
  // Pick an anchor topic; for each other topic, show the fraction of
  // anchor papers (in each decade) that ALSO had that co-topic. Same
  // facet idiom as the topic-trends section so visual conventions carry.

  let anchorTopic: string = $state('social power');

  // If the user switches model and the previously-anchored topic isn't in the
  // new category list, fall back to the first category.
  const effectiveAnchor: string = $derived(
    topicCategories.includes(anchorTopic) ? anchorTopic : topicCategories[0]
  );

  type AnchorSeries = {
    coTopic: string;
    max: number;
    overall: number;
    phi: number;
    points: { decade: string; proportion: number; numerator: number; denominator: number }[];
  };

  let anchorSort = $state<'overall' | 'phi' | 'absphi'>('overall');

  const anchorSeries: AnchorSeries[] = $derived.by(() => {
    const anchor = effectiveAnchor;
    const anchorIdx = topicCategories.indexOf(anchor);
    const decadeBuckets = new Map<string, TopicPaper[]>();
    for (const p of topicPapers) {
      if (!p.topics.includes(anchor)) continue;
      const d = getDecade(p.pub_year);
      const arr = decadeBuckets.get(d);
      if (arr) arr.push(p);
      else decadeBuckets.set(d, [p]);
    }
    const totalAnchorPapers = [...decadeBuckets.values()].reduce(
      (a, arr) => a + arr.length,
      0
    );
    const series = topicCategories
      .filter((t) => t !== anchor)
      .map((coTopic) => {
        let overallCo = 0;
        const points = decades.map((d) => {
          const inBucket = decadeBuckets.get(d) ?? [];
          const denominator = inBucket.length;
          const numerator = inBucket.filter((p) => p.topics.includes(coTopic)).length;
          overallCo += numerator;
          const proportion = denominator > 0 ? numerator / denominator : 0;
          return { decade: d, proportion, numerator, denominator };
        });
        const max = points.reduce((m, p) => (p.proportion > m ? p.proportion : m), 0);
        const overall = totalAnchorPapers > 0 ? overallCo / totalAnchorPapers : 0;
        const coIdx = topicCategories.indexOf(coTopic);
        const phi = anchorIdx >= 0 && coIdx >= 0 ? topicPhi[anchorIdx][coIdx] : 0;
        return { coTopic, max, overall, phi, points };
      });
    if (anchorSort === 'phi') {
      series.sort((a, b) => b.phi - a.phi);
    } else if (anchorSort === 'absphi') {
      series.sort((a, b) => Math.abs(b.phi) - Math.abs(a.phi));
    } else {
      series.sort((a, b) => b.overall - a.overall);
    }
    return series;
  });

  const anchorTotalPapers = $derived(
    topicPapers.filter((p) => p.topics.includes(effectiveAnchor)).length
  );

  let anchorSharedY: boolean = $state(true);

  const anchorFacetYMax = $derived(
    Math.min(1, Math.ceil(anchorSeries.reduce((m, s) => (s.max > m ? s.max : m), 0) * 10) / 10)
  );
  const anchorFacetY = $derived(
    scaleLinear().domain([0, anchorFacetYMax]).range([facetInnerHeight, 0])
  );
  const anchorFacetYTicks = $derived([0, anchorFacetYMax / 2, anchorFacetYMax]);

  function peakAnchorBucket(points: { decade: string; proportion: number }[]): string {
    let best = points[0];
    for (const p of points) {
      if (p.proportion > best.proportion) best = p;
    }
    return bucketLabel(best.decade);
  }

  function peakTopicBucket(points: { decade: string; proportion: number }[]): string {
    let best = points[0];
    for (const p of points) {
      if (p.proportion > best.proportion) best = p;
    }
    return bucketLabel(best.decade);
  }

  // Per-label F1 delta: cat14 (granular preds collapsed via parent map) vs cat16
  // scored against the same n_shared papers in the cat16 12-bucket label space.
  type CompareRow = {
    label: string;
    support_gt: number;
    base: { p: number; r: number; f1: number; support_pred: number };
    new: { p: number; r: number; f1: number; support_pred: number };
    delta_f1: number;
  };
  const compareRows: CompareRow[] = [...(topicCompare.per_label as CompareRow[])]
    .sort((a, b) => a.delta_f1 - b.delta_f1);

  const compareChartWidth = 520;
  const compareLabelGutter = 180;
  const compareRowHeight = 22;
  const compareChartHeight = compareRows.length * compareRowHeight + 28;
  const compareMaxAbsDelta = Math.max(
    0.05,
    ...compareRows.map((r) => Math.abs(r.delta_f1))
  );
  const compareBarWidth = compareChartWidth - compareLabelGutter - 70;
  const compareZeroX = compareLabelGutter + compareBarWidth / 2;
  const compareDeltaScale = scaleLinear()
    .domain([-compareMaxAbsDelta, compareMaxAbsDelta])
    .range([compareLabelGutter, compareLabelGutter + compareBarWidth]);
  const compareJaccardDelta = topicCompare.new_jaccard - topicCompare.base_jaccard;

  // Overview shows the raw corpus count, independent of which methods model is
  // selected — pre-1992 papers exist even when sections_baseline has no coverage.
  const totalByDecade = decades.map((decade) => ({
    decade,
    count: methodsViz.papers.filter((p) => getDecade(p.pub_year) === decade).length
  }));
  const totalByDecadeMax = Math.max(...totalByDecade.map((d) => d.count), 1);
  const overviewWidth = 620;
  const overviewHeight = 180;
  const overviewMargin = { top: 20, right: 20, bottom: 32, left: 48 };
  const overviewX = scaleBand<string>()
    .domain([...decades])
    .range([overviewMargin.left, overviewWidth - overviewMargin.right])
    .padding(0.2);
  const overviewY = scaleLinear()
    .domain([0, totalByDecadeMax])
    .range([overviewHeight - overviewMargin.bottom, overviewMargin.top]);
</script>

<svg width="0" height="0" style="position: absolute;" aria-hidden="true">
  <defs>
    <pattern id="lowDataHatch-shared" patternUnits="userSpaceOnUse" width="6" height="6">
      <path d="M-1,1 l2,-2 M0,6 l6,-6 M5,7 l2,-2" stroke="#666" stroke-width="0.8" />
    </pattern>
  </defs>
</svg>

<!--
  Shared bar-chart / facet snippets — reduce repetition across the page.
  All inputs (xBand, yBar, barWidth, barHeight, barMargin, decades, facetX,
  facetCx, facetInnerHeight, lowConfidenceBuckets, lowConfidenceTitle,
  bucketLabel) are module-level constants in the <script> block.
-->
{#snippet barYAxisTicks()}
  {#each [0, 0.25, 0.5, 0.75, 1.0] as tick (tick)}
    <line
      x1={barMargin.left}
      x2={barWidth - barMargin.right}
      y1={yBar(tick)}
      y2={yBar(tick)}
      stroke="#e0e0e0"
      stroke-width="1"
    />
    <text
      x={barMargin.left - 8}
      y={yBar(tick) + 4}
      text-anchor="end"
      font-size="11"
      fill="#666"
    >{tick}</text>
  {/each}
{/snippet}

{#snippet barXAxisLabels()}
  {#each decades as decade (decade)}
    <text
      x={(xBand(decade) ?? 0) + xBand.bandwidth() / 2}
      y={barHeight - barMargin.bottom + 20}
      text-anchor="middle"
      font-size="12"
      fill="#333"
    >{bucketLabel(decade)}</text>
  {/each}
{/snippet}

{#snippet barXAxisTitle()}
  <text
    x={(barMargin.left + barWidth - barMargin.right) / 2}
    y={barHeight - 8}
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Year (5-year buckets)</text>
{/snippet}

{#snippet facetHatchOverlay()}
  {#each [...lowConfidenceBuckets] as lc (lc)}
    {@const lcX = facetX(lc)}
    {@const lcIdx = (decades as readonly string[]).indexOf(lc)}
    {#if lcX !== undefined}
      {@const lcWidth = lcIdx >= 0 && lcIdx < decades.length - 1 ? facetCx(decades[lcIdx + 1]) - lcX : facetX.bandwidth()}
      <rect
        x={lcX}
        y={0}
        width={lcWidth}
        height={facetInnerHeight}
        fill="url(#lowDataHatch-shared)"
        opacity="0.45"
        pointer-events="none"
      >
        <title>{lowConfidenceTitle}</title>
      </rect>
    {/if}
  {/each}
{/snippet}

<h2>Overview (1986–2026)</h2>

<button type="button" class="export-btn" onclick={() => exportPng(overviewRef, 'overview_total_papers')}>⬇ PNG</button>
<svg bind:this={overviewRef} width={overviewWidth} height={overviewHeight} class="overview-chart" aria-label="Total papers per 5-year bucket">
  <text
    x={-(overviewHeight / 2)}
    y={14}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="11"
    fill="#666"
  >Papers</text>

  {#each overviewY.ticks(4) as tick (tick)}
    <line
      x1={overviewMargin.left}
      x2={overviewWidth - overviewMargin.right}
      y1={overviewY(tick)}
      y2={overviewY(tick)}
      stroke="#eee"
      stroke-width="1"
    />
    <text
      x={overviewMargin.left - 6}
      y={overviewY(tick) + 3}
      text-anchor="end"
      font-size="10"
      fill="#888"
    >{tick}</text>
  {/each}

  {#each totalByDecade as { decade, count } (decade)}
    {@const x = overviewX(decade) ?? 0}
    {@const bw = overviewX.bandwidth()}
    {@const yTop = overviewY(count)}
    {@const h = overviewY(0) - yTop}
    <rect x={x} y={yTop} width={bw} height={h} fill="#888" opacity="0.85" />
    <text
      x={x + bw / 2}
      y={yTop - 4}
      text-anchor="middle"
      font-size="10"
      fill="#333"
    >{count}</text>
    <text
      x={x + bw / 2}
      y={overviewHeight - overviewMargin.bottom + 14}
      text-anchor="middle"
      font-size="11"
      fill="#333"
    >{bucketLabel(decade)}</text>
  {/each}

</svg>


<div bind:this={methodsStackedHeaderRef}>
<h2>Methods classification across rural geography (1986–2026)</h2>
<p class="caption">
  Methods predicted on {papers.length} papers across {methodCategories.length} categories using the selected model below. The 2022–2026 bucket includes partial 2026.
</p>

<div class="facet-controls">
  <span class="control-label">Methods model:</span>
  {#each methodModels as m (m.key)}
    <button
      type="button"
      class="toggle-btn"
      class:active={methodModel === m.key}
      onclick={() => (methodModel = m.key)}
    >{m.label}</button>
  {/each}
</div>
<p class="caption">{currentMethodModel.description}</p>

<div class="legend">
  {#each methodCategories as method (method)}
    <div class="legend-cell">
      <button
        type="button"
        class="legend-item"
        class:dimmed={selectedMethod !== null && selectedMethod !== method}
        onclick={() => toggleMethod(method)}
      >
        <span class="swatch" style="background: {color(method)};"></span>
        <span class="label">{method}</span>
      </button>
      <div class="legend-desc" role="tooltip">{methodDescriptions[method]}</div>
    </div>
  {/each}
</div>
</div>

<div class="charts-row">
<button type="button" class="export-btn" onclick={() => exportPng(methodsStackedRef, 'methods_stacked', methodsStackedHeaderRef)}>⬇ PNG</button>
<svg bind:this={methodsStackedRef} width={barWidth} height={barHeight} class="bar-chart">
  <!-- Y-axis label -->
  <text
    x={-(barHeight / 2)}
    y={16}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Proportion</text>

  {@render barYAxisTicks()}

  <!-- Stacked bars -->
  {#each decadeProportions as { decade, segments } (decade)}
    {#each segments as seg (seg.method)}
      {#if seg.proportion > 0}
        {@const x = xBand(decade) ?? 0}
        {@const bw = xBand.bandwidth()}
        {@const yTop = yBar(seg.y1)}
        {@const h = yBar(seg.y0) - yBar(seg.y1)}
        <rect
          x={x}
          y={yTop}
          width={bw}
          height={h}
          fill={color(seg.method)}
          opacity={selectedMethod !== null && seg.method !== selectedMethod ? 0.15 : 0.85}
          role="button"
          tabindex="-1"
          aria-label="{seg.method}, {decade}"
          onclick={() => toggleMethod(seg.method)}
          onkeydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') toggleMethod(seg.method);
          }}
          style="cursor: pointer;"
        />
        {#if seg.proportion > 0.06}
          <text
            x={x + bw / 2}
            y={yTop + h / 2 + 4}
            text-anchor="middle"
            font-size="11"
            fill="white"
            pointer-events="none"
          >n={seg.count}</text>
        {/if}
      {/if}
    {/each}
  {/each}

  {@render barXAxisLabels()}
  {@render barXAxisTitle()}
</svg>

<button type="button" class="export-btn" onclick={() => exportPng(methodsFacetsRef, 'methods_facets')}>⬇ PNG</button>
<section bind:this={methodsFacetsRef} class="facets" aria-label="Method proportion over time">
  {#each methodSeries as series (series.method)}
    {@const dimmed = selectedMethod !== null && selectedMethod !== series.method}
    {@const maxPct = (series.max * 100).toFixed(0)}
    <button
      type="button"
      class="facet"
      class:dimmed
      onclick={() => toggleMethod(series.method)}
      aria-label="{series.method} proportion over time: peak {maxPct}% in {peakBucket(series.points)}"
    >
      <div class="facet-header">
        <span class="swatch small" style="background: {color(series.method)};"></span>
        <span class="facet-name">{series.method}</span>
        <span class="facet-max">· peak {maxPct}%</span>
      </div>
      <svg width={facetWidth} height={facetHeight} class="facet-svg">
        <g transform="translate({facetMargin.left},{facetMargin.top})">
          {@render facetHatchOverlay()}
          {#each facetYTicks as t (t)}
            <line
              x1={0}
              x2={facetInnerWidth}
              y1={facetY(t)}
              y2={facetY(t)}
              stroke="#eee"
              stroke-width="1"
            />
            <text
              x={-4}
              y={facetY(t) + 3}
              text-anchor="end"
              font-size="9"
              fill="#888"
            >{(t * 100).toFixed(0)}%</text>
          {/each}
          {#if series.max > 0}
            {@const pathD = series.points
              .map((p, i) => `${i === 0 ? 'M' : 'L'} ${facetCx(p.decade)} ${facetY(p.proportion)}`)
              .join(' ')}
            <path
              d={pathD}
              fill="none"
              stroke={color(series.method)}
              stroke-width="1.5"
              opacity={dimmed ? 0.15 : 0.9}
            />
            {#each series.points as p (p.decade)}
              <circle
                cx={facetCx(p.decade)}
                cy={facetY(p.proportion)}
                r="2.5"
                fill={color(series.method)}
                opacity={dimmed ? 0.15 : 0.9}
              />
            {/each}
          {/if}
        </g>
        <g transform="translate({facetMargin.left},{facetMargin.top + facetInnerHeight})">
          <text
            x={facetCx(decades[0])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[0]}</text>
          <text
            x={facetCx(decades[decades.length - 1])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[decades.length - 1]}</text>
        </g>
      </svg>
    </button>
  {/each}
</section>
</div>

<div bind:this={regionsStackedHeaderRef}>
<h2 class="section-h2">Region across rural geography (1986–2026)</h2>
<p class="caption">
  Predicted on {locations.length} papers (snapshot: 2026-05-20_2325_location_v3_abstract).
</p>

<div class="legend">
  {#each locationCategories as region (region)}
    <button
      type="button"
      class="legend-item"
      class:dimmed={selectedRegion !== null && selectedRegion !== region}
      onclick={() => toggleRegion(region)}
    >
      <span class="swatch" style="background: {locationColor(region)};"></span>
      <span class="label">{region}</span>
    </button>
  {/each}
</div>
</div>

<div class="charts-row">
<button type="button" class="export-btn" onclick={() => exportPng(regionsStackedRef, 'regions_stacked', regionsStackedHeaderRef)}>⬇ PNG</button>
<svg bind:this={regionsStackedRef} width={barWidth} height={barHeight} class="bar-chart">
  <!-- Y-axis label -->
  <text
    x={-(barHeight / 2)}
    y={16}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Proportion</text>

  {@render barYAxisTicks()}

  <!-- Stacked bars -->
  {#each decadeRegionProportions as { decade, segments } (decade)}
    {#each segments as seg (seg.region)}
      {#if seg.proportion > 0}
        {@const x = xBand(decade) ?? 0}
        {@const bw = xBand.bandwidth()}
        {@const yTop = yBar(seg.y1)}
        {@const h = yBar(seg.y0) - yBar(seg.y1)}
        <rect
          x={x}
          y={yTop}
          width={bw}
          height={h}
          fill={locationColor(seg.region)}
          opacity={selectedRegion !== null && seg.region !== selectedRegion ? 0.15 : 0.85}
          role="button"
          tabindex="-1"
          aria-label="{seg.region}, {decade}"
          onclick={() => toggleRegion(seg.region)}
          onkeydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') toggleRegion(seg.region);
          }}
          style="cursor: pointer;"
        />
        {#if seg.proportion > 0.06}
          <text
            x={x + bw / 2}
            y={yTop + h / 2 + 4}
            text-anchor="middle"
            font-size="11"
            fill="white"
            pointer-events="none"
          >n={seg.count}</text>
        {/if}
      {/if}
    {/each}
  {/each}

  {@render barXAxisLabels()}
  {@render barXAxisTitle()}
</svg>

<button type="button" class="export-btn" onclick={() => exportPng(regionsFacetsRef, 'regions_facets')}>⬇ PNG</button>
<section bind:this={regionsFacetsRef} class="facets" aria-label="Region proportion over time">
  {#each regionSeries as series (series.region)}
    {@const dimmed = selectedRegion !== null && selectedRegion !== series.region}
    {@const maxPct = (series.max * 100).toFixed(0)}
    <button
      type="button"
      class="facet"
      class:dimmed
      onclick={() => toggleRegion(series.region)}
      aria-label="{series.region} proportion over time: peak {maxPct}% in {peakRegionBucket(series.points)}"
    >
      <div class="facet-header">
        <span class="swatch small" style="background: {locationColor(series.region)};"></span>
        <span class="facet-name">{series.region}</span>
        <span class="facet-max">· peak {maxPct}%</span>
      </div>
      <svg width={facetWidth} height={facetHeight} class="facet-svg">
        <g transform="translate({facetMargin.left},{facetMargin.top})">
          {@render facetHatchOverlay()}
          {#each regionFacetYTicks as t (t)}
            <line
              x1={0}
              x2={facetInnerWidth}
              y1={regionFacetY(t)}
              y2={regionFacetY(t)}
              stroke="#eee"
              stroke-width="1"
            />
            <text
              x={-4}
              y={regionFacetY(t) + 3}
              text-anchor="end"
              font-size="9"
              fill="#888"
            >{(t * 100).toFixed(0)}%</text>
          {/each}
          {#if series.max > 0}
            {@const pathD = series.points
              .map((p, i) => `${i === 0 ? 'M' : 'L'} ${facetCx(p.decade)} ${regionFacetY(p.proportion)}`)
              .join(' ')}
            <path
              d={pathD}
              fill="none"
              stroke={locationColor(series.region)}
              stroke-width="1.5"
              opacity={dimmed ? 0.15 : 0.9}
            />
            {#each series.points as p (p.decade)}
              <circle
                cx={facetCx(p.decade)}
                cy={regionFacetY(p.proportion)}
                r="2.5"
                fill={locationColor(series.region)}
                opacity={dimmed ? 0.15 : 0.9}
              />
            {/each}
          {/if}
        </g>
        <g transform="translate({facetMargin.left},{facetMargin.top + facetInnerHeight})">
          <text
            x={facetCx(decades[0])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[0]}</text>
          <text
            x={facetCx(decades[decades.length - 1])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[decades.length - 1]}</text>
        </g>
      </svg>
    </button>
  {/each}
</section>
</div>

<div bind:this={methodsUsVsNonUsBarHeaderRef}>
<h2 class="section-h2">Methods by region: USA vs non-USA (1986–2026)</h2>
<p class="caption">
  Methods proportion over time, <span style="color: {usColor}; font-weight: 600;">USA</span> vs <span style="color: {nonUsColor}; font-weight: 600;">Non-USA</span>. n={compareTotal} (USA={usPapers.length}, Non-USA={nonUsPapers.length}). Papers with region <em>multiple regions</em> or <em>unclear or conceptual</em>, and papers missing from the locations dataset, are excluded.
</p>

<div class="legend">
  <div class="legend-item static">
    <span class="swatch" style="background: {usColor};"></span>
    <span class="label">USA (n={usPapers.length})</span>
  </div>
  <div class="legend-item static">
    <span class="swatch" style="background: {nonUsColor};"></span>
    <span class="label">Non-USA (n={nonUsPapers.length})</span>
  </div>
</div>
</div>

<div class="charts-row">
<button type="button" class="export-btn" onclick={() => exportPng(methodsUsVsNonUsBarRef, 'methods_us_vs_nonus_bar', methodsUsVsNonUsBarHeaderRef)}>⬇ PNG</button>
<svg bind:this={methodsUsVsNonUsBarRef} width={barWidth} height={barHeight} class="bar-chart">
  <text
    x={-(barHeight / 2)}
    y={16}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Proportion</text>

  {@render barYAxisTicks()}

  {#each decadeUsNonUsProportions as { decade, segments } (decade)}
    {#each segments as seg (seg.bucket)}
      {#if seg.proportion > 0}
        {@const x = xBand(decade) ?? 0}
        {@const bw = xBand.bandwidth()}
        {@const yTop = yBar(seg.y1)}
        {@const h = yBar(seg.y0) - yBar(seg.y1)}
        <rect
          x={x}
          y={yTop}
          width={bw}
          height={h}
          fill={seg.bucket === 'USA' ? usColor : nonUsColor}
          opacity={0.85}
        />
        {#if seg.proportion > 0.06}
          <text
            x={x + bw / 2}
            y={yTop + h / 2 + 4}
            text-anchor="middle"
            font-size="11"
            fill="white"
            pointer-events="none"
          >n={seg.count}</text>
        {/if}
      {/if}
    {/each}
  {/each}

  {@render barXAxisLabels()}
  {@render barXAxisTitle()}
</svg>

<button type="button" class="export-btn" onclick={() => exportPng(methodsUsVsNonUsFacetsRef, 'methods_us_vs_nonus_facets')}>⬇ PNG</button>
<section bind:this={methodsUsVsNonUsFacetsRef} class="facets" aria-label="Methods USA vs non-USA over time">
  {#each combinedMethodSeries as { method, us, nonUs } (method)}
    {@const dimmed = selectedMethod !== null && selectedMethod !== method}
    {@const usPct = (us.max * 100).toFixed(0)}
    {@const nonUsPct = (nonUs.max * 100).toFixed(0)}
    {@const usN = us.points.reduce((a, p) => a + p.count, 0)}
    {@const nonUsN = nonUs.points.reduce((a, p) => a + p.count, 0)}
    <button
      type="button"
      class="facet"
      class:dimmed
      onclick={() => toggleMethod(method)}
      aria-label="{method} proportion over time: USA peak {usPct}%, Non-USA peak {nonUsPct}%"
    >
      <div class="facet-header">
        <span class="facet-name">{method}</span>
        <span class="facet-max">· US peak {usPct}% · NonUS peak {nonUsPct}% (n_US={usN}, n_NonUS={nonUsN})</span>
      </div>
      <svg width={facetWidth} height={facetHeight} class="facet-svg">
        <g transform="translate({facetMargin.left},{facetMargin.top})">
          {@render facetHatchOverlay()}
          {#each compareYTicks as t (t)}
            <line
              x1={0}
              x2={facetInnerWidth}
              y1={compareY(t)}
              y2={compareY(t)}
              stroke="#eee"
              stroke-width="1"
            />
            <text
              x={-4}
              y={compareY(t) + 3}
              text-anchor="end"
              font-size="9"
              fill="#888"
            >{(t * 100).toFixed(0)}%</text>
          {/each}
          {#if us.max > 0}
            {@const usPath = us.points
              .map((p, i) => `${i === 0 ? 'M' : 'L'} ${facetCx(p.decade)} ${compareY(p.proportion)}`)
              .join(' ')}
            <path
              d={usPath}
              fill="none"
              stroke={usColor}
              stroke-width="1.5"
              opacity={dimmed ? 0.15 : 0.9}
            />
            {#each us.points as p (p.decade)}
              <circle
                cx={facetCx(p.decade)}
                cy={compareY(p.proportion)}
                r="2.5"
                fill={usColor}
                opacity={dimmed ? 0.15 : 0.9}
              />
            {/each}
          {/if}
          {#if nonUs.max > 0}
            {@const nonUsPath = nonUs.points
              .map((p, i) => `${i === 0 ? 'M' : 'L'} ${facetCx(p.decade)} ${compareY(p.proportion)}`)
              .join(' ')}
            <path
              d={nonUsPath}
              fill="none"
              stroke={nonUsColor}
              stroke-width="1.5"
              opacity={dimmed ? 0.15 : 0.9}
            />
            {#each nonUs.points as p (p.decade)}
              <circle
                cx={facetCx(p.decade)}
                cy={compareY(p.proportion)}
                r="2.5"
                fill={nonUsColor}
                opacity={dimmed ? 0.15 : 0.9}
              />
            {/each}
          {/if}
        </g>
        <g transform="translate({facetMargin.left},{facetMargin.top + facetInnerHeight})">
          <text
            x={facetCx(decades[0])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[0]}</text>
          <text
            x={facetCx(decades[decades.length - 1])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[decades.length - 1]}</text>
        </g>
      </svg>
    </button>
  {/each}
</section>
</div>

<div bind:this={topicsStackedHeaderRef}>
<h2 class="section-h2">Topics across rural geography (1986–2026)</h2>
<p class="caption">
  {topicPapers.length} papers across {topicCategories.length} categories. The stacked bar shows each topic's share of all topic-instances in each 5-year bucket; the small multiples show the proportion of papers tagged with each topic over time.
</p>

<div class="facet-controls">
  <span class="control-label">Model:</span>
  <select bind:value={topicModel} class="upset-topn">
    {#each topicModels as m (m.key)}
      <option value={m.key}>{m.label}</option>
    {/each}
  </select>
</div>
<p class="caption">{currentModel.description}</p>

<div class="facet-controls">
  <span class="control-label">Small multiples y-axis:</span>
  <button
    type="button"
    class="toggle-btn"
    class:active={topicSharedY}
    onclick={() => (topicSharedY = true)}
  >shared</button>
  <button
    type="button"
    class="toggle-btn"
    class:active={!topicSharedY}
    onclick={() => (topicSharedY = false)}
  >free (per-facet)</button>
</div>

<div class="legend">
  {#each topicCategories as topic (topic)}
    <div class="legend-cell">
      <button
        type="button"
        class="legend-item"
        class:dimmed={selectedTopic !== null && selectedTopic !== topic}
        onclick={() => toggleTopic(topic)}
      >
        <span class="swatch" style="background: {topicColor(topic)};"></span>
        <span class="label">{topic}</span>
      </button>
      <div class="legend-desc" role="tooltip">{topicDescriptions[topic]}</div>
    </div>
  {/each}
</div>
</div>

<div class="charts-row">
<button type="button" class="export-btn" onclick={() => exportPng(topicsStackedRef, 'topics_stacked', topicsStackedHeaderRef)}>⬇ PNG</button>
<svg bind:this={topicsStackedRef} width={barWidth} height={barHeight} class="bar-chart">
  <text
    x={-(barHeight / 2)}
    y={16}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Share of topic-instances</text>

  {@render barYAxisTicks()}

  {#each decadeTopicProportions as { decade, segments } (decade)}
    {#each segments as seg (seg.topic)}
      {#if seg.proportion > 0}
        {@const x = xBand(decade) ?? 0}
        {@const bw = xBand.bandwidth()}
        {@const yTop = yBar(seg.y1)}
        {@const h = yBar(seg.y0) - yBar(seg.y1)}
        <rect
          x={x}
          y={yTop}
          width={bw}
          height={h}
          fill={topicColor(seg.topic)}
          opacity={selectedTopic !== null && seg.topic !== selectedTopic ? 0.15 : 0.85}
          role="button"
          tabindex="-1"
          aria-label="{seg.topic}, {decade}"
          onclick={() => toggleTopic(seg.topic)}
          onkeydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') toggleTopic(seg.topic);
          }}
          style="cursor: pointer;"
        />
        {#if seg.proportion > 0.06}
          <text
            x={x + bw / 2}
            y={yTop + h / 2 + 4}
            text-anchor="middle"
            font-size="11"
            fill="white"
            pointer-events="none"
          >n={seg.count}</text>
        {/if}
      {/if}
    {/each}
  {/each}

  {@render barXAxisLabels()}
  {@render barXAxisTitle()}
</svg>

<button type="button" class="export-btn" onclick={() => exportPng(topicsFacetsRef, 'topics_facets')}>⬇ PNG</button>
<section bind:this={topicsFacetsRef} class="facets" aria-label="Topic proportion over time">
  {#each topicSeries as series (series.topic)}
    {@const dimmed = selectedTopic !== null && selectedTopic !== series.topic}
    {@const maxPct = (series.max * 100).toFixed(0)}
    {@const yScale = topicSharedY ? topicFacetY : localY(series.max)}
    {@const yTicks = topicSharedY ? topicFacetYTicks : localYTicks(series.max)}
    <button
      type="button"
      class="facet"
      class:dimmed
      onclick={() => toggleTopic(series.topic)}
      aria-label="{series.topic} proportion over time: peak {maxPct}% in {peakTopicBucket(series.points)}"
    >
      <div class="facet-header">
        <span class="swatch small" style="background: {topicColor(series.topic)};"></span>
        <span class="facet-name">{series.topic}</span>
        <span class="facet-max">· peak {maxPct}%</span>
      </div>
      <svg width={facetWidth} height={facetHeight} class="facet-svg">
        <g transform="translate({facetMargin.left},{facetMargin.top})">
          {@render facetHatchOverlay()}
          {#each yTicks as t (t)}
            <line
              x1={0}
              x2={facetInnerWidth}
              y1={yScale(t)}
              y2={yScale(t)}
              stroke="#eee"
              stroke-width="1"
            />
            <text
              x={-4}
              y={yScale(t) + 3}
              text-anchor="end"
              font-size="9"
              fill="#888"
            >{(t * 100).toFixed(0)}%</text>
          {/each}
          {#if series.max > 0}
            {@const pathD = series.points
              .map((p, i) => `${i === 0 ? 'M' : 'L'} ${facetCx(p.decade)} ${yScale(p.proportion)}`)
              .join(' ')}
            <path
              d={pathD}
              fill="none"
              stroke={topicColor(series.topic)}
              stroke-width="1.5"
              opacity={dimmed ? 0.15 : 0.9}
            />
            {#each series.points as p (p.decade)}
              <circle
                cx={facetCx(p.decade)}
                cy={yScale(p.proportion)}
                r="2.5"
                fill={topicColor(series.topic)}
                opacity={dimmed ? 0.15 : 0.9}
              />
            {/each}
          {/if}
        </g>
        <g transform="translate({facetMargin.left},{facetMargin.top + facetInnerHeight})">
          <text
            x={facetCx(decades[0])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[0]}</text>
          <text
            x={facetCx(decades[decades.length - 1])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[decades.length - 1]}</text>
        </g>
      </svg>
    </button>
  {/each}
</section>
</div>

<div bind:this={topicsUsVsNonUsBarHeaderRef}>
<h2 class="section-h2">Topics by region: USA vs non-USA (1986–2026)</h2>
<p class="caption">
  Topic prevalence over time, <span style="color: {usColor}; font-weight: 600;">USA</span> vs <span style="color: {nonUsColor}; font-weight: 600;">Non-USA</span>. n={compareTopicTotal} (USA={usTopicPapers.length}, Non-USA={nonUsTopicPapers.length}). Papers with region <em>multiple regions</em> or <em>unclear or conceptual</em>, and papers missing from the locations dataset, are excluded.
</p>

<div class="legend">
  <div class="legend-item static">
    <span class="swatch" style="background: {usColor};"></span>
    <span class="label">USA (n={usTopicPapers.length})</span>
  </div>
  <div class="legend-item static">
    <span class="swatch" style="background: {nonUsColor};"></span>
    <span class="label">Non-USA (n={nonUsTopicPapers.length})</span>
  </div>
</div>
</div>

<div class="charts-row">
<button type="button" class="export-btn" onclick={() => exportPng(topicsUsVsNonUsBarRef, 'topics_us_vs_nonus_bar', topicsUsVsNonUsBarHeaderRef)}>⬇ PNG</button>
<svg bind:this={topicsUsVsNonUsBarRef} width={barWidth} height={barHeight} class="bar-chart">
  <text
    x={-(barHeight / 2)}
    y={16}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Proportion</text>

  {@render barYAxisTicks()}

  {#each decadeUsNonUsTopicProportions as { decade, segments } (decade)}
    {#each segments as seg (seg.bucket)}
      {#if seg.proportion > 0}
        {@const x = xBand(decade) ?? 0}
        {@const bw = xBand.bandwidth()}
        {@const yTop = yBar(seg.y1)}
        {@const h = yBar(seg.y0) - yBar(seg.y1)}
        <rect
          x={x}
          y={yTop}
          width={bw}
          height={h}
          fill={seg.bucket === 'USA' ? usColor : nonUsColor}
          opacity={0.85}
        />
        {#if seg.proportion > 0.06}
          <text
            x={x + bw / 2}
            y={yTop + h / 2 + 4}
            text-anchor="middle"
            font-size="11"
            fill="white"
            pointer-events="none"
          >n={seg.count}</text>
        {/if}
      {/if}
    {/each}
  {/each}

  {@render barXAxisLabels()}
  {@render barXAxisTitle()}
</svg>

<button type="button" class="export-btn" onclick={() => exportPng(topicsUsVsNonUsFacetsRef, 'topics_us_vs_nonus_facets')}>⬇ PNG</button>
<section bind:this={topicsUsVsNonUsFacetsRef} class="facets" aria-label="Topics USA vs non-USA over time">
  {#each combinedTopicSeries as { topic, us, nonUs } (topic)}
    {@const dimmed = selectedTopic !== null && selectedTopic !== topic}
    {@const usPct = (us.max * 100).toFixed(0)}
    {@const nonUsPct = (nonUs.max * 100).toFixed(0)}
    {@const usN = us.points.reduce((a, p) => a + p.count, 0)}
    {@const nonUsN = nonUs.points.reduce((a, p) => a + p.count, 0)}
    <button
      type="button"
      class="facet"
      class:dimmed
      onclick={() => toggleTopic(topic)}
      aria-label="{topic} proportion over time: USA peak {usPct}%, Non-USA peak {nonUsPct}%"
    >
      <div class="facet-header">
        <span class="facet-name">{topic}</span>
        <span class="facet-max">· US peak {usPct}% · NonUS peak {nonUsPct}% (n_US={usN}, n_NonUS={nonUsN})</span>
      </div>
      <svg width={facetWidth} height={facetHeight} class="facet-svg">
        <g transform="translate({facetMargin.left},{facetMargin.top})">
          {@render facetHatchOverlay()}
          {#each compareTopicYTicks as t (t)}
            <line
              x1={0}
              x2={facetInnerWidth}
              y1={compareTopicY(t)}
              y2={compareTopicY(t)}
              stroke="#eee"
              stroke-width="1"
            />
            <text
              x={-4}
              y={compareTopicY(t) + 3}
              text-anchor="end"
              font-size="9"
              fill="#888"
            >{(t * 100).toFixed(0)}%</text>
          {/each}
          {#if us.max > 0}
            {@const usPath = us.points
              .map((p, i) => `${i === 0 ? 'M' : 'L'} ${facetCx(p.decade)} ${compareTopicY(p.proportion)}`)
              .join(' ')}
            <path
              d={usPath}
              fill="none"
              stroke={usColor}
              stroke-width="1.5"
              opacity={dimmed ? 0.15 : 0.9}
            />
            {#each us.points as p (p.decade)}
              <circle
                cx={facetCx(p.decade)}
                cy={compareTopicY(p.proportion)}
                r="2.5"
                fill={usColor}
                opacity={dimmed ? 0.15 : 0.9}
              />
            {/each}
          {/if}
          {#if nonUs.max > 0}
            {@const nonUsPath = nonUs.points
              .map((p, i) => `${i === 0 ? 'M' : 'L'} ${facetCx(p.decade)} ${compareTopicY(p.proportion)}`)
              .join(' ')}
            <path
              d={nonUsPath}
              fill="none"
              stroke={nonUsColor}
              stroke-width="1.5"
              opacity={dimmed ? 0.15 : 0.9}
            />
            {#each nonUs.points as p (p.decade)}
              <circle
                cx={facetCx(p.decade)}
                cy={compareTopicY(p.proportion)}
                r="2.5"
                fill={nonUsColor}
                opacity={dimmed ? 0.15 : 0.9}
              />
            {/each}
          {/if}
        </g>
        <g transform="translate({facetMargin.left},{facetMargin.top + facetInnerHeight})">
          <text
            x={facetCx(decades[0])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[0]}</text>
          <text
            x={facetCx(decades[decades.length - 1])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[decades.length - 1]}</text>
        </g>
      </svg>
    </button>
  {/each}
</section>
</div>

<h3 class="section-h3">Topic combinations: UpSet (left) + pairwise co-occurrence (right)</h3>
<p class="caption">
  <strong>Left — UpSet (exact-set view):</strong> the {UPSET_TOP_N} most-recurring <em>exact</em> topic combinations across {topicPapers.length} papers ({topicIntersections.length} distinct combinations total). Each vertical bar counts papers whose <em>full topic set</em> matches the dotted pattern — a "social power + identity" bar counts only papers tagged with those two and <em>nothing else</em>. <strong>Right — pairwise heatmap (at-least-both view):</strong> cell (row, column) counts papers tagged with <em>both</em> topics regardless of what else they have, so the same pair will always show a larger number here than in the UpSet view (the heatmap value equals the sum of every UpSet bar whose dot pattern contains both topics). Diagonal cells are each topic's own paper count, shown in grey. Click any UpSet bar or heatmap cell to filter the table below.
</p>

<div class="facet-controls">
  <span class="control-label">Heatmap intensity:</span>
  <button
    type="button"
    class="toggle-btn"
    class:active={coocMode === 'count'}
    onclick={() => (coocMode = 'count')}
  >raw count</button>
  <button
    type="button"
    class="toggle-btn"
    class:active={coocMode === 'phi'}
    onclick={() => (coocMode = 'phi')}
  >phi correlation</button>
  {#if coocMode === 'phi'}
    <span class="control-label" style="margin-left: 12px;">
      <span style="color: rgba(46, 92, 158, 0.85); font-weight: 600;">blue</span> = positive association,
      <span style="color: rgba(190, 70, 70, 0.85); font-weight: 600;">red</span> = negative.
      φ ∈ [−1, 1]; cells with |φ| &lt; 0.05 are blanked.
    </span>
  {/if}
</div>

<div class="facet-controls">
  <span class="control-label">Row/column order:</span>
  <button
    type="button"
    class="toggle-btn"
    class:active={coocSort === 'frequency'}
    onclick={() => (coocSort = 'frequency')}
  >by frequency</button>
  <button
    type="button"
    class="toggle-btn"
    class:active={coocSort === 'alphabetical'}
    onclick={() => (coocSort = 'alphabetical')}
  >alphabetical</button>
  <button
    type="button"
    class="toggle-btn"
    class:active={coocSort === 'cluster'}
    onclick={() => (coocSort = 'cluster')}
  >cluster (hierarchical on 1−φ)</button>
</div>

<div class="cooc-row">
<div class="upset-wrap">
<button type="button" class="export-btn" onclick={() => exportPng(upsetRef, 'topics_upset')}>⬇ PNG</button>
<svg bind:this={upsetRef} width={upsetWidth} height={upsetHeight} class="upset">
  <!-- Intersection bars (top) -->
  <g transform="translate({upsetMatrixLeft},{upsetMargin.top})">
    {#each topIntersections as inter, i (inter.setKey)}
      {@const x = i * upsetCellSize}
      {@const h = upsetBarHeight(inter.count)}
      {@const active = upsetSelected === inter.setKey}
      <rect
        x={x + 3}
        y={upsetIntersectionBarHeight - h}
        width={upsetCellSize - 6}
        height={h}
        fill={active ? '#1a4a8a' : '#444'}
        opacity={upsetSelected !== null && !active ? 0.25 : 0.85}
        style="cursor: pointer;"
        role="button"
        tabindex="-1"
        aria-label="{inter.count} papers with topics: {[...inter.members].join(', ')}"
        onclick={() => toggleUpset(inter.setKey)}
      />
      {#if inter.count >= 2}
        <text
          x={x + upsetCellSize / 2}
          y={upsetIntersectionBarHeight - h - 4}
          text-anchor="middle"
          font-size="10"
          fill="#444"
          pointer-events="none"
        >{inter.count}</text>
      {/if}
    {/each}
  </g>

  <!-- Topic labels + set-size bars (left column, aligned with matrix rows) -->
  <g transform="translate({upsetMargin.left},{upsetMatrixTop})">
    {#each topicCategories as topic, ti (topic)}
      {@const y = ti * upsetCellSize}
      {@const total = topicSetTotals.get(topic) ?? 0}
      {@const w = upsetSetBarWidthScale(total)}
      <text
        x={upsetTopicLabelWidth - 6}
        y={y + upsetCellSize / 2 + 4}
        text-anchor="end"
        font-size="11"
        fill="#333"
      >{topic}</text>
      <rect
        x={upsetTopicLabelWidth}
        y={y + 4}
        width={w}
        height={upsetCellSize - 8}
        fill="#999"
        opacity="0.6"
      />
      <text
        x={upsetTopicLabelWidth + w + 4}
        y={y + upsetCellSize / 2 + 4}
        font-size="10"
        fill="#666"
      >{total}</text>
    {/each}
  </g>

  <!-- Intersection dot matrix (bottom-right) -->
  <g transform="translate({upsetMatrixLeft},{upsetMatrixTop})">
    {#each topicCategories as topic, ti (topic)}
      <line
        x1={upsetCellSize / 2}
        x2={topIntersections.length * upsetCellSize - upsetCellSize / 2}
        y1={ti * upsetCellSize + upsetCellSize / 2}
        y2={ti * upsetCellSize + upsetCellSize / 2}
        stroke="#f0f0f0"
        stroke-width="1"
      />
    {/each}
    {#each topIntersections as inter, ii (inter.setKey)}
      {@const x = ii * upsetCellSize}
      {@const active = upsetSelected === inter.setKey}
      {@const memberIdxs = topicCategories
        .map((t, ti) => (inter.members.has(t) ? ti : -1))
        .filter((ti) => ti >= 0)}
      {#if memberIdxs.length >= 2}
        {@const minI = Math.min(...memberIdxs)}
        {@const maxI = Math.max(...memberIdxs)}
        <line
          x1={x + upsetCellSize / 2}
          x2={x + upsetCellSize / 2}
          y1={minI * upsetCellSize + upsetCellSize / 2}
          y2={maxI * upsetCellSize + upsetCellSize / 2}
          stroke={active ? '#1a4a8a' : '#444'}
          stroke-width="1.5"
          opacity={upsetSelected !== null && !active ? 0.2 : 0.7}
        />
      {/if}
      {#each topicCategories as topic, ti (topic)}
        {@const inSet = inter.members.has(topic)}
        <circle
          cx={x + upsetCellSize / 2}
          cy={ti * upsetCellSize + upsetCellSize / 2}
          r={inSet ? 4 : 2}
          fill={inSet ? (active ? '#1a4a8a' : '#333') : '#ddd'}
          opacity={inSet
            ? upsetSelected !== null && !active ? 0.25 : 0.9
            : 0.45}
          style="cursor: pointer;"
          role="button"
          tabindex="-1"
          aria-label="{inSet ? 'in' : 'not in'} combination {ii + 1}: {topic}"
          onclick={() => toggleUpset(inter.setKey)}
        />
      {/each}
    {/each}
  </g>
</svg>
</div>

<div class="cooc-wrap">
<button type="button" class="export-btn" onclick={() => exportPng(coocRef, 'topics_cooccurrence')}>⬇ PNG</button>
<svg bind:this={coocRef} width={coocWidth} height={coocHeight} class="cooc">
  <!-- Column labels (rotated -45° above grid) — uses ordered indices -->
  <g transform="translate({coocMargin.left},{coocMargin.top})">
    {#each heatmapOrder as origJ, displayJ (origJ)}
      {@const topic = topicCategories[origJ]}
      <text
        x={displayJ * coocCellSize + coocCellSize / 2}
        y={-6}
        text-anchor="start"
        font-size="11"
        fill="#333"
        transform="rotate(-45, {displayJ * coocCellSize + coocCellSize / 2}, -6)"
      >{topic}</text>
    {/each}
  </g>

  <!-- Row labels — uses ordered indices -->
  <g transform="translate({coocMargin.left},{coocMargin.top})">
    {#each heatmapOrder as origI, displayI (origI)}
      {@const topic = topicCategories[origI]}
      <text
        x={-6}
        y={displayI * coocCellSize + coocCellSize / 2 + 4}
        text-anchor="end"
        font-size="11"
        fill="#333"
      >{topic}</text>
    {/each}
  </g>

  <!-- Cells — render in display order; look up cell by original i/j -->
  <g transform="translate({coocMargin.left},{coocMargin.top})">
    {#each heatmapOrder as origI, displayI (origI)}
      {#each heatmapOrder as origJ, displayJ (origJ)}
        {@const rowTopic = topicCategories[origI]}
        {@const colTopic = topicCategories[origJ]}
        {@const cell = topicCooccurrence[origI][origJ]}
        {@const active =
          coocSelected !== null &&
          coocSelected.rowTopic === rowTopic &&
          coocSelected.colTopic === colTopic}
        <rect
          x={displayJ * coocCellSize}
          y={displayI * coocCellSize}
          width={coocCellSize - 1}
          height={coocCellSize - 1}
          fill={coocCellFill(origI, origJ, cell.count)}
          stroke={active ? '#1a4a8a' : 'transparent'}
          stroke-width={active ? 2 : 0}
          style="cursor: {cell.count > 0 ? 'pointer' : 'default'};"
          role="button"
          tabindex="-1"
          aria-label="{rowTopic} × {colTopic}: {cell.count} papers"
          onclick={() => toggleCooc(rowTopic, colTopic, cell.count)}
        />
        {@const label = coocCellLabel(origI, origJ, cell.count)}
        {#if label}
          <text
            x={displayJ * coocCellSize + coocCellSize / 2}
            y={displayI * coocCellSize + coocCellSize / 2 + 4}
            text-anchor="middle"
            font-size="11"
            fill={coocCellTextFill(origI, origJ, cell.count)}
            pointer-events="none"
          >{label}</text>
        {/if}
      {/each}
    {/each}
  </g>
</svg>
</div>
</div>

<details class="interpretation">
  <summary>Reading the two views</summary>
  <ul>
    <li>
      <strong>UpSet bar ≠ heatmap cell.</strong> The UpSet bar for "A + B" counts papers whose <em>exact</em> topic set is {`{A, B}`} and nothing else (e.g. <code>social power + identity</code> ≈ 15 papers). The heatmap cell counts every paper with <em>at least</em> both tags, regardless of what else they carry (e.g. ≈ 131 papers). The heatmap value equals the sum of every UpSet bar whose dot pattern contains both topics.
    </li>
    <li>
      <strong>Raw count vs phi.</strong> Raw count is volume; phi is association above chance. Two common labels (like <code>social power</code> and <code>identity</code>) will co-occur a lot in absolute terms even if they're only modestly associated — their phi may be only ~0.20–0.30 even when their co-occurrence count is the corpus maximum. Rare labels that nonetheless travel together (like <code>emotion + place-based study</code>) can be invisible in raw count but jump out in phi.
    </li>
    <li>
      <strong>Cluster ordering surfaces block structure.</strong> Switching to <code>cluster (hierarchical on 1−φ)</code> reorders rows and columns so positively-associated labels land adjacent. Expect roughly three blocks on the diagonal: a social-political cluster (<code>social power</code>, <code>identity</code>, <code>governance</code>, <code>mobility</code>), a place/space-form cluster (<code>place-based study</code>, <code>built environment</code>, <code>scale/location</code>), and a nature-society cluster (<code>human-environment</code>, <code>natural environment</code>, <code>climate and natural hazards</code>, perhaps <code>agriculture/food</code>). The long-tail labels (<code>methods</code>, <code>technology</code>, <code>energy</code>, <code>weather</code>, <code>recreation</code>) typically sit at the edges and their clustering position is noisy because of small support.
    </li>
    <li>
      <strong>What strong negative phi (red) means.</strong> Red cells flag tag pairs that papers <em>avoid</em> combining — distinct analytical commitments. Expect mild red between method-of-paper-explanation labels (<code>methods</code>, <code>technology</code>) and affective labels (<code>emotion</code>), and between purely-physical labels (<code>weather</code>, <code>climate and natural hazards</code>) and identity/power labels.
    </li>
    <li>
      <strong>Sample-size caveat.</strong> <code>weather</code> (n=2), <code>recreation</code> (n=13), <code>energy</code> (n=12), <code>natural environment</code> (n=14) have low support, so their phi values are noisy and their clustered position can shift on minor data changes. Treat their positions as suggestive at best.
    </li>
  </ul>
</details>

<details class="interpretation">
  <summary>How phi is computed (and why it differs from raw count)</summary>
  <p>
    Pairs like <code>social power</code> and <code>identity</code> are the most common co-occurring tags, but that's not particularly meaningful — they're also the two most common individual tags. We instead want to examine the <em>correlation</em> between tags: how often they appear together relative to how often they appear separately. The phi coefficient does exactly this. Its focus is <em>how much more likely it is that either both topics X and Y appear on a paper, or neither does, than that one appears without the other.</em>
  </p>

  <p class="phi-formula">
    <span class="phi-frac">
      <span class="phi-num">
        φ &nbsp;=&nbsp;
      </span>
      <span class="phi-stack">
        <span class="phi-numerator">n<sub>11</sub>·n<sub>00</sub> − n<sub>10</sub>·n<sub>01</sub></span>
        <span class="phi-bar"></span>
        <span class="phi-denominator">√(n<sub>1·</sub>·n<sub>0·</sub>·n<sub>·0</sub>·n<sub>·1</sub>)</span>
      </span>
    </span>
  </p>

  <p>
    The four counts come from a 2×2 contingency table for any pair of topics X and Y across the corpus:
  </p>

  <table class="contingency">
    <thead>
      <tr>
        <th></th>
        <th>Has tag Y</th>
        <th>No tag Y</th>
        <th>Total</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <th>Has tag X</th>
        <td>n<sub>11</sub></td>
        <td>n<sub>10</sub></td>
        <td>n<sub>1·</sub></td>
      </tr>
      <tr>
        <th>No tag X</th>
        <td>n<sub>01</sub></td>
        <td>n<sub>00</sub></td>
        <td>n<sub>0·</sub></td>
      </tr>
      <tr>
        <th>Total</th>
        <td>n<sub>·1</sub></td>
        <td>n<sub>·0</sub></td>
        <td>n</td>
      </tr>
    </tbody>
  </table>

  <p>
    Concretely, for X = <code>social power</code> and Y = <code>identity</code> on our 346 papers:
    n<sub>11</sub> ≈ papers with both, n<sub>10</sub> ≈ social-power-only, n<sub>01</sub> ≈ identity-only, n<sub>00</sub> ≈ neither. The numerator (n<sub>11</sub>·n<sub>00</sub> − n<sub>10</sub>·n<sub>01</sub>) is positive when "both-or-neither" dominates "one-without-the-other", and negative in the reverse case. The denominator is a geometric mean of the marginal totals; dividing by it normalizes φ into [−1, 1] regardless of corpus size or how lopsided the individual labels are.
  </p>

  <p>
    Properties worth knowing:
  </p>
  <ul>
    <li>φ is symmetric: φ(X, Y) = φ(Y, X). The heatmap is therefore symmetric across the diagonal.</li>
    <li>φ = 0 means topics co-occur exactly at chance frequency, given their marginals.</li>
    <li>For two binary variables, φ equals the Pearson correlation coefficient; both have the same meaning in this setting.</li>
    <li>In practice |φ| rarely exceeds ~0.5 even for strong associations in document-tagging data, because each tag has a wide range of papers it could appear on — the diverging colour scale on the heatmap amplifies the |φ| × 2.5 mapping so that mid-range associations are still visible.</li>
    <li>φ is sensitive to the marginal frequencies. A pair with low individual support that always co-occurs can show a very high φ on a small sample (the <code>weather</code>/<code>climate-and-natural-hazards</code> pair would be a candidate here). The sample-size caveat above applies.</li>
  </ul>

  <h5 class="phi-subhead">Is |φ| = 0.3 surprising? Significance and bootstrap</h5>

  <p>
    A useful intuition for our 346-paper corpus: under the null hypothesis that two tags are independent, the standard error of φ is roughly 1/√n ≈ 0.054. So an observed φ = 0.3 sits about 5–6 standard errors away from zero — extremely unlikely under independence.
  </p>

  <p>
    More precisely: the chi-square test statistic for a 2×2 contingency table is χ² = n · φ², with 1 degree of freedom. So:
  </p>
  <ul>
    <li>|φ| ≥ 0.10  →  χ² ≥ 3.46,  p ≈ 0.06  (marginal)</li>
    <li>|φ| ≥ 0.15  →  χ² ≥ 7.79,  p &lt; 0.01</li>
    <li>|φ| ≥ 0.20  →  χ² ≥ 13.8,  p &lt; 0.001</li>
    <li>|φ| ≥ 0.30  →  χ² ≥ 31.1,  p &lt; 10⁻⁷</li>
  </ul>
  <p>
    These thresholds are asymptotic and assume both tags have reasonable marginal support. They break down when one tag is rare. <strong>Click any heatmap cell to see its 95% bootstrap CI and its chi-square p-value</strong> — bootstrap (resampling papers with replacement, 1000 iterations) is the more honest measure when marginal support is small, because it captures the actual sampling variability of φ rather than assuming the asymptotic Normal approximation.
  </p>
</details>

{#if coocSelected !== null}
  <div class="table-section">
    <h2>
      Co-occurrence: <span class="upset-set">{coocSelected.rowTopic} + {coocSelected.colTopic}</span>
      <span class="count">({coocSelectedPapers.length} papers)</span>
      <button onclick={() => (coocSelected = null)}>Clear</button>
    </h2>
    {#if coocSelectedStats}
      <div class="cooc-stats">
        <div class="cooc-stats-row">
          <div class="cooc-contingency">
            <div class="cooc-cont-title">Contingency (n = {coocSelectedStats.n})</div>
            <table class="cont-tbl">
              <thead>
                <tr>
                  <th></th>
                  <th>{coocSelected.colTopic} ✓</th>
                  <th>{coocSelected.colTopic} ✗</th>
                  <th>row total</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>{coocSelected.rowTopic} ✓</th>
                  <td class="hi">n<sub>11</sub> = {coocSelectedStats.a}</td>
                  <td>n<sub>10</sub> = {coocSelectedStats.b}</td>
                  <td class="marg">{coocSelectedStats.a + coocSelectedStats.b}</td>
                </tr>
                <tr>
                  <th>{coocSelected.rowTopic} ✗</th>
                  <td>n<sub>01</sub> = {coocSelectedStats.c}</td>
                  <td>n<sub>00</sub> = {coocSelectedStats.d}</td>
                  <td class="marg">{coocSelectedStats.c + coocSelectedStats.d}</td>
                </tr>
                <tr class="marg-row">
                  <th>col total</th>
                  <td class="marg">{coocSelectedStats.a + coocSelectedStats.c}</td>
                  <td class="marg">{coocSelectedStats.b + coocSelectedStats.d}</td>
                  <td class="marg">{coocSelectedStats.n}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="cooc-numbers">
            <div class="cooc-stat-row">
              <span class="cooc-stat-label">φ̂</span>
              <span class="cooc-stat-val">{coocSelectedStats.phi.toFixed(3)}</span>
            </div>
            <div class="cooc-stat-row">
              <span class="cooc-stat-label">95% bootstrap CI</span>
              <span class="cooc-stat-val">[{coocSelectedStats.ciLow.toFixed(3)}, {coocSelectedStats.ciHigh.toFixed(3)}]</span>
            </div>
            <div class="cooc-stat-row">
              <span class="cooc-stat-label">χ² (1 df)</span>
              <span class="cooc-stat-val">{coocSelectedStats.chi2.toFixed(2)}</span>
            </div>
            <div class="cooc-stat-row">
              <span class="cooc-stat-label">p</span>
              <span class="cooc-stat-val">{fmtP(coocSelectedStats.pValue)}</span>
            </div>
            <div class="cooc-stat-note">
              Bootstrap: {BOOTSTRAP_N} resamples of papers with replacement.
              {#if coocSelectedStats.ciLow > 0 || coocSelectedStats.ciHigh < 0}
                CI excludes 0 — association is reliable at the 5% level.
              {:else}
                CI includes 0 — direction not reliable; treat as noise.
              {/if}
            </div>
          </div>
        </div>
      </div>
    {/if}
    <table>
      <thead>
        <tr>
          <th>Year</th>
          <th>Title</th>
          <th>Authors</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {#each coocSelectedPapers as p (p.doi)}
          <tr>
            <td>{p.pub_year}</td>
            <td>{p.title || p.doi}</td>
            <td>{p.authors}</td>
            <td>{p.source}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<h3 class="section-h3">Anchor topic — co-occurrence over time</h3>
<p class="caption">
  Pick an anchor topic. Each facet shows the fraction of <em>anchor-tagged
  papers</em> in each decade that <em>also</em> had the co-topic. Sort by
  <strong>overall %</strong> for the loudest trajectories, by <strong>signed φ</strong>
  to put true positive associations first and avoidance pairs last, or by
  <strong>|φ|</strong> to surface the most structurally informative pairs
  regardless of direction.
</p>

<div class="facet-controls">
  <span class="control-label">Anchor:</span>
  <select bind:value={anchorTopic} class="upset-topn">
    {#each topicCategories as t (t)}
      <option value={t}>{t} (n={topicSetTotals.get(t) ?? 0})</option>
    {/each}
  </select>
  <span class="control-label">sort:</span>
  <button
    type="button"
    class="toggle-btn"
    class:active={anchorSort === 'overall'}
    onclick={() => (anchorSort = 'overall')}
  >overall %</button>
  <button
    type="button"
    class="toggle-btn"
    class:active={anchorSort === 'phi'}
    onclick={() => (anchorSort = 'phi')}
  >signed φ</button>
  <button
    type="button"
    class="toggle-btn"
    class:active={anchorSort === 'absphi'}
    onclick={() => (anchorSort = 'absphi')}
  >|φ|</button>
  <span class="control-label">y-axis:</span>
  <button
    type="button"
    class="toggle-btn"
    class:active={anchorSharedY}
    onclick={() => (anchorSharedY = true)}
  >shared</button>
  <button
    type="button"
    class="toggle-btn"
    class:active={!anchorSharedY}
    onclick={() => (anchorSharedY = false)}
  >free</button>
  <span class="control-label" style="margin-left: 12px;">n papers tagged <em>{effectiveAnchor}</em>: {anchorTotalPapers}</span>
</div>

<button type="button" class="export-btn" onclick={() => exportPng(anchorFacetsRef, 'anchor_topic_facets')}>⬇ PNG</button>
<section bind:this={anchorFacetsRef} class="facets anchor-facets" aria-label="Co-occurrence with anchor topic over time">
  {#each anchorSeries as series (series.coTopic)}
    {@const maxPct = (series.max * 100).toFixed(0)}
    {@const overallPct = (series.overall * 100).toFixed(0)}
    {@const yScale = anchorSharedY ? anchorFacetY : localY(series.max)}
    {@const yTicks = anchorSharedY ? anchorFacetYTicks : localYTicks(series.max)}
    <div class="facet" style="cursor: default;">
      <div class="facet-header">
        <span class="swatch small" style="background: {topicColor(series.coTopic)};"></span>
        <span class="facet-name">{series.coTopic}</span>
        <span class="facet-max">· overall {overallPct}% · peak {maxPct}% ({peakAnchorBucket(series.points)}) · </span>
        <span
          class="facet-phi"
          style="color: {series.phi >= 0 ? 'rgb(46, 92, 158)' : 'rgb(190, 70, 70)'};"
          title="phi correlation of {series.coTopic} with anchor {effectiveAnchor}"
        >φ = {series.phi.toFixed(2)}</span>
      </div>
      <svg width={facetWidth} height={facetHeight} class="facet-svg">
        <g transform="translate({facetMargin.left},{facetMargin.top})">
          {@render facetHatchOverlay()}
          {#each yTicks as t (t)}
            <line
              x1={0}
              x2={facetInnerWidth}
              y1={yScale(t)}
              y2={yScale(t)}
              stroke="#eee"
              stroke-width="1"
            />
            <text
              x={-4}
              y={yScale(t) + 3}
              text-anchor="end"
              font-size="9"
              fill="#888"
            >{(t * 100).toFixed(0)}%</text>
          {/each}
          {#if series.max > 0}
            {@const pathD = series.points
              .map((p, i) => `${i === 0 ? 'M' : 'L'} ${facetCx(p.decade)} ${yScale(p.proportion)}`)
              .join(' ')}
            <path
              d={pathD}
              fill="none"
              stroke={topicColor(series.coTopic)}
              stroke-width="1.5"
              opacity="0.9"
            />
            {#each series.points as p (p.decade)}
              <circle
                cx={facetCx(p.decade)}
                cy={yScale(p.proportion)}
                r="2.5"
                fill={topicColor(series.coTopic)}
                opacity="0.9"
              >
                <title>{p.decade}: {p.numerator}/{p.denominator} anchor papers</title>
              </circle>
            {/each}
          {/if}
        </g>
        <g transform="translate({facetMargin.left},{facetMargin.top + facetInnerHeight})">
          <text
            x={facetCx(decades[0])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[0]}</text>
          <text
            x={facetCx(decades[decades.length - 1])}
            y={12}
            text-anchor="middle"
            font-size="9"
            fill="#888"
          >{decades[decades.length - 1]}</text>
        </g>
      </svg>
    </div>
  {/each}
</section>

{#if upsetSelected !== null && upsetSelectedMembers}
  <div class="table-section">
    <h2>
      Topic combination:
      <span class="upset-set">{[...upsetSelectedMembers].join(' + ')}</span>
      <span class="count">({upsetSelectedPapers.length} papers)</span>
      <button onclick={() => (upsetSelected = null)}>Clear</button>
    </h2>
    <table>
      <thead>
        <tr>
          <th>Year</th>
          <th>Title</th>
          <th>Authors</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {#each upsetSelectedPapers as p (p.doi)}
          <tr>
            <td>{p.pub_year}</td>
            <td>{p.title || p.doi}</td>
            <td>{p.authors}</td>
            <td>{p.source}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

{#if selectedMethod !== null || selectedRegion !== null || selectedTopic !== null}
  <div class="table-section">
    <h2>
      Filtered papers
      <span class="filter-chips">
        {#if selectedMethod !== null}
          <span class="filter-chip">
            Method: <span class="chip-value">{selectedMethod}</span>
            <button class="chip-clear" aria-label="Clear method filter" onclick={() => (selectedMethod = null)}>✕</button>
          </span>
        {/if}
        {#if selectedRegion !== null}
          <span class="filter-chip">
            Region: <span class="chip-value">{selectedRegion}</span>
            <button class="chip-clear" aria-label="Clear region filter" onclick={() => (selectedRegion = null)}>✕</button>
          </span>
        {/if}
        {#if selectedTopic !== null}
          <span class="filter-chip">
            Topic: <span class="chip-value">{selectedTopic}</span>
            <button class="chip-clear" aria-label="Clear topic filter" onclick={() => (selectedTopic = null)}>✕</button>
          </span>
        {/if}
      </span>
      <span class="count">({filteredCombined.length} papers)</span>
      <button onclick={clearAllFilters}>Clear all</button>
    </h2>
    <table>
      <thead>
        <tr>
          <th>
            <button class="sort-btn" onclick={toggleYearSort}>Year{yearSortIndicator}</button>
          </th>
          <th>Title</th>
          <th>Authors</th>
          <th>Source</th>
          <th>Method</th>
          <th>Region</th>
          <th>Topics</th>
          <th>Abstract</th>
        </tr>
      </thead>
      <tbody>
        {#each sortedFiltered as p (p.doi)}
          <tr>
            <td>{p.pub_year}</td>
            <td>{p.title || p.doi}</td>
            <td>{p.authors}</td>
            <td>{p.source}</td>
            <td>{p.method ?? '—'}</td>
            <td>{p.region ?? '—'}</td>
            <td>{p.topics.join(', ')}</td>
            <td class="abstract-cell">{p.abstract}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  h1 {
    font-family: system-ui, sans-serif;
    margin-bottom: 4px;
  }

  .section-h2 {
    font-size: 18px;
    margin: 32px 0 4px;
    font-family: system-ui, sans-serif;
  }

  .caption {
    font-family: system-ui, sans-serif;
    color: #888;
    font-size: 13px;
    margin: 0 0 16px;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 12px;
    font-family: system-ui, sans-serif;
  }

  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: none;
    border: none;
    padding: 4px 6px;
    font-size: 13px;
    cursor: pointer;
    color: #333;
    border-radius: 4px;
    transition: opacity 0.15s, background 0.15s;
  }

  .legend-item:hover {
    background: #f0f0f0;
  }

  .legend-item.dimmed {
    opacity: 0.35;
  }

  .legend-cell {
    position: relative;
  }

  .legend-desc {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 4px;
    width: 320px;
    padding: 8px 10px;
    background: #222;
    color: #f4f4f4;
    border-radius: 4px;
    font-size: 11px;
    line-height: 1.45;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.12s;
    z-index: 10;
  }

  .legend-cell:hover .legend-desc,
  .legend-cell:focus-within .legend-desc {
    opacity: 1;
  }

  .swatch {
    display: inline-block;
    width: 14px;
    height: 14px;
    border-radius: 3px;
  }

  svg {
    display: block;
  }

  .bar-chart rect {
    transition: opacity 0.15s;
  }

  .charts-row {
    display: flex;
    gap: 24px;
    align-items: flex-start;
  }

  .facets {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    column-gap: 16px;
    row-gap: 8px;
    width: 620px;
    font-family: system-ui, sans-serif;
  }

  .facets.anchor-facets {
    display: flex;
    flex-wrap: wrap;
    width: 100%;
    gap: 8px 16px;
  }

  .facets.anchor-facets .facet {
    flex: 0 0 auto;
    width: 300px;
  }

  .facet {
    background: none;
    border: none;
    padding: 4px;
    width: 100%;
    text-align: left;
    cursor: pointer;
    border-radius: 4px;
    transition: opacity 0.15s, background 0.15s;
  }

  .facet:hover {
    background: #f0f0f0;
  }

  .facet.dimmed {
    opacity: 0.35;
  }

  .facet-header {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #333;
    margin-bottom: 2px;
  }

  .swatch.small {
    width: 12px;
    height: 12px;
  }

  .facet-name {
    font-weight: 500;
  }

  .facet-max {
    color: #888;
    font-size: 11px;
  }

  .facet-phi {
    font-size: 11px;
    font-weight: 600;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .section-h3 {
    font-size: 15px;
    margin: 28px 0 4px;
    font-family: system-ui, sans-serif;
    color: #333;
  }

  .cooc-row {
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    align-items: flex-start;
    margin-bottom: 8px;
  }

  .interpretation {
    margin: 12px 0 24px;
    padding: 14px 18px;
    background: #fafafa;
    border-left: 3px solid #d0d7de;
    border-radius: 4px;
    font-family: system-ui, sans-serif;
    max-width: 1100px;
  }

  .interpretation > summary {
    margin: 0 0 6px;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #555;
    font-weight: 600;
    cursor: pointer;
    list-style-position: outside;
    user-select: none;
  }

  .interpretation > summary:hover {
    color: #222;
  }

  .interpretation[open] > summary {
    margin-bottom: 10px;
  }

  .interpretation ul {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
    line-height: 1.55;
    color: #333;
  }

  .interpretation li {
    margin-bottom: 6px;
  }

  .interpretation code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    padding: 1px 4px;
    background: #eee;
    border-radius: 3px;
    color: #1a4a8a;
  }

  .interpretation p {
    margin: 8px 0;
    font-size: 13px;
    line-height: 1.55;
    color: #333;
  }

  .phi-formula {
    display: flex;
    justify-content: center;
    margin: 18px 0 !important;
    font-family: 'Georgia', 'Times New Roman', serif;
    font-style: italic;
    font-size: 16px;
    color: #1a4a8a;
  }

  .phi-frac {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .phi-num {
    font-size: 18px;
  }

  .phi-stack {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    line-height: 1.25;
  }

  .phi-numerator,
  .phi-denominator {
    padding: 0 4px;
  }

  .phi-bar {
    height: 1px;
    background: #1a4a8a;
    width: 100%;
    margin: 2px 0;
  }

  table.contingency {
    margin: 6px auto 14px;
    border-collapse: collapse;
    font-size: 12.5px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  table.contingency th,
  table.contingency td {
    border: 1px solid #d8d8d8;
    padding: 4px 12px;
    text-align: center;
    color: #333;
  }

  table.contingency thead th,
  table.contingency tbody th {
    background: #f0f0f0;
    color: #555;
    font-weight: 500;
  }

  .upset-wrap {
    overflow-x: auto;
  }

  .cooc-wrap {
    overflow-x: auto;
  }

  .upset {
    display: block;
    background: white;
  }

  .cooc {
    display: block;
    background: white;
  }

  .upset-topn {
    font-family: inherit;
    font-size: 12px;
    padding: 1px 6px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
    color: #333;
  }

  .upset-set {
    font-weight: normal;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px;
    color: #1a4a8a;
  }

  .filter-chips {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-left: 8px;
    vertical-align: middle;
  }

  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border: 1px solid #ccc;
    border-radius: 999px;
    background: #f4f4f4;
    font-size: 12px;
    font-weight: normal;
    color: #333;
  }

  .filter-chip .chip-value {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    color: #1a4a8a;
  }

  .filter-chip .chip-clear {
    margin: 0 0 0 2px;
    padding: 0 4px;
    border: none;
    background: transparent;
    color: #666;
    font-size: 12px;
    line-height: 1;
    cursor: pointer;
  }

  .filter-chip .chip-clear:hover {
    color: #000;
  }

  .sort-btn {
    border: none;
    background: transparent;
    padding: 0;
    font: inherit;
    color: inherit;
    cursor: pointer;
  }

  .sort-btn:hover {
    color: #1a4a8a;
  }

  .export-btn {
    display: inline-block;
    margin: 4px 0;
    padding: 2px 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: #fafafa;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: #555;
    cursor: pointer;
  }
  .export-btn:hover {
    background: #f0f0f0;
    color: #1a4a8a;
  }

  .abstract-cell {
    max-width: 720px;
    font-size: 12px;
    color: #444;
    line-height: 1.4;
  }

  .facet-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-family: system-ui, sans-serif;
    font-size: 12px;
  }

  .control-label {
    color: #666;
  }

  .toggle-btn {
    padding: 3px 10px;
    border: 1px solid #ccc;
    border-radius: 999px;
    background: white;
    color: #333;
    font-size: 12px;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
  }

  .toggle-btn:hover {
    background: #f4f4f4;
  }

  .toggle-btn.active {
    background: #222;
    color: white;
    border-color: #222;
  }

  .legend-item.static {
    cursor: default;
  }

  .legend-item.static:hover {
    background: none;
  }

  .table-section {
    margin-top: 24px;
    font-family: system-ui, sans-serif;
  }

  .table-section h2 {
    font-size: 16px;
    margin-bottom: 8px;
  }

  .count {
    font-weight: normal;
    color: #888;
    font-size: 14px;
  }

  .table-section button {
    margin-left: 8px;
    font-size: 12px;
    padding: 2px 8px;
    cursor: pointer;
  }

  .cooc-stats {
    margin: 8px 0 16px;
    padding: 12px 14px;
    border: 1px solid #e3e3e3;
    background: #fafafa;
    border-radius: 4px;
    font-size: 13px;
  }

  .cooc-stats-row {
    display: flex;
    gap: 32px;
    flex-wrap: wrap;
    align-items: flex-start;
  }

  .cooc-contingency {
    flex: 0 0 auto;
  }

  .cooc-cont-title {
    font-weight: 600;
    margin-bottom: 4px;
    font-size: 12px;
    color: #555;
  }

  .cont-tbl {
    width: auto;
    border-collapse: collapse;
    font-size: 12px;
  }

  .cont-tbl th,
  .cont-tbl td {
    padding: 3px 8px;
    border: 1px solid #ddd;
    text-align: center;
  }

  .cont-tbl thead th {
    background: #f0f0f0;
    font-weight: 600;
  }

  .cont-tbl tbody th {
    background: #f0f0f0;
    font-weight: 600;
    text-align: right;
  }

  .cont-tbl td.hi {
    background: rgba(46, 92, 158, 0.12);
    font-weight: 600;
  }

  .cont-tbl td.marg,
  .cont-tbl tr.marg-row th,
  .cont-tbl tr.marg-row td {
    color: #777;
    font-style: italic;
  }

  .cooc-numbers {
    flex: 1 1 240px;
    min-width: 220px;
  }

  .cooc-stat-row {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    padding: 3px 0;
    border-bottom: 1px dotted #e0e0e0;
  }

  .cooc-stat-label {
    color: #555;
  }

  .cooc-stat-val {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-weight: 600;
    color: #222;
  }

  .cooc-stat-note {
    margin-top: 8px;
    font-size: 12px;
    color: #666;
    line-height: 1.35;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  th, td {
    text-align: left;
    padding: 6px 8px;
    border-bottom: 1px solid #eee;
  }

  th {
    font-weight: 600;
    border-bottom: 2px solid #ccc;
  }

  tbody tr:hover {
    background: #f8f8f8;
  }
</style>
