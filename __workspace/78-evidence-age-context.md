# Evidence age and retrieval context

The owned Evidence used view now gives each linked observation an age relative to
the saved model-output event. Quote details include observation age at output
save, timestamp basis and the recorded receipt lag. Headline details include
published age and retrieval age at output save, publication-to-retrieval time,
and the provider-delay value saved with the headline.

Age values are derived only from the timestamps explicitly stored with the linked
output and context. Negative intervals or invalid links are presented as
Unavailable. This view does not label an old quote fresh, infer news suitability,
or imply source rights. Output-save time is the reference point, not the provider
request start time. A saved provider-delay value of zero is displayed as a stored
zero; it is not treated as evidence of zero real-world delay.

No new citation is inferred by timestamp proximity. Old unlinked outputs, broader
news suitability/rights coverage and depth provenance remain unresolved under
D16/D18 and the existing ledger. No broker, market or permission operation was
performed. Tests/build checks were not run for this slice.
