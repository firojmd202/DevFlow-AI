"""Streamlit views for specification requests, progress, review, and approval."""

import asyncio
from typing import cast

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from devflow_core.config import get_settings
from devflow_ui.api_client import APIClient

type Row = dict[str, object]


def specification_pages() -> list[StreamlitPage]:
    return [
        st.Page(
            "app_pages/7_Spec_Request.py", title="Feature request", icon=":material/edit_note:"
        ),
        st.Page("app_pages/8_Generation_Status.py", title="Generation", icon=":material/article:"),
        st.Page(
            "app_pages/9_Review_Findings.py", title="Review findings", icon=":material/rate_review:"
        ),
        st.Page(
            "app_pages/10_Approval.py", title="Specification approval", icon=":material/task_alt:"
        ),
    ]


def client() -> APIClient:
    return APIClient(get_settings().DEVFLOW_API_BASE_URL)


def call(
    api: APIClient,
    path: str = "",
    *,
    method: str = "GET",
    payload: Row | None = None,
    params: dict[str, str | int] | None = None,
) -> object:
    with st.spinner("Contacting DevFlow API…"):
        return asyncio.run(api.specifications(path, method=method, payload=payload, params=params))


def rows(value: object) -> list[Row]:
    if not isinstance(value, list):
        return []
    return [cast(Row, item) for item in value if isinstance(item, dict)]


def row(value: object) -> Row | None:
    return cast(Row, value) if isinstance(value, dict) else None


def show_error(api: APIClient) -> None:
    code = api.last_error_code
    if code in {"PROVIDER_NOT_CONFIGURED", "PROVIDER_UNAVAILABLE"}:
        st.error(f"{code}. Check the selected inference provider and model.")
    elif code == "APPROVAL_EXPIRED":
        st.error("The approval expired. Request a fresh approval for the displayed digest.")
    elif code in {"APPROVAL_BINDING_MISMATCH", "SPEC_DIGEST_MISMATCH"}:
        st.error("The version or digest changed. Refresh before requesting a fresh approval.")
    elif code:
        st.error(f"The specification action was rejected ({code}).")
    else:
        st.error("API unavailable. Start the backend and try again.")


def selected_request(api: APIClient) -> Row | None:
    data = call(api)
    if data is None:
        show_error(api)
        return None
    choices = {str(item["id"]): item for item in rows(data) if "id" in item}
    if not choices:
        st.info("Create a feature request first.")
        return None
    keys = list(choices)
    prior = str(st.session_state.get("spec_request_id", ""))
    selection = st.selectbox(
        "Feature request",
        keys,
        index=keys.index(prior) if prior in keys else 0,
        format_func=lambda key: f"{choices[key].get('title', 'Feature')} · #{key}",
    )
    if selection is None:
        return None
    st.session_state["spec_request_id"] = selection
    return choices[selection]


def render_feature_request() -> None:
    st.header("Feature request")
    api = client()
    available = rows(call(api, "/providers"))
    options = {str(item["provider_id"]): item for item in available if "provider_id" in item}
    options.setdefault("ollama", {})
    provider = st.selectbox(
        "AI provider",
        list(options),
        index=list(options).index("ollama"),
        format_func=lambda value: "Ollama · Local inference"
        if value == "ollama"
        else "OpenAI · Cloud inference",
    )
    if provider is None:
        return
    availability = options[provider]
    if availability.get("available") is False:
        st.warning(
            f"{provider}: PROVIDER_UNAVAILABLE. Check the inference service before generating."
        )
    with st.form("specification_request"):
        title = st.text_input("Title", max_chars=200)
        description = st.text_area("Feature requirements", max_chars=4000)
        model = st.text_input("Model", value=str(availability.get("model_id", "")), max_chars=256)
        context = st.text_area("Repository context")
        submit = st.form_submit_button("Create feature request")
    if submit:
        if not title.strip() or not description.strip():
            st.error("Enter a title and feature requirements.")
            return
        data = row(
            call(
                api,
                method="POST",
                payload={
                    "title": title,
                    "description": description,
                    "repo_context": context or None,
                    "provider_id": provider,
                    "model_id": model or None,
                },
            )
        )
        if data is None:
            show_error(api)
        else:
            st.session_state["spec_request_id"] = str(data["id"])
            st.success("Draft saved. Open Generation to generate the specification.")


