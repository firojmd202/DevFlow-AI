"""Pure structural review and validation of specification Markdown."""

import re

from devflow_api.schemas.specification import (
    ARTIFACT_TYPES,
    ArtifactType,
    Dimension,
    ReviewFinding,
    Severity,
)
from devflow_api.specification_errors import MalformedSpecificationError

_METADATA = ("Version", "Status", "Scope", "Branch", "Last Updated")
_DESIGN: dict[str, tuple[Severity, Dimension]] = {
    "Architecture Overview": ("High", "architecture_compatibility"),
    "Component Specifications": ("High", "completeness"),
    "Data Models": ("High", "completeness"),
    "API Contracts": ("High", "completeness"),
    "Failure Modes": ("High", "edge_cases"),
    "Security Architecture": ("Critical", "security_privacy"),
    "Concurrency Model": ("Critical", "architecture_compatibility"),
    "Integration Boundaries": ("High", "scope_creep"),
}
_REQUIREMENT_ID = re.compile(r"\bREQ-[A-Z0-9]+(?:[.\-][A-Z0-9]+)*\b")
_TASK_ID = re.compile(r"\b[A-Z][A-Z0-9]*\.T\d+\b")
_HEADER = re.compile(r"(?m)^(#{1,6})[ \t]+(.+)$")
_ACCEPTANCE = re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*)?Acceptance Criteria(?:\*\*)?:?(?:\*\*)?[ \t]*"
    r"(?:\r?\n[ \t]*[-*\d][^\r\n]*|[^\s*:\r\n][^\r\n]*)"
)
_TASK_FIELDS = {
    "Description": r"(?im)^\s*(?:\*\*)?Description\s*(?::|\*\*)",
    "Dependencies": r"(?im)^\s*(?:\*\*)?(?:Dependencies|Depends on)\s*(?::|\*\*)",
    "Size Estimate": r"(?im)^\s*(?:\*\*)?Size(?: Estimate)?\s*:?(?:\*\*)?\s*[SML]\b",
}
_TRACE_HEADERS = ("requirement id", "source input field", "business goal")


def _finding(
    severity: Severity, dimension: Dimension, location: str, evidence: str, recommendation: str
) -> ReviewFinding:
    return ReviewFinding(
        severity=severity,
        dimension=dimension,
        location=location,
        finding_text=evidence,
        recommendation=recommendation,
        source="deterministic",
    )


def _sections(text: str, identifier: re.Pattern[str]) -> list[tuple[str, str]]:
    headings = list(_HEADER.finditer(text))
    sections = []
    for index, heading in enumerate(headings):
        match = identifier.match(heading[2].strip(" `"))
        if match is not None:
            next_start = len(text)
            for next_index in range(index + 1, len(headings)):
                following = headings[next_index]
                if len(following[1]) <= len(heading[1]):
                    next_start = following.start()
                    break
            sections.append((match[0], text[heading.end() : next_start]))
    return sections


def _trace_table(text: str) -> bool:
    return any(
        all(field in line.lower() for field in _TRACE_HEADERS)
        for line in text.splitlines()
        if line.lstrip().startswith("|")
    )


def _metadata_findings(kind: ArtifactType, content: str) -> list[ReviewFinding]:
    if not content.strip():
        return [
            _finding(
                "Critical",
                "completeness",
                f"{kind}.md",
                "Artifact is absent or empty.",
                "Provide the complete artifact.",
            )
        ]
    missing = [
        field
        for field in _METADATA
        if not re.search(
            rf"(?im)^[ \t]*(?:\*\*)?{re.escape(field)}(?:\*\*)?:" rf"(?:\*\*)?[ \t]*[^\s*][^\r\n]*",
            content,
        )
    ]
    return (
        [
            _finding(
                "Critical",
                "completeness",
                f"{kind}.md metadata",
                f"Missing metadata fields: {', '.join(missing)}.",
                "Add the required metadata with explicit values.",
            )
        ]
        if missing
        else []
    )


def _design_findings(content: str) -> list[ReviewFinding]:
    headings = [heading[2].casefold() for heading in _HEADER.finditer(content)]
    findings = []
    for section, (severity, dimension) in _DESIGN.items():
        if not any(section.casefold() in heading for heading in headings):
            findings.append(
                _finding(
                    severity,
                    dimension,
                    f"design.md / {section}",
                    f"Missing {section} section.",
                    f"Describe {section.lower()} for the proposed change.",
                )
            )
    return findings


