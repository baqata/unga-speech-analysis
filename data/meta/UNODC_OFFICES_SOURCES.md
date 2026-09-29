# UNODC field offices: country coverage

Verified 2026-09-26 from UNODC's own pages. Where they disagree, an office's own site takes precedence over the central field-offices page.

## Files

| File | What it holds |
| --- | --- |
| `unodc_offices.csv` | The top-level partition. Each country appears in at most one office. |
| `unodc_offices_nested.csv` | Country and programme offices that sit inside a regional office, such as Bolivia under ROCOL and Pakistan under ROCA. |
| `unodc_offices_partner_links.csv` | Partner-only links. These are not coverage and are not used for groups. |

## How the dashboard uses them

- **Office groups.** Every office that covers more than one country becomes a group: ROCOL, ROPAN, ROSEN, ROSAF, ROEA, ROMENA, OGCCR, ROCA, ROSA, ROSEAP, ROSEE and POUKR.
- **Single-country offices.** COFRB (Brazil), LPOMEX (Mexico) and CONIG (Nigeria) are shown as the country itself.
- **Host-only offices.** HQ (Austria), BRULO (Belgium) and NYLO (USA) are not groups.
- **Countries with no field office.** Member states outside every office form the group "Sin oficina de terreno / No field office" (46 states), together with the three host-only countries. UNODC does not publish an assignment for them. The label deliberately avoids claiming "covered from Headquarters", which would be an inference.
- **Non-member codes.** SXM, COK, NIU, PYF, NCL and XKX are dropped, since they have no General Debate speeches.

## Judgment calls

- **ROCOL.** Exactly ARG, BOL, CHL, COL, ECU, PRY, PER, URY. This matches the live contact page and UN job opening 310261 (2025). Brazil is excluded; older structures included it.
- **ROCA.** Uses the newer scope, "Afghanistan, Central Asia, Iran and Pakistan", taken from the Regional Representative pages.
- **ROMENA.** Includes both Syria (Regional Framework 2023-2028) and South Sudan (website, office in Juba).
- **ROSEAP.** Uses the 29 beneficiary countries of the 2025 evaluation. Australia, New Zealand and North Korea are partner-only.
- **ROSEN.** Uses the 22 countries from the July 2025 Regional Representative job opening. Nigeria belongs to CONIG.
- **ROSEE.** Türkiye is included as a beneficiary of the Regional Programme 2024-2029.
- **No office found.** Venezuela, Russia, Israel and Belarus are not listed by any office.

## Key sources

- https://www.unodc.org/unodc/en/field-offices.html
- https://www.unodc.org/rocol/es/contacto.html ; https://unjoblink.org/job/details/310261/
- https://www.unodc.org/ropan/en/en-qu-pases-estamos.html
- https://www.unodc.org/westandcentralafrica/en/west-africa.html ; https://www.impactpool.org/jobs/1161004
- https://www.unodc.org/rosaf/en/about-us.html
- https://www.unodc.org/roea/en/framework.html
- https://www.unodc.org/romena/en/contact-us.html
- https://www.unodc.org/roca/en/regional-representative.html
- https://www.unodc.org/documents/southasia//publications/UNODC_Regional_Programme_for_South_Asia_2024-2028.pdf
- https://www.unodc.org/roseap/en/where-we-work/index.html
- https://www.unodc.org/rosee/en/main-menu/regional-office-for-south-eastern-europe.html
- https://www.unodc.org/poukr/index.html
- https://www.unodc.org/lpomex/es/UNODC-en-Mexico/quienes-somos.html
- https://www.unodc.org/cofrb/en/sobre/o-unodc.html
