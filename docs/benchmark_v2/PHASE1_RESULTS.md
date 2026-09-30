# Phase 1 results — the v2 route list (2026-10-01)

**Status:** complete, awaiting Ishan + professor review (Gate 3) before any Phase 2 (Google Routes) calls.
Definitions: [METHODOLOGY.md](METHODOLOGY.md) · decisions: [DECISIONS.md](DECISIONS.md) (D-02…D-24) · file columns: [DATA_DICTIONARY.md](DATA_DICTIONARY.md) · runs: [RUN_LOG.md](RUN_LOG.md) (R-03…R-12).

## 1. Summary
| Item | Result |
|---|---|
| Landmarks drafted | 70 (`landmarks_seed.csv`) |
| Geocoded (Places Text Search) | 72 calls in total (70 + 2 re-queries), all successful, ≈ $0 (free cap) |
| Automatic checks | 47 OK · 23 flagged |
| Human review (Gate 2) | 19 flagged approved (correct place; name wording or large-site snap) · 4 dropped · 1 replaced (Lalbagh Main Gate → Lalbagh Metro Station, passed) |
| **Usable landmarks** | **66** (47 OK + 19 APPROVED); 64 are used by at least one route |
| Candidate routes | 2,059 pairs (straight line 0.7–22 km) → 2,019 eligible |
| **Selected routes** | **72**, exactly 4 in each of the 18 groups (3 bands × 3 road types × 2 hotspot exposure) |
| Route length | 1.3 – 23.9 km, median 9.7 km (band medians 3.7 / 9.7 / 15.3 km) |
| Road type | median arterial share: arterial 0.79 · mixed 0.50 · sub-arterial 0.22 |
| Hotspot exposure | median share on hotspot legs: high 0.78 · low 0.38 |
| Endpoint kinds | metro 40 · junction 36 · hospital 14 · bus station 12 · landmark 11 · mall 10 · tech park 9 · rail 7 · campus 5 |
| Endpoint zones | East 34 · Central 31 · South 31 · West 29 · North 19 |
| Queries this implies | 72 × 28 = **2,016** Google + 2,016 LLM (condition A) |
| Determinism | same inputs → identical `od_pairs.csv` (md5 checked) |

