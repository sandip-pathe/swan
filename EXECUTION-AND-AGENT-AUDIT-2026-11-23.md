# Execution and agent-system audit, 23 November 2026

The earlier two live-data paper trades were manual. The local validation script
saved manual plans and submitted them through `ManualPaperService`. Agents did
not select the contracts, levels or entry times. The watchdog handled their exits.
They verify execution plumbing, not autonomous strategy selection.

## Corrections made

| Finding | Correction | Evidence |
| --- | --- | --- |
| The paper model admitted only 10% of visible quantities. This was a configurable assumption, not an Angel One limit. | The owner-authorized paper configuration now allows up to 100% of actual displayed depth. Consumption budgets, slippage, freshness, spread and risk checks remain. | Audited `SETUP_CONFIGURATION_UPDATED`, config version `paper-displayed-depth-20261123-v2`. |
| A valuation-driven pause of new entries forced manual holdings to exit because protection treated `account.enabled == false` as session termination. | Protection validates the original holding's bounded lease independently of the entry-enable flag. Unavailable valuation still blocks new entries and reports unavailable equity. It does not manufacture a liquidation value. | Both new regression cases failed before the fix and passed afterward. |
| Chat's stop-new-entries command also forced manual liquidation through the same path. | Entry-only session stops preserve the held position's stop, target and maximum hold. Explicit lease stop, expiry, feed failure, daily-loss protection and user exits still operate. | Regression covers both entry-only pause causes; existing explicit-stop and protection tests pass. |
| The protection valuation clock was captured before waiting for the account lock. | Read the clock after locking, as other serialized execution operations do. | Existing concurrent clock regressions and the protection suite. |
| The generic agent context omitted the execution model and did not distinguish planning evidence age from fill-time freshness. | Context now includes the versioned execution model, its mapping evidence and fee assumptions, plus explicit planning/execution semantics. No executor freshness check changed. | Persisted real-provider context for the corrected audit. |
| A real model response mixed a news ID into market evidence citations. | Added separate allowed market and news ID lists and clear role instructions. Strict citation validation remains unchanged. | First audit rejected the invalid citation. The corrected real-provider run passed both executed stages. |

The 100% setting is a paper simulation choice. It does not model queue position,
other traders consuming the same book, or hidden liquidity. It is not a guarantee
that a real broker order would receive the modeled fill.

## Actual agent checks

First read-only trial: `cff8bc8e-75fb-4807-baf5-7ea9b7a70ee1`.
Analysis passed. Proposal returned WAIT but contained an invalid market citation,
which the validator rejected. No order was created.

Corrected read-only trial: `df7c226f-e215-4deb-957e-4147c5289cca`.
The configured `gpt-6.1-sol` provider processed eight actual option observations
and attributed delayed news. Analysis and proposal validation passed. The result
was WAIT because single option snapshots and session aggregates did not supply a
recent underlying series or a supported entry/stop/target setup. That is a valid
abstention, not a profitable strategy demonstration. Review was not called after
WAIT. Order count remained nine before and after both read-only trials.

Private evidence:
`.local/run/agent-system-audit-2026-11-23.json` and
`.local/run/agent-system-audit-corrected-2026-11-23.json`.
The latter retains actual model outputs and stage checks.

## Remaining integration findings

1. **ORB data production is not automatic.** `refresh_index_history` in
   `services/api/index_history.py` fetches completed index bars, persists the
   assessment and queues eligible watcher work. The API's background assignment
   consumer exists, but no worker job currently drives that index-history refresh.
   Polling a queue does not produce its market events. The owner account had zero
   durable assignments and zero paper-plan candidates at audit time.
2. **Two strategy paths coexist.** The generic worker pipeline proposes from
   option snapshots and news. The predefined ORB workflow reasons over index
   history and deterministic assessments. The worker preserves an already active
   ORB envelope, but pending ORB work is not an explicit priority gate before generic
   evaluation. The intended predefined-first behavior is not established end to end.
3. **The generic path lacks sufficient strategy evidence.** It does not receive
   the ORB assessment, recent index bars or a general quantitative-tool result set.
   The real model correctly refused to infer a short-horizon trade from snapshots.
   Supplying the execution policy fixes missing policy context, not missing signals.
4. **Conservative model limits remain visible.** Sale proceeds stay restricted
   under the reviewed policy. Durable liquidity budgets do not infer hidden book
   replenishment. Existing budgets reject incompatible configuration versions at
   the same session/price. The 5-second entry lifetime is a maximum; approval
   evidence freshness can expire an order earlier. These constraints must not be
   reported as missing Angel One data or relaxed silently to obtain a fill.

The next integration slice should give the predefined workflow one execution
owner: scheduled completed-index-bar acquisition within the mandate window,
durable assessment events, analyst/reviewer output, candidate staging, then the
existing separately authorized paper admission. Reuse shared provider rate limits,
fixed deadlines, deduplication and restart recovery. Define explicit fallback
eligibility before allowing generic proposals to preempt predefined work.
Do not fabricate an ORB opportunity outside its time window, qualification or an
arm to demonstrate the flow.

## Verification and operating state

The new execution regressions and existing manual/session-stop suite passed.
The agent run/check/evidence/workflow suites passed. Ruff and targeted mypy passed
for the changed modules. The final full suite passed: 406 tests, with one existing Starlette/httpx deprecation warning.
The API and observation worker are reloaded after verification. Entries stay
paused and no position is open. This audit did not place another paper trade or
any broker order. Live holding behavior after these fixes remains to be accepted
in a separate bounded session; passing regressions alone does not close it.
