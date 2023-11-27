from os import getenv
from git import Repo
from git.exc import GitCommandError
from pydantic import BaseModel, SecretStr, HttpUrl, Field
from fastapi import APIRouter, Query, HTTPException
from pathlib import Path
from logging import getLogger
from http import HTTPStatus

from ..utils.errors import HTTPError

log = getLogger(__name__)

DATA_DIR = getenv("DATA_DIR")
GIT_CREDENTIALS = Path.home() / ".git-credentials"

router = APIRouter(prefix="/git", tags=["git"])


class GitConfig(BaseModel):
    remote: HttpUrl = Field(
        examples=["https://github.com/model-checking/cbmc-starter-kit.git"],
    )
    branch: str = Field(
        examples=["master"],
        min_length=1,
    )
    username: str | None = Field(examples=["firstname.lastname"])
    password: SecretStr | None


@router.get(
    "/config",
    description="Get git config",
    responses={404: {"model": HTTPError}},
)
async def get_git_config() -> GitConfig:
    """Return GitConfig with remote and branch."""
    repo = Repo(DATA_DIR)

    remote = [remote for remote in repo.remotes if remote.name == "origin"]

    if len(remote) == 0:
        log.info("No git remote configured")
        raise HTTPException(HTTPStatus.NOT_FOUND, "No git remote configured")

    username = None
    password = None

    with open(GIT_CREDENTIALS, "r") as file:
        line = file.readline().strip()

        if len(line) > 0:
            url = HttpUrl(line)
            username = url.username
            password = SecretStr(url.password) if url.password is not None else None

    config = GitConfig(
        remote=remote[0].url,
        branch=repo.active_branch.name,
        username=username,
        password=password,
    )

    log.info(f"Git config: {config}")
    return config


@router.put(
    "/config",
    description="Set git config",
    responses={
        409: {"model": HTTPError},
        404: {"model": HTTPError},
    },
)
async def set_git_config(
    config: GitConfig,
    pull: bool = Query(False, description="Pull sources from remote"),
) -> GitConfig:
    """Configure git repo according to given GitConfig."""
    log.info(f"Updating git config: {config}")
    repo = Repo(DATA_DIR)
    new_remote_url = str(config.remote)

    if len(repo.remotes) == 0:
        log.debug(f"Adding remote 'origin'")
        repo.create_remote("origin", new_remote_url)

    log.debug("Updating remote url")
    remote = repo.remote("origin")
    remote.set_url(new_remote_url, remote.url)

    if config.username is not None and config.password is not None:
        log.debug("Updating git credentials")

        with repo.config_writer() as writer:
            writer.set_value("credential", "helper", "store")

        with open(GIT_CREDENTIALS, "w") as file:
            file.write(
                f"{config.remote.scheme}://{config.username}:{config.password.get_secret_value()}@{config.remote.host}"
            )

    try:
        remote.fetch()

    except GitCommandError as e:
        raise HTTPException(HTTPStatus.CONFLICT, f"Failed to fetch remote: {e}")

    try:
        # check if branch exists
        remote_branch = remote.refs[config.branch]

    except IndexError:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Branch '{config.branch}' not found")

    repo.active_branch.set_tracking_branch(remote_branch)

    if pull:
        remote.pull()
        # repo.git.reset("--hard", remote_branch.name)

    return await get_git_config()


@router.post(
    "/pull",
    status_code=HTTPStatus.NO_CONTENT,
    description="Pull sources from configured remote/branch",
    responses={409: {"model": HTTPError}},
)
async def pull_sources() -> None:
    """Pull sources from remote."""
    repo = Repo(DATA_DIR)
    log.info("Pulling remote sources")

    if len(repo.remotes) == 0:
        raise HTTPException(HTTPStatus.CONFLICT, "No git remote configured")

    remote = repo.remote("origin")

    try:
        remote.pull()
        # remote.fetch()
        # repo.git.reset("--hard", remote.refs[repo.active_branch.name].name)

    except GitCommandError as e:
        raise HTTPException(HTTPStatus.CONFLICT, f"Failed to pull remote: {e}")


# TODO: git status, git add, git commit, git push
