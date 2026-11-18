"""Read-only paper configuration diagnostics. These never enable an execution engine."""

from datetime import date
from pathlib import Path

from pydantic import ValidationError

from services.core.execution import REQUIRED_FEE_CODES, PaperExecutionConfig

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "paper-execution.json"


def evidence_requirements(config: PaperExecutionConfig, day: date) -> list[dict]:
    """Explain current blockers from the parsed policy, without approving any input."""
    requirements = []

    def add(
        code: str,
        title: str,
        detail: str,
        action: str,
        fields: list[str],
        sources: list[str] | None = None,
    ):
        requirements.append(
            {
                "code": code,
                "title": title,
                "detail": detail,
                "action": action,
                "fields": fields,
                "sources": sources or [],
            }
        )

    for code in config.execution.blockers():
        if code == "QUANTITY_UNIT_UNVERIFIED":
            add(
                code,
                "Verify displayed depth quantity units",
                "REST and WebSocket depth must have verified units for both NFO and BFO. Order-entry quantity documentation alone does not establish depth units.",
                "Record provider confirmation or explicit protocol evidence, corroborate it with actual observations, then review the mapping. Do not infer units from lot-size divisibility.",
                ["execution.quantity_unit", "execution.quantity_unit_sources"],
                list(dict.fromkeys(str(s.url) for s in config.execution.quantity_unit_sources)),
            )
        else:
            fields = (
                ["execution." + code.removesuffix("_REQUIRED").lower()]
                if code.endswith("_REQUIRED")
                else ["execution.sale_proceeds_reuse", "execution.sale_proceeds_sources"]
                if code == "SALE_PROCEEDS_REUSE_UNVERIFIED"
                else ["execution.reviewed"]
            )
            add(
                code,
                code.replace("_", " ").capitalize(),
                "A reviewed execution-policy requirement is unresolved.",
                "Review the named policy field and its provenance before importing an update.",
                fields,
            )
    for venue in ("NFO", "BFO"):
        schedule = next(
            (s for s in config.fee_schedules if s.exchange == venue and s.applies(day)), None
        )
        if schedule is None:
            add(
                venue + "_FEE_SCHEDULE_MISSING",
                venue + " effective fee schedule missing",
                "No fee schedule covers " + day.isoformat() + ".",
                "Import a sourced, reviewed schedule covering this date; do not extend expiry without checking the tariff.",
                ["fee_schedules"],
            )
            continue
        prefix = f"fee_schedules[{schedule.version}]"
        for component in sorted(REQUIRED_FEE_CODES - {r.code for r in schedule.rules}):
            add(
                venue + "_FEE_COMPONENT_" + component + "_MISSING",
                venue + " " + component + " is unresolved",
                "The component is absent. Absence is not evidence of a zero charge.",
                "Obtain an explicit applicable broker/exchange source, including evidence if the component is zero.",
                [prefix + ".rules." + component],
            )
        unresolved = [
            (rule, source)
            for rule in schedule.rules
            for source in rule.sources
            if source.status == "unverified"
        ]
        if unresolved:
            add(
                venue + "_FEE_EVIDENCE_UNVERIFIED",
                venue + " fee evidence needs verification",
                " ".join(dict.fromkeys(source.finding for _, source in unresolved)),
                "Verify each affected component's rate, basis, rounding increment, rounding mode and allocation scope against explicit broker evidence. A tariff link alone does not establish rounding.",
                list(dict.fromkeys(prefix + ".rules." + rule.code for rule, _ in unresolved)),
                list(
                    dict.fromkeys(
                        str(source.url) for rule, _ in unresolved for source in rule.sources
                    )
                ),
            )
        if not schedule.account_pricing_verified:
            add(
                venue + "_ACCOUNT_PRICING_UNVERIFIED",
                venue + " account pricing is unconfirmed",
                "The schedule has not been matched to the account's pricing plan.",
                "Confirm the applicable plan privately; credentials are not required in the review.",
                [prefix + ".account_pricing_verified"],
            )
        if not schedule.reviewed:
            add(
                venue + "_FEE_SCHEDULE_NOT_REVIEWED",
                venue + " fee review is pending",
                "The schedule remains an unreviewed draft.",
                "Resolve missing components and unverified evidence before reviewing the complete schedule.",
                [prefix + ".reviewed"],
            )
    return requirements


def configuration_status(
    day: date, path: Path = DEFAULT_CONFIG, *, qualification_valid: bool = False
) -> dict:
    try:
        config = PaperExecutionConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return {
            "configuration_valid": False,
            "configuration_ready": False,
            "engine_ready": False,
            "final_connected_qa_complete": False,
            "requirements": [
                {
                    "code": "PAPER_EXECUTION_CONFIG_UNAVAILABLE_OR_INVALID",
                    "title": "Execution configuration cannot be read",
                    "detail": "The execution document is unavailable or schema-invalid.",
                    "action": "Restore a valid execution configuration before reviewing individual evidence requirements.",
                    "fields": ["execution", "fee_schedules"],
                    "sources": [],
                }
            ],
            "blockers": [
                "PAPER_EXECUTION_CONFIG_UNAVAILABLE_OR_INVALID",
                "FINAL_CONNECTED_QA_PENDING",
            ],
        }
    problems = config.blockers(day)
    return {
        "version": config.version,
        "execution_version": config.execution.version,
        "configuration_valid": True,
        "configuration_ready": not problems,
        "requirements": evidence_requirements(config, day),
        "engine_ready": not problems and qualification_valid,
        "durable_ledger_code_available": True,
        "fee_engine_code_available": True,
        "depth_matcher_code_available": True,
        "depth_risk_sizing_code_available": True,
        "durable_worker_routing_code_available": True,
        "independent_protection_code_available": True,
        "final_connected_qa_complete": qualification_valid,
        "effective_date": day.isoformat(),
        "fee_schedule_versions": [s.version for s in config.fee_schedules if s.applies(day)],
        "blockers": [*problems, *([] if qualification_valid else ["FINAL_CONNECTED_QA_PENDING"])],
    }