def render_generation() -> None:
    st.header("Generation")
    api = client()
    request = selected_request(api)
    if request is None:
        return
    path = f"/{request['id']}"
    st.button("Refresh status")
    progress = row(call(api, path + "/status"))
    if progress is None:
        show_error(api)
        return
    lifecycle = str(request.get("status"))
    status = str(progress.get("status"))
    st.write(f"Specification status · {lifecycle.replace('_', ' ')}")
    if status in {"pending", "running"}:
        st.info(f"Generation is {status}. Refresh to check progress.")
        if st.button("Cancel generation"):
            if call(api, path + "/generate", method="DELETE") is None:
                show_error(api)
            else:
                st.success("Cancellation requested.")
    elif status == "failed":
        code = progress.get("error_code")
        st.error(f"Generation failed · {request.get('provider_id', 'ollama')} · {code}")
    elif status == "cancelled":
        st.info("Generation cancelled.")
    elif status == "succeeded":
        st.success("Generation complete.")
    if st.button("Generate specification", disabled=lifecycle != "draft"):
        if (
            call(
                api,
                path + "/generate",
                method="POST",
                payload={"expected_version": request["version"]},
            )
            is None
        ):
            show_error(api)
        else:
            st.rerun()
    history = rows(call(api, path + "/versions"))
    versions = {str(item["version_number"]): item for item in history if item.get("content_digest")}
    if not versions:
        return
    version = st.selectbox("Artifact version", list(versions), index=len(versions) - 1)
    comparison = st.selectbox("Compare with", ["None", *versions])
    kind = st.selectbox("Artifact", ["requirements", "design", "tasks"])
    if version is None or kind is None:
        return
    left = row(call(api, f"{path}/versions/{versions[version]['id']}/artifacts/{kind}"))
    if comparison in versions and comparison != version:
        right = row(call(api, f"{path}/versions/{versions[comparison]['id']}/artifacts/{kind}"))
        columns = st.columns(2)
        for column, label, result in zip(
            columns, (version, comparison), (left, right), strict=True
        ):
            with column:
                st.caption(f"Version {label}")
                if result is not None:
                    st.code(str(result.get("content", "")), language="markdown")
    elif left is not None:
        st.code(str(left.get("content", "")), language="markdown")
    else:
        show_error(api)


def render_review() -> None:
    st.header("Review findings")
    api = client()
    request = selected_request(api)
    if request is None:
        return
    path = f"/{request['id']}"
    state = str(request.get("status"))
    st.button("Refresh review")
    progress = row(call(api, path + "/status", params={"kind": "review"}))
    if progress is None:
        show_error(api)
        return
    if progress.get("status") in {"pending", "running"}:
        st.info("Review in progress.")
        if st.button("Cancel review"):
            if call(api, path + "/review", method="DELETE") is None:
                show_error(api)
            else:
                st.success("Cancellation requested.")
    elif progress.get("status") == "failed":
        st.error(f"Review failed · {progress.get('error_code')}")
    elif progress.get("status") == "cancelled":
        st.info("Review cancelled.")
    if st.button("Request AI review", disabled=state != "generated"):
        if (
            call(
                api,
                path + "/review",
                method="POST",
                payload={"expected_version": request["version"]},
            )
            is None
        ):
            show_error(api)
        else:
            st.rerun()
    versions = {str(item["version_number"]): item for item in rows(call(api, path + "/versions"))}
    selection = (
        st.selectbox("Review version", list(versions), index=len(versions) - 1)
        if versions
        else None
    )
    if selection is None:
        return
    data = row(
        call(
            api,
            path + "/review/findings",
            params={"version_id": int(str(versions[selection]["id"]))},
        )
    )
    if data is None:
        show_error(api)
        return
    st.info(str(data["disclaimer"]))
    if state == "revision_required":
        st.warning("Revision required. Critical findings cannot be bypassed by acknowledgment.")
    if st.button("Request revision", disabled=state not in {"under_review", "ready_for_approval"}):
        if call(api, path + "/revision", method="POST") is None:
            show_error(api)
        else:
            st.rerun()
    if state == "revision_required":
        with st.form("specification_revision"):
            title = st.text_input("Revision title", value=str(request.get("title", "")))
            description = st.text_area(
                "Revision requirements", value=str(request.get("description", ""))
            )
            if st.form_submit_button("Save revised draft"):
                editable: Row = {
                    key: request[key]
                    for key in (
                        "business_goal",
                        "functional_requirements",
                        "nonfunctional_constraints",
                        "acceptance_criteria",
                        "repo_context",
                        "clarifying_questions",
                        "workflow_run_id",
                        "workflow_step_id",
                    )
                    if key in request
                }
                if (
                    call(
                        api,
                        path,
                        method="PATCH",
                        payload={
                            **editable,
                            "title": title,
                            "description": description,
                            "expected_version": request["version"],
                        },
                    )
                    is None
                ):
                    show_error(api)
                else:
                    st.rerun()
    findings = rows(data.get("findings"))
    if not findings:
        st.info("No findings for this version.")
    for finding in findings:
        st.subheader(f"{finding['severity']} · {finding['location']}")
        st.text(str(finding["finding_text"]))
        st.text(str(finding["recommendation"]))
        if finding["severity"] in {"Critical", "High"} and not finding["acknowledged"]:
            enabled = selection == str(request["version"]) and state in {
                "ready_for_approval",
                "revision_required",
            }
            if st.button("Acknowledge", key=f"finding-{finding['id']}", disabled=not enabled):
                if call(api, f"{path}/findings/{finding['id']}/acknowledge", method="POST") is None:
                    show_error(api)
                else:
                    st.rerun()


