<script lang="ts">
  import { scaleLinear, scaleOrdinal, scaleBand } from 'd3-scale';
  import { schemeTableau10 } from 'd3-scale-chromatic';
  import { SvelteMap } from 'svelte/reactivity';
  import data from '$lib/data/methods_viz.json';
  import locationsData from '$lib/data/locations_viz.json';

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

  const papers: Paper[] = data as Paper[];

  const methodCategories = [
    'qual',
    'quant',
    'mixed',
    'descriptive-empirical',
    'theoretical-conceptual',
    'spatial',
    'unclear'
  ] as const;

  // From classify/schemas/prompts/v3/categories/methods_01.csv
  const methodDescriptions: Record<string, string> = {
    'qual': 'qualitative methods (interviews, ethnography, focus groups, archival analysis, discourse analysis, single in-depth case study)',
    'quant': 'non-spatial quantitative methods (standard regression, t-tests, ANOVA, large-N surveys, modeling, formal hypothesis testing)',
    'mixed': 'mixed methods — qualitative AND quantitative carry comparable weight, neither is clearly primary',
    'spatial': "geography is core to the methodology — GIS, cartography, remote sensing, geospatial visualization, OR spatial statistical methods (GWR, Moran's I, kriging, spatial lag/error, point-pattern analysis, remote-sensing classification)",
    'descriptive-empirical': 'original empirical work that describes a phenomenon without inferential testing — case-study description, named-corpus literature review, agenda-setting piece comparing specific cases',
    'theoretical-conceptual': 'conceptual essay or position paper with no original empirical data — argues for a framework, reframes a debate, or synthesizes existing literature without analyzing new cases',
    'unclear': 'methodology cannot be determined from the title and abstract',
  };

  const color = scaleOrdinal<string, string>()
    .domain(methodCategories as unknown as string[])
    .range(schemeTableau10);

  // Bar chart dimensions
  const barWidth = 600;
  const barHeight = 500;
  const barMargin = { top: 20, right: 20, bottom: 50, left: 60 };

  // 5-year bucketing anchored at 1992 (data range 1992–2026). Labels are bucket start years.
  const decades = ['1992', '1997', '2002', '2007', '2012', '2017', '2022'] as const;

  function getDecade(year: string): string {
    const y = parseInt(year, 10);
    const clamped = Math.max(1992, Math.min(2026, y));
    return String(1992 + Math.floor((clamped - 1992) / 5) * 5);
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

  const decadeProportions: DecadeData[] = decades.map((decade) => {
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
  });

  // Bar chart scales
  const xBand = scaleBand<string>()
    .domain([...decades])
    .range([barMargin.left, barWidth - barMargin.right])
    .padding(0.2);

  const yBar = scaleLinear()
    .domain([0, 1])
    .range([barHeight - barMargin.bottom, barMargin.top]);

  let selectedMethod: string | null = $state(null);

  const filteredPapers = $derived(
    selectedMethod !== null ? papers.filter((d) => d.method === selectedMethod) : []
  );

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
    return `${start}–${start + 4}`;
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

  const filteredLocations = $derived(
    selectedRegion !== null ? locations.filter((d) => d.region === selectedRegion) : []
  );

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
</script>

<h1>Methods classification across rural geography (1992–2026)</h1>
<p class="caption">
  Predicted by Gemma 4 31B on {papers.length} papers (snapshot: 2026-05-20_1458_methods_v3_sections_full). The 2022–2026 bucket includes partial 2026.
</p>

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

<div class="charts-row">
<svg width={barWidth} height={barHeight} class="bar-chart">
  <!-- Y-axis label -->
  <text
    x={-(barHeight / 2)}
    y={16}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Proportion</text>

  <!-- Y-axis ticks -->
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

  <!-- X-axis decade labels -->
  {#each decades as decade (decade)}
    <text
      x={(xBand(decade) ?? 0) + xBand.bandwidth() / 2}
      y={barHeight - barMargin.bottom + 20}
      text-anchor="middle"
      font-size="12"
      fill="#333"
    >{decade}</text>
  {/each}

  <!-- X-axis label -->
  <text
    x={(barMargin.left + barWidth - barMargin.right) / 2}
    y={barHeight - 8}
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Year (5-year buckets)</text>
</svg>

<section class="facets" aria-label="Method proportion over time">
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

<h2 class="section-h2">Region across rural geography (1992–2026)</h2>
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

<div class="charts-row">
<svg width={barWidth} height={barHeight} class="bar-chart">
  <!-- Y-axis label -->
  <text
    x={-(barHeight / 2)}
    y={16}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Proportion</text>

  <!-- Y-axis ticks -->
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

  <!-- X-axis decade labels -->
  {#each decades as decade (decade)}
    <text
      x={(xBand(decade) ?? 0) + xBand.bandwidth() / 2}
      y={barHeight - barMargin.bottom + 20}
      text-anchor="middle"
      font-size="12"
      fill="#333"
    >{decade}</text>
  {/each}

  <!-- X-axis label -->
  <text
    x={(barMargin.left + barWidth - barMargin.right) / 2}
    y={barHeight - 8}
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Year (5-year buckets)</text>
</svg>

<section class="facets" aria-label="Region proportion over time">
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

<h2 class="section-h2">Methods by region: USA vs non-USA (1992–2026)</h2>
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

<div class="charts-row">
<svg width={barWidth} height={barHeight} class="bar-chart">
  <text
    x={-(barHeight / 2)}
    y={16}
    transform="rotate(-90)"
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Proportion</text>

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

  {#each decades as decade (decade)}
    <text
      x={(xBand(decade) ?? 0) + xBand.bandwidth() / 2}
      y={barHeight - barMargin.bottom + 20}
      text-anchor="middle"
      font-size="12"
      fill="#333"
    >{decade}</text>
  {/each}

  <text
    x={(barMargin.left + barWidth - barMargin.right) / 2}
    y={barHeight - 8}
    text-anchor="middle"
    font-size="12"
    fill="#666"
  >Year (5-year buckets)</text>
</svg>

<section class="facets" aria-label="Methods USA vs non-USA over time">
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

{#if selectedRegion !== null}
  <div class="table-section">
    <h2>
      Region: {selectedRegion}
      <span class="count">({filteredLocations.length} papers)</span>
      <button onclick={() => (selectedRegion = null)}>Clear</button>
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
        {#each filteredLocations as p (p.doi)}
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

{#if selectedMethod !== null}
  <div class="table-section">
    <h2>
      Methods: {selectedMethod}
      <span class="count">({filteredPapers.length} papers)</span>
      <button onclick={() => (selectedMethod = null)}>Clear</button>
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
        {#each filteredPapers as p (p.doi)}
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
