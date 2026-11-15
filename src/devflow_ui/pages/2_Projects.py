"""Persistent project management through the backend API."""

import asyncio

import streamlit as st

from devflow_core.config import get_settings
from devflow_ui.api_client import APIClient


def render_projects() -> None:
    st.header("Projects")
    client = APIClient(get_settings().DEVFLOW_API_BASE_URL)
    projects = asyncio.run(client.list_projects())
    if projects is None:
        st.warning("Backend unavailable — start the FastAPI service to view projects.")
        return

    if projects:
        st.dataframe(projects, hide_index=True)
    else:
        st.info("No projects yet.")

    with st.form("create_project"):
        name = st.text_input("Project name")
        description = st.text_area("Description")
        create = st.form_submit_button("Create project")
    if create:
        if not name.strip():
            st.warning("Enter a project name.")
        elif asyncio.run(client.create_project(name.strip(), description or None)) is None:
            st.error("Could not create the project.")
        else:
            st.rerun()

    for project in projects:
        project_id = int(str(project["id"]))
        project_name = str(project["name"])
        with st.expander(project_name):
            with st.form(f"edit_project_{project_id}"):
                updated_name = st.text_input("Name", project_name)
                updated_description = st.text_area(
                    "Description", str(project.get("description") or "")
                )
                statuses = ("active", "archived", "completed")
                status = st.selectbox(
                    "Status", statuses, index=statuses.index(str(project["status"]))
                )
                save = st.form_submit_button("Save changes")
            if save:
                if not updated_name.strip():
                    st.warning("Enter a project name.")
                elif (
                    asyncio.run(
                        client.update_project(
                            project_id,
                            name=updated_name.strip(),
                            description=updated_description,
                            status=status,
                        )
                    )
                    is None
                ):
                    st.error("Could not update the project.")
                else:
                    st.rerun()
            confirm = st.checkbox("Confirm deletion", key=f"confirm_project_{project_id}")
            if st.button(
                "Delete project", key=f"delete_project_{project_id}", disabled=not confirm
            ):
                if asyncio.run(client.delete_project(project_id)):
                    st.rerun()
                else:
                    st.error("Could not delete the project.")


render_projects()