def render_approval() -> None:
    st.header("Specification approval")
    api = client()
    request = selected_request(api)
    if request is None:
        return
    path = f"/{request['id']}"
    versions = rows(call(api, path + "/versions"))
    state = str(request.get("status"))
    st.write(f"Specification status · {state.replace('_', ' ')}")
    if state == "approved":
        st.success("Approved specification.")
    version = next(
        (item for item in versions if item["version_number"] == request["version"]), None
    )
    if version is not None and version.get("content_digest"):
        digest = str(version["content_digest"])
        st.caption(f"Version {version['version_number']} · Digest {digest[:12]}")
        binding = {"version_id": version["id"], "content_digest": digest}
        key = f"approval-{request['id']}-{version['id']}-{digest}"
        review_ready = False
        if state == "ready_for_approval":
            progress = row(call(api, path + "/status", params={"kind": "review"}))
            findings = row(call(api, path + "/review/findings"))
            review_ready = (
                progress is not None
                and progress.get("status") == "succeeded"
                and findings is not None
                and not any(
                    item.get("severity") == "Critical"
                    or (item.get("severity") == "High" and not item.get("acknowledged"))
                    for item in rows(findings.get("findings"))
                )
            )
            if not review_ready:
                st.warning("Complete the review and resolve blocking findings before approval.")
        if st.button("Request approval", disabled=not review_ready):
            approval = row(call(api, path + "/approval", method="POST", payload=binding))
            if approval is None:
                show_error(api)
            else:
                st.session_state[key] = approval
        approval = row(st.session_state.get(key))
        if approval:
            st.caption(
                f"Approval status · {approval['status']} · Expires {approval.get('expires_at')}"
            )
        confirmed = st.checkbox("I reviewed this version and its digest")
        reason = st.text_input("Rejection reason", max_chars=1000)
        enabled = approval is not None and review_ready and confirmed
        approve, reject = st.columns(2)
        approved = approve.button("Approve", disabled=not enabled)
        rejected = reject.button("Reject", disabled=not enabled or not reason.strip())
        if approval is not None and (approved or rejected):
            result = row(
                call(
                    api,
                    path + "/approve",
                    method="POST",
                    payload={
                        **binding,
                        "approval_id": approval["id"],
                        "decision": "approved" if approved else "rejected",
                        "reason": reason or None,
                    },
                )
            )
            if result is None:
                show_error(api)
            else:
                st.session_state[key] = result
                st.rerun()
    st.subheader("Audit history")
    history = rows(call(api, path + "/audit"))
    if not history:
        st.info("No audit events yet.")
    for event in history:
        st.text(f"{event.get('created_at', '')} · {event.get('event_type', '')}")
