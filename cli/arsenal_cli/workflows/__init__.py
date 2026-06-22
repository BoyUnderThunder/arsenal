"""Arsenal workflow engine — high-level orchestration of multiple tools.

Each workflow subclasses :class:`~arsenal_cli.workflows.base.Workflow` and
declares a :meth:`plan` of :class:`Task` objects. The base class runs them,
records structured results into an engagement :class:`~arsenal_cli.project.Project`,
and renders a report. Adding a workflow is one small module.
"""
