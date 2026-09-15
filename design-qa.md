# P-Heritage-Portal-UI-01 Design QA

## Comparison target

- Source visual truth: `H:\my_code\datak\docs\前端修改\01.png` through `10.png`
- Primary implementation: `http://127.0.0.1:3000/`
- Desktop screenshots: `H:\my_code\datak\docs\heritage-portal-ui\screenshots\desktop-*-1440x900.png`
- Mobile screenshots: `H:\my_code\datak\docs\heritage-portal-ui\screenshots\mobile-*-390x844.png`
- Viewports: desktop `1440 × 900`; mobile `390 × 844`
- State: local FastAPI + SQLite real data; authentication bypass follows existing `AUTH_ENABLED=false`; compare page uses park IDs `1,2,3`; map key is intentionally absent and therefore displays the documented configuration error state.

## Evidence

- Full-page, same-input comparison for all ten desktop references and implementations: `H:\my_code\datak\docs\heritage-portal-ui\screenshots\design-qa-all-pages-comparison.png`
- Primary home comparison at readable scale: `H:\my_code\datak\docs\heritage-portal-ui\screenshots\design-qa-comparison-home.png`
- Desktop implementation contact sheet: `H:\my_code\datak\docs\heritage-portal-ui\screenshots\design-qa-desktop-contact-sheet.png`
- Mobile implementation contact sheet: `H:\my_code\datak\docs\heritage-portal-ui\screenshots\design-qa-mobile-contact-sheet.png`
- Focused region comparison was not required: the primary home comparison preserves the header, hero, statistics, CTA and first tool row at readable scale; dense functional pages are also preserved as individual original-size screenshots.

## Findings

No actionable P0/P1/P2 findings remain.

- Typography: system Chinese sans-serif fallbacks, display weights, body line height and small-label hierarchy are consistent with the references. The source did not provide a licensed font file, so a system stack is an acceptable implementation constraint.
- Spacing and layout rhythm: the portal header, hero, overlapping statistics strip, card grid, page heroes and dense research workspaces preserve the source hierarchy. The implementation deliberately removes the global sidebars visible in references 05, 08 and 09 because the written specification explicitly overrides them with one PortalHeader.
- Colors and tokens: the white/blue surfaces, dark navy text, restrained border/shadow system and semantic green/violet/orange accents map consistently to the source direction. No CSS gradients were substituted for source assets.
- Image quality: the hero, assistant and park fallback images are real raster WebP assets generated for their measured slots, with appropriate crop and compression. No inline SVG, emoji, CSS art or placeholder boxes replace visible source imagery.
- Copy and content: static labels follow the product specification; all statistics, park records, scores, knowledge documents and chart values come from existing APIs rather than mock or random data.
- Responsiveness: desktop and mobile captures have no horizontal viewport overflow; mobile navigation collapses to a menu and the map filters move into a bottom drawer.
- States and accessibility: loading, empty and error states are explicit; the missing AMap key is presented as a configuration error instead of a fake map. Header, navigation, buttons, headings, form labels and image alt text are present.

## Comparison history

### Iteration 1

- Earlier finding: [P1] `ResearchData.vue` initialized ECharts while its loading branch still owned the DOM, so the page fell into an error state.
- Fix: completed the loading transition before `nextTick()` and chart initialization.
- Post-fix evidence: `desktop-research-data-1440x900.png` shows three real-data charts; browser inspection reported three non-zero canvases and no error state.

### Iteration 2

- Earlier finding: [P1] `Bibliometrics.vue` had the same mount-order issue, leaving the trend and type charts visually blank.
- Fix: completed the loading transition before chart initialization.
- Post-fix evidence: `desktop-bibliometrics-1440x900.png` shows trend, type and keyword charts; browser inspection reported five chart canvases and no error state.

### Iteration 3

- Earlier finding: [P2] the first comparison-page screenshot used an empty initial state while reference 05 showed an active comparison.
- Fix: captured and verified the real `park_ids=1,2,3` state without adding fake data.
- Post-fix evidence: `desktop-compare-1440x900.png` shows three selected parks, two rendered charts and three real-data table rows.

### Iteration 4

- Earlier finding: [P2] the comparison page eagerly initialized the hidden “指标对比” canvas, producing an ECharts zero-size warning.
- Fix: changed comparison charts to lazy initialization by active tab and resize only the visible chart set.
- Post-fix evidence: a fresh browser tab rendered the dimension charts, switched to the indicator chart, reported three valid canvases, no overflow and zero console warnings or errors.

## Runtime verification

- Primary interactions tested: desktop/mobile navigation, mobile menu, park keyword filter, park detail route, map filter and mobile filter drawer, real park comparison, knowledge search and AI question input.
- Fresh in-app browser sweep: ten target routes, no unexpected horizontal overflow and no global left sidebar.
- Fresh console check after fixes: zero warnings or errors.
- Automated verification: lint passed; typecheck passed; 3 unit tests passed; 12 Playwright desktop/mobile tests passed; production build passed.

## Follow-up polish

- [P3] The desktop header uses an icon-triggered global search rather than the wider inline search field shown in some references. This keeps ten navigation items readable at 1440px and still provides the required search entry.
- [P3] A configured AMap key will enable the final basemap/marker visual comparison; the current missing-key state is the expected safe fallback.

final result: passed
