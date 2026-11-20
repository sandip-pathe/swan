# Mobile market depth

Implemented 20 November 2026. The user explicitly asked to skip M3 evidence/manual
work and continue implementation. Those checks remain deferred, not passed.

## Delivered

A Depth tab beside Chart and Details shows up to five retained bid/ask levels,
quote time, freshness, spread and source receipt information. It uses the same
selected-contract quote/polling/refresh as the other tabs; no competing feed or
provider request was introduced. The price chart stays mounted when tabs change.

When only top bid/ask is retained, show those prices with an explanation that
additional levels are unavailable. Preserve partial/asymmetric books and missing
levels. No quote has a meaningful empty state; older/future/error observations
cannot acquire a Recent quote label. Crossed top prices receive a notice and no
usable spread. This is display only and changes no execution permissions.

Quantity columns require both units/lots and a nonempty quantity_unit_source on
the normalized quote. Unknown units or absent provenance hide quantities even
when numeric payload values exist. Do not infer units from lot size, convert lots
to units, expose hidden raw counts or imply complete exchange-book visibility.
Existing real-account quantity verification is still unresolved.

The mobile table has four columns, semantic headers/caption, explicit bid/ask
labels, formatted numeric values and missing-value marks. Color is supplemental.
The three tabs retain 44px minimum touch targets and fit the 360px layout.

## Verification

Frontend type checking, ten existing calculation/preference tests and production
build pass. Browser fixtures at 360, 390, 430, 768, 1440 and landscape 844 pass
navigation, depth rendering, chart controls and offline behavior with no overflow
or browser exceptions. Additional 390px cases cover unknown quantities hidden,
verified units and lots, asymmetric five/two levels, and top-of-book fallback.
Visual review inspected the 360px depth screenshot. Actual localhost mobile
sign-in/PWA smoke passes. All displayed test prices remain isolated fixtures.

Backend code was unchanged; the preceding full backend suite passed 178 tests.
No provider calls, login, manual evidence collection or worker restart were
performed for this slice. Local environment/setup edits remain outside commits.

Next workspace slice: underlying reference and ATM context, then the manual paper
order preview/intent design. Depth/fee evidence remains a dependency for execution
qualification; deferred M3 evidence is not required to continue UI implementation.
