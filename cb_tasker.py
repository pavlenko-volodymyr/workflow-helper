# coding: utf-8

from __future__ import with_statement

import re
import sys

from fabric.api import task, local, quiet, prompt
from fabric.colors import red, cyan

from utils import add_class_methods_as_module_level_functions_for_fabric


class PullRequestMixin(object):
    def send_pull_request(self):
        pass

    def update_pull_request(self):
        pass

    def delete_pull_request(self):
        pass


class GitMixin(object):
    @property
    def branch_name(self):
        with quiet():
            return local(self.git("rev-parse --abbrev-ref HEAD"), capture=True)

    @task(alias="ci")
    def commit(self):
        with quiet():
            local("git commit")

    def reset(self, remote=None, branch=None, hard=False, files=None):
        with quiet():
            args = ["%s/%s" % (remote, branch)]
            if hard:
                args.append("--hard")
            if files:
                args.append(" ".join(files))
            local(self.git("reset", args))

    @task(alias="rr")
    def reset_remote(self, remote="upstream", branch="master"):
        self.reset(remote=remote, branch=branch, hard=True)

    @task(alias="p")
    def push(self, force=False):
        with quiet():
            args = ["origin", self.branch_name]
            if force:
                args.append("-f")
            local(self.git("push", args))

    @task(alias="upr")
    def update_pull_request(self):
        self.push(force=True)

    def process_untracked_files(self):
        with quiet():
            untracked_files = local(self.git("ls-files --other --exclude-standard"), capture=True)
            if untracked_files:
                answer = prompt(cyan("You have untracked files. Add them?(y/n):"), default="n")
                if answer == "y":
                    self.git("add", untracked_files.splitlines())

    def process_staged_files(self):
        with quiet():
            staged_files = local(self.git("diff --name-only --cached"), capture=True)
            answer = prompt(red("You have staged files. (unstage/add)"), default="unstage")

            if answer == "unstage":
                self.reset(branch="HEAD", files=staged_files.splitlines())
            if answer == "add":
                self.git("add", staged_files.splitlines())

    def git(self, command, command_arguments=None):
        git_cmd = "git %s" % command
        if command_arguments:
            git_cmd += " " + " ".join(command_arguments)
        return git_cmd


class Task(PullRequestMixin, GitMixin):
    TASK_PREFIX_TEMPLATE = "Task-{id}"

    def __init__(self):
        self.id = self.get_task_id()

        if not self.id:
            sys.exit("Can't find task ID")

    def get_task_id(self):
        branch_name = self.branch_name
        branch_id_pattern = re.compile(r"(\d+)")

        result = branch_id_pattern.findall(branch_name)

        if result:
            return result[0]


add_class_methods_as_module_level_functions_for_fabric(Task(), __name__)