def _requirement_findings(
    requirements: list[tuple[str, str]],
    text: str,
) -> list[ReviewFinding]:
    findings = []
    if not requirements:
        findings.append(
            _finding(
                "High",
                "completeness",
                "requirements.md",
                "No numbered requirement headings.",
                "Add individually numbered requirements.",
            )
        )
    if not _trace_table(text):
        findings.append(
            _finding(
                "Informational",
                "scope_creep",
                "requirements.md traceability",
                "The input traceability table is missing.",
                "Link each requirement to its source input and business goal.",
            )
        )
    identifiers: set[str] = set()
    for identifier, body in requirements:
        if identifier in identifiers:
            findings.append(
                _finding(
                    "High",
                    "consistency",
                    f"requirements.md / {identifier}",
                    "Requirement ID is duplicated.",
                    "Assign each requirement a unique ID.",
                )
            )
        identifiers.add(identifier)
        if not _ACCEPTANCE.search(body):
            findings.append(
                _finding(
                    "High",
                    "testability",
                    f"requirements.md / {identifier}",
                    "No acceptance criterion is specified.",
                    "Add an observable acceptance criterion.",
                )
            )
        if not re.search(rf"(?m)^\s*\|\s*{re.escape(identifier)}\s*\|", text):
            findings.append(
                _finding(
                    "Informational",
                    "scope_creep",
                    f"requirements.md / {identifier}",
                    "Requirement has no traceability row.",
                    "Link the requirement to the feature input.",
                )
            )
    return findings


def _task_findings(
    tasks: list[tuple[str, str]],
    requirement_ids: set[str],
) -> list[ReviewFinding]:
    if not tasks:
        return [
            _finding(
                "High",
                "completeness",
                "tasks.md",
                "No numbered task headings.",
                "Add individually numbered implementation tasks.",
            )
        ]
    task_ids = {identifier for identifier, _ in tasks}
    findings = []
    seen: set[str] = set()
    for identifier, body in tasks:
        location = f"tasks.md / {identifier}"
        if identifier in seen:
            findings.append(
                _finding(
                    "High",
                    "consistency",
                    location,
                    "Task ID is duplicated.",
                    "Assign each task a unique ID.",
                )
            )
        seen.add(identifier)
        missing = [field for field, pattern in _TASK_FIELDS.items() if not re.search(pattern, body)]
        if not _ACCEPTANCE.search(body):
            missing.append("Acceptance Criteria")
        if missing:
            findings.append(
                _finding(
                    "High",
                    "completeness",
                    location,
                    f"Missing task fields: {', '.join(missing)}.",
                    "Complete the task definition and its verification criteria.",
                )
            )
        dependencies = re.findall(
            r"(?im)^\s*(?:\*\*)?(?:Dependencies|Depends on)\s*:?(?:\*\*)?[ \t]*([^\r\n]*)",
            body,
        )
        refs = set(_TASK_ID.findall("\n".join(dependencies)))
        if refs - task_ids or identifier in refs:
            findings.append(
                _finding(
                    "High",
                    "dependency_assumptions",
                    location,
                    "Dependency references an undefined task or the task itself.",
                    "Use valid dependencies and remove the self-reference.",
                )
            )
        if not set(_REQUIREMENT_ID.findall(body)) & requirement_ids:
            findings.append(
                _finding(
                    "Medium",
                    "scope_creep",
                    location,
                    "Task has no traceable requirement.",
                    "Link the task to at least one defined requirement.",
                )
            )
    return findings


def deterministic_findings(artifacts: dict[ArtifactType, str]) -> list[ReviewFinding]:
    findings = [
        finding
        for kind in ARTIFACT_TYPES
        for finding in _metadata_findings(kind, artifacts.get(kind, ""))
    ]
    requirements = artifacts.get("requirements", "")
    design = artifacts.get("design", "")
    tasks = artifacts.get("tasks", "")
    sections = _sections(requirements, _REQUIREMENT_ID)
    requirement_ids = {identifier for identifier, _ in sections}
    findings.extend(_requirement_findings(sections, requirements))
    findings.extend(_design_findings(design))
    findings.extend(_task_findings(_sections(tasks, _TASK_ID), requirement_ids))
    for kind, content in (("design", design), ("tasks", tasks)):
        if set(_REQUIREMENT_ID.findall(content)) - requirement_ids:
            findings.append(
                _finding(
                    "High",
                    "consistency",
                    f"{kind}.md cross-references",
                    "The artifact refers to an undefined requirement.",
                    "Match requirement references to IDs in requirements.md.",
                )
            )
    return findings


def validate_generation(artifacts: dict[ArtifactType, str]) -> None:
    if not _trace_table(artifacts["requirements"]):
        raise MalformedSpecificationError("Specification requirement traceability is missing")
    findings = deterministic_findings(artifacts)
    if any(
        finding.severity in {"Critical", "High"}
        and finding.dimension
        in {
            "completeness",
            "testability",
            "architecture_compatibility",
            "security_privacy",
            "edge_cases",
        }
        for finding in findings
    ):
        raise MalformedSpecificationError("Generated specification is structurally incomplete")


def malformed_review_finding() -> ReviewFinding:
    return _finding(
        "High",
        "completeness",
        "AI semantic review",
        "AI_REVIEW_MALFORMED",
        "Repeat semantic review or inspect all review dimensions manually.",
    )
