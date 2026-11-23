"""Typed specification workflow executors with injected handlers."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from devflow_api.schemas.executor import (
    ArtifactRef,
    Capability,
    ExecutionContext,
    ExecutionMetadata,
    ExecutorIdentifier,
    ExecutorModel,
    StepExecutionResult,
    StructuredError,
    TimeoutPolicy,
)
from devflow_api.schemas.workflow_template import ToolSelection
from devflow_api.specification_errors import SpecificationError


class GeneratorInput(ExecutorModel):
    spec_request_id: int = Field(gt=0, strict=True)


class ReviewerInput(ExecutorModel):
    spec_version_id: int = Field(gt=0, strict=True)


class GeneratorOutput(ExecutorModel):
    artifacts: list[ArtifactRef]


class ReviewerOutput(ExecutorModel):
    finding_count_by_severity: dict[str, int]


type Handler = Callable[[ExecutionContext], Awaitable[dict[str, object]]]


class SpecificationExecutor:
    executor_id: ClassVar[str]
    _input_schema: ClassVar[type[ExecutorModel]]
    _output_schema: ClassVar[type[ExecutorModel]]

    def __init__(self, handler: Handler | None = None) -> None:
        self.identifier = ExecutorIdentifier(id=self.executor_id, version=1)
        self.input_schema: type[BaseModel] = self._input_schema
        self.output_schema: type[BaseModel] = self._output_schema
        self.capabilities = [Capability(operation=self.executor_id)]
        self.timeout_policy = TimeoutPolicy(default_s=120, max_s=600)
        self._handler = handler

    def supports(self, tool_selection: ToolSelection) -> bool:
        return (
            tool_selection.executor_id == self.executor_id
            and tool_selection.tool is None
            and not tool_selection.options
        )

    async def execute(self, context: ExecutionContext) -> StepExecutionResult:
        start = datetime.now(UTC)

        def metadata() -> ExecutionMetadata:
            return ExecutionMetadata(
                executor_id=self.executor_id,
                executor_version=self.identifier.version,
                started_at=start,
                finished_at=datetime.now(UTC),
            )

        if context.cancellation.cancelled:
            return StepExecutionResult(
                outcome="cancelled",
                metadata=metadata(),
                error=StructuredError(
                    code="STEP_CANCELLED",
                    category="cancelled",
                    message="Specification execution cancelled",
                ),
            )
        try:
            if self._handler is None:
                raise SpecificationError("Specification executor unavailable")
            self.input_schema.model_validate(context.inputs)
            output = self.output_schema.model_validate(await self._handler(context))
            refs = output.artifacts if isinstance(output, GeneratorOutput) else []
            return StepExecutionResult(
                outcome="succeeded",
                metadata=metadata(),
                output=output.model_dump(mode="json"),
                artifact_refs=refs,
            )
        except SpecificationError as exc:
            code = exc.code
        except Exception:
            code = "SPECIFICATION_EXECUTION_FAILED"
        return StepExecutionResult(
            outcome="failed",
            metadata=metadata(),
            error=StructuredError(
                code=code,
                category="executor",
                message="Specification execution failed",
                attempt=context.attempt,
            ),
        )


class SpecGeneratorExecutor(SpecificationExecutor):
    executor_id = "spec_generator"
    _input_schema = GeneratorInput
    _output_schema = GeneratorOutput


class SpecReviewerExecutor(SpecificationExecutor):
    executor_id = "spec_reviewer"
    _input_schema = ReviewerInput
    _output_schema = ReviewerOutput
