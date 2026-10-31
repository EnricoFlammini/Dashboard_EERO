import os
import platform
import socket
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _detect_environment() -> str:
    """Classifies the host as 'kubernetes', 'docker' or 'local'."""
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        return "kubernetes"
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return "docker"
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore")
        if any(marker in cgroup for marker in ("docker", "containerd", "kubepods", "libpod")):
            return "docker"
    except OSError:
        pass
    return "local"


def _read_git_checkout(root: Path) -> Tuple[Optional[str], Optional[str]]:
    """Reads (branch, commit) straight from .git without shelling out to git."""
    git_dir = root / ".git"
    if git_dir.is_file():
        # Worktree or submodule: .git is a pointer file ("gitdir: <path>").
        pointer = git_dir.read_text(encoding="utf-8").strip()
        if not pointer.startswith("gitdir:"):
            return None, None
        git_dir = (root / pointer.split(":", 1)[1].strip()).resolve()
    head_file = git_dir / "HEAD"
    if not head_file.is_file():
        return None, None

    head = head_file.read_text(encoding="utf-8").strip()
    if not head.startswith("ref:"):
        return None, head[:12] or None

    ref = head.split(":", 1)[1].strip()
    branch = ref.removeprefix("refs/heads/")
    # Linked worktrees keep refs in the shared common dir.
    common_dir = git_dir
    commondir_file = git_dir / "commondir"
    if commondir_file.is_file():
        common_dir = (git_dir / commondir_file.read_text(encoding="utf-8").strip()).resolve()

    commit = None
    ref_file = common_dir / ref
    if ref_file.is_file():
        commit = ref_file.read_text(encoding="utf-8").strip()
    else:
        packed = common_dir / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2 and parts[1] == ref:
                    commit = parts[0]
                    break
    return branch, (commit[:12] if commit else None)


def get_runtime_info() -> Dict[str, Any]:
    """Describes where this instance runs and which source branch it was built from."""
    branch = os.getenv("GIT_BRANCH", "").strip() or None
    commit = os.getenv("GIT_COMMIT", "").strip()[:12] or None
    source = "build" if (branch or commit) else None

    if not source:
        try:
            branch, commit = _read_git_checkout(PROJECT_ROOT)
        except OSError:
            branch, commit = None, None
        if branch or commit:
            source = "checkout"

    return {
        "environment": _detect_environment(),
        "hostname": socket.gethostname(),
        "git_branch": branch,
        "git_commit": commit,
        "git_source": source,
        "app_version": settings.app_version,
        "build_number": settings.build_number,
        "python_version": platform.python_version(),
        "os": f"{platform.system()} {platform.machine()}".strip(),
    }