## 2. Landmark review outcome (Gate 2)
- **Dropped (4):** L09 Bangalore Palace (point 493 m inside grounds) · L19 IISc Main Gate (two queries both returned campus centroid, 282 m from road) · L44 RMZ Ecospace (Google returned a different park, RMZ Ecoworld, ~1 km away) · L54 Electronic City Metro (outside local OSM map / BBMP limits).
- **Replaced (1):** L07 Lalbagh Main Gate → **Lalbagh Metro Station** (garden centroid was 276 m from road).
- **Approved despite flag (19):** 14 correct places whose Google name differs from the everyday name (e.g. "MG Road Metro Station" = Google's "Mahatma Gandhi Road" subway station); 5 large sites 151–202 m from the nearest road (Embassy Tech Village, ITPL, Phoenix Marketcity, IIM Bangalore, NIMHANS).
- All decisions with reasons: `data/benchmark_v2/review_decisions.csv`.

## 3. Caveats to keep in mind
1. **Tags are provisional.** Band, road type and hotspot exposure come from the OSM shortest path. Phase 2 recomputes them from Google's actual route; some routes may change group.
2. **Hotspot exposure is relative** (above/below the band median, D-17). A "low" 12–25 km route can still have ~50 % of its length on hotspot legs, because the band median is 0.60.
3. Only **one route is under 2 km** (R055 Trinity Circle → MG Road Metro, 1.3 km; both compact). The 1–5 km band is mostly 2–5 km.
4. North has the fewest endpoints (19) — fewer landmarks there inside BBMP limits.
5. Large-site endpoints (19 of 144 endpoints) are points inside the site; Google Routes starts from the nearest road. Phase 2 records Google's actual start/end point.
6. 2 usable landmarks ended up unused (L42 Hope Farm Junction, L60 Konanakunte Cross Metro) because of the 3-uses cap and near-duplicate rule.

## 4. Figures (`data/benchmark_v2/figures/phase1/`)
| Plot | What it shows |
|---|---|
| p1_landmarks_map.png | all 70 landmarks at Google coordinates; flagged/dropped circled |
| p2_geocode_quality.png | pass/flag per check; distance-to-road histogram |
| p3_hotspot_legs_map.png | 564 plausible Stage-4 legs; 113 hotspots in red |
| p4_selected_routes_map.png | the 72 routes, coloured by band, dashed = high hotspot exposure |
| p5_group_fill_heatmap.png | 4 per group, and how many were eligible in each |
| p6_selected_vs_candidates.png | selected vs eligible length and arterial-share distributions |
| p7_landmark_usage_zones.png | routes per landmark; endpoints per zone |
| p8_detour_factor.png | OSM length vs straight line; median detour **1.22×** (input to the naive baseline) |
QGIS: open `data/benchmark_v2/od_pairs.geojson` (routes) and `hotspot_legs.geojson`.

## 5. The 72 routes
The origin/destination text is exactly what the LLM will receive; Google receives the coordinates in `od_pairs.csv`.

| Route | Origin → Destination (exact LLM strings) | OSM km | Band | Road type (arterial share) | Hotspot exposure (share) |
|---|---|---|---|---|---|
| R001 | Tin Factory Junction → Baiyappanahalli Metro Station | 3.4 | 1-5km | arterial (0.99) | high (1.00) |
| R002 | Shivajinagar Bus Station → Mekhri Circle | 4.7 | 1-5km | arterial (0.66) | low (0.40) |
| R003 | Victoria Hospital → Shivajinagar Bus Station | 4.5 | 1-5km | mixed (0.50) | high (0.78) |
| R004 | Town Hall → Richmond Circle | 2.8 | 1-5km | mixed (0.47) | low (0.50) |
| R005 | Banashankari Bus Station → Lalbagh Metro Station | 3.7 | 1-5km | sub-arterial (0.34) | high (0.56) |
| R006 | Rajajinagar Metro Station → Mantri Square Mall | 3.6 | 1-5km | sub-arterial (0.06) | low (0.34) |
| R007 | Richmond Circle → Baiyappanahalli Metro Station | 7.9 | 5-12km | arterial (0.96) | high (0.96) |
| R008 | Deepanjali Nagar Metro Station → Kengeri Bus Terminal | 8.0 | 5-12km | arterial (0.92) | low (0.26) |
| R009 | Bengaluru Cantonment Railway Station → Mysore Road Metro Station | 10.2 | 5-12km | mixed (0.60) | high (0.82) |
| R010 | IIM Bangalore → Manipal Hospital Old Airport Road | 11.8 | 5-12km | mixed (0.59) | low (0.37) |
| R011 | Jayanagar Metro Station → Iblur Junction | 10.5 | 5-12km | sub-arterial (0.39) | high (0.53) |
| R012 | Bull Temple Basavanagudi → HSR Layout BDA Complex | 10.4 | 5-12km | sub-arterial (0.19) | low (0.15) |
| R013 | Iblur Junction → Deepanjali Nagar Metro Station | 16.4 | 12-25km | arterial (0.81) | high (0.75) |
| R014 | IIM Bangalore → Rajarajeshwari Nagar Metro Station | 12.7 | 12-25km | arterial (0.74) | low (0.28) |
| R015 | Sony World Junction → MS Ramaiah Hospital | 14.1 | 12-25km | mixed (0.50) | high (0.80) |
| R016 | KR Puram Railway Station → Carmelaram Railway Station | 13.1 | 12-25km | mixed (0.51) | low (0.27) |
| R017 | Baiyappanahalli Metro Station → BEL Circle | 15.3 | 12-25km | sub-arterial (0.36) | high (0.69) |
| R018 | Vijayanagar Metro Station → Yelahanka Railway Station | 19.5 | 12-25km | sub-arterial (0.08) | low (0.19) |
| R019 | Rajarajeshwari Nagar Metro Station → Vijayanagar Metro Station | 5.0 | 1-5km | arterial (0.94) | high (0.72) |
| R020 | Magadi Road Metro Station → Sumanahalli Junction | 4.9 | 1-5km | arterial (0.89) | low (0.16) |
| R021 | Richmond Circle → Forum Mall Koramangala | 4.8 | 1-5km | mixed (0.59) | high (0.65) |
| R022 | Nagarbhavi Circle → Deepanjali Nagar Metro Station | 3.3 | 1-5km | mixed (0.45) | low (0.27) |
| R023 | Vidhana Soudha → Trinity Circle | 3.8 | 1-5km | sub-arterial (0.25) | high (0.57) |
| R024 | Sony World Junction → St. John's Medical College Hospital | 2.0 | 1-5km | sub-arterial (0.36) | low (0.43) |
| R025 | Shivajinagar Bus Station → Esteem Mall Hebbal | 10.3 | 5-12km | arterial (0.76) | high (0.65) |
| R026 | Magadi Road Metro Station → Kengeri Bus Terminal | 11.8 | 5-12km | arterial (0.70) | low (0.17) |
| R027 | MG Road Metro Station → Jayadeva Hospital | 7.5 | 5-12km | mixed (0.49) | high (0.86) |
| R028 | Jayadeva Hospital → Nagarbhavi Circle | 11.7 | 5-12km | mixed (0.47) | low (0.12) |
| R029 | Rajajinagar Metro Station → Jayanagar Metro Station | 10.1 | 5-12km | sub-arterial (0.27) | high (0.62) |
| R030 | Royal Meenakshi Mall → HSR Layout BDA Complex | 8.7 | 5-12km | sub-arterial (0.04) | low (0.25) |
| R031 | Kundalahalli Gate → Town Hall | 16.3 | 12-25km | arterial (1.00) | high (0.89) |
| R032 | Nagarbhavi Circle → Carmelaram Railway Station | 23.9 | 12-25km | arterial (0.64) | low (0.50) |
| R033 | Phoenix Marketcity → Mekhri Circle | 14.6 | 12-25km | mixed (0.56) | high (0.61) |
| R034 | Silk Institute Metro Station → Halasuru Metro Station | 19.4 | 12-25km | mixed (0.55) | low (0.46) |
| R035 | St. John's Medical College Hospital → ITPL Whitefield | 17.9 | 12-25km | sub-arterial (0.40) | high (0.79) |
| R036 | Iblur Junction → Peenya Metro Station | 23.5 | 12-25km | sub-arterial (0.27) | low (0.52) |
| R037 | KR Puram Railway Station → Phoenix Marketcity | 2.8 | 1-5km | arterial (0.76) | high (0.79) |
| R038 | Mysore Road Metro Station → RV College of Engineering | 5.0 | 1-5km | arterial (0.88) | low (0.35) |
| R039 | Lalbagh Metro Station → Town Hall | 2.1 | 1-5km | mixed (0.52) | high (1.00) |
| R040 | Silk Board Junction → Sony World Junction | 3.8 | 1-5km | mixed (0.59) | low (0.47) |
| R041 | Esteem Mall Hebbal → Manyata Tech Park | 3.7 | 1-5km | sub-arterial (0.00) | high (0.52) |
| R042 | ISKCON Temple Rajajinagar → Sumanahalli Junction | 4.8 | 1-5km | sub-arterial (0.03) | low (0.17) |
| R043 | Manipal Hospital Old Airport Road → Bull Temple Basavanagudi | 10.8 | 5-12km | arterial (0.67) | high (0.83) |
| R044 | RV College of Engineering → Vijayanagar Metro Station | 7.9 | 5-12km | arterial (0.97) | low (0.48) |
| R045 | Halasuru Metro Station → Banashankari Bus Station | 10.6 | 5-12km | mixed (0.46) | high (0.85) |
| R046 | Rajajinagar Metro Station → RV College of Engineering | 12.0 | 5-12km | mixed (0.51) | low (0.42) |
| R047 | Banashankari Bus Station → Kempegowda Bus Station (Majestic) | 7.6 | 5-12km | sub-arterial (0.35) | high (0.66) |
| R048 | Kempegowda Bus Station (Majestic) → Jalahalli Cross | 10.1 | 5-12km | sub-arterial (0.39) | low (0.41) |
| R049 | Forum Mall Koramangala → Tin Factory Junction | 12.5 | 12-25km | arterial (0.61) | high (0.66) |
| R050 | Manipal Hospital Old Airport Road → Sumanahalli Junction | 16.5 | 12-25km | arterial (0.87) | low (0.54) |
| R051 | HSR Layout BDA Complex → Hoodi Metro Station | 15.4 | 12-25km | mixed (0.47) | high (0.85) |
| R052 | Nagasandra Metro Station → Mekhri Circle | 12.5 | 12-25km | mixed (0.57) | low (0.47) |
| R053 | MS Ramaiah Hospital → Jayanagar Metro Station | 13.0 | 12-25km | sub-arterial (0.13) | high (0.61) |
| R054 | Bull Temple Basavanagudi → Manyata Tech Park | 14.7 | 12-25km | sub-arterial (0.24) | low (0.55) |
| R055 | Trinity Circle → MG Road Metro Station | 1.3 | 1-5km | arterial (0.72) | high (0.79) |
| R056 | Jayadeva Hospital → Silk Board Junction | 3.0 | 1-5km | arterial (0.97) | low (0.17) |
| R057 | Yeshwanthpur Metro Station → Peenya Metro Station | 3.2 | 1-5km | mixed (0.40) | high (0.62) |
| R058 | Victoria Hospital → Magadi Road Metro Station | 3.2 | 1-5km | mixed (0.59) | low (0.18) |
| R059 | Marathahalli Bridge → Embassy Tech Village | 4.3 | 1-5km | sub-arterial (0.00) | high (0.84) |
| R060 | Embassy Tech Village → Carmelaram Railway Station | 3.6 | 1-5km | sub-arterial (0.00) | low (0.00) |
| R061 | Trinity Circle → Phoenix Marketcity | 9.3 | 5-12km | arterial (0.95) | high (0.96) |
| R062 | St. John's Medical College Hospital → Bagmane Tech Park | 9.2 | 5-12km | arterial (0.60) | low (0.41) |
| R063 | Indiranagar Metro Station → Lalbagh Metro Station | 8.5 | 5-12km | mixed (0.50) | high (0.82) |
| R064 | Embassy GolfLinks Business Park → Bagmane Tech Park | 6.6 | 5-12km | mixed (0.45) | low (0.40) |
| R065 | Tin Factory Junction → Hennur Cross | 7.3 | 5-12km | sub-arterial (0.05) | high (0.54) |
| R066 | BEL Circle → Mantri Square Mall | 7.6 | 5-12km | sub-arterial (0.07) | low (0.40) |
| R067 | Hennur Cross → Whitefield (Kadugodi) Metro Station | 17.0 | 12-25km | arterial (0.61) | high (0.67) |
| R068 | Kengeri Bus Terminal → Kempegowda Bus Station (Majestic) | 13.8 | 12-25km | arterial (0.77) | low (0.39) |
| R069 | Kundalahalli Gate → Hennur Cross | 15.7 | 12-25km | mixed (0.56) | high (0.84) |
| R070 | Peenya Metro Station → NIMHANS | 14.3 | 12-25km | mixed (0.48) | low (0.51) |
| R071 | Kudlu Gate Metro Station → Marathahalli Bridge | 12.0 | 12-25km | sub-arterial (0.04) | high (0.80) |
| R072 | Whitefield (Kadugodi) Metro Station → Manyata Tech Park | 20.8 | 12-25km | sub-arterial (0.26) | low (0.36) |
