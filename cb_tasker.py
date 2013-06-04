# coding: utf-8

from __future__ import with_statement

from os import environ
from sys import exit
from functools import partial
import json

from fabric.api import task, local, quiet, prompt
from fabric.colors import red, cyan

from requests import post

from utils import add_class_methods_as_module_level_functions_for_fabric

GITHUB_USER = environ.get('GITHUB_USER')
GITHUB_PASSWORD = environ.get('GITHUB_PASSWORD')

if not GITHUB_USER or not GITHUB_PASSWORD:
    exit("Enviroment variables GITHUB_USER and GITHUB_PASSWORD should be present.")


class PullRequestMixin(object):
    GITHUB = {
        'user': GITHUB_USER,
        'password': GITHUB_PASSWORD,
        'urls': {
            'base': 'https://api.github.com',
            'pull_request': '/repos/django-stars/mmp/pulls'
        }
    }

    def post(self, *args, **kwargs):
        kwargs.update({'auth': (GITHUB_USER, GITHUB_PASSWORD)})
        return post(*args, **kwargs)

    def send(self):
        message = prompt("Pull request message, either joined commit's messages will be used",
                         default=False) or self.commits_messages
        pull_request_title = ", ".join(
            [self.branch_name.capitalize(), message]
        )
        data = {
            "title": pull_request_title,
            "body": "",
            "head": "{user}:{branch}".format(
                user=GITHUB_USER, branch=self.branch_name
            ),
            "base": "master"
        }
        url = "".join([self.GITHUB['urls']['base'], self.GITHUB['urls']['pull_request']])
        response = self.post(url=url, data=json.dumps(data))

        json_response = json.loads(response.content)
        pull_request_url = json_response.get('html_url')

    @task(alias="upr")
    def update(self):
        self.push(force=True)

    def finish(self):
        self.send()


class GitMixin(object):
    @property
    def branch_name(self):
        with quiet():
            return self.git("rev-parse --abbrev-ref HEAD")

    @task(alias="ci")
    def commit(self):
        with quiet():
            commit_message_body = prompt(cyan("Commit message"), default="Temp")
            commit_message = ", ".join([self.branch_name.capitalize(), commit_message_body])
            self.git("commit -m '%s'" % commit_message)

    def reset(self, remote=None, branch=None, hard=False, files=None):
        with quiet():
            args = ["%s/%s" % (remote, branch)]
            if hard:
                args.append("--hard")
            if files:
                args.append(" ".join(files))
            self.git("reset", args)

    @task(alias="rr")
    def reset_remote(self, remote="upstream", branch="master"):
        self.reset(remote=remote, branch=branch, hard=True)

    @task(alias="p")
    def push(self, force=False):
        with quiet():
            args = ["origin", self.branch_name]
            if force:
                args.append("-f")
            self.git("push", args)

    def process_untracked_files(self):
        with quiet():
            untracked_files = local(self.git("ls-files --other --exclude-standard"), capture=True)
            if untracked_files:
                answer = prompt(cyan("You have untracked files. Add them?(y/n):"), default="n")
                if answer == "y":
                    self.git("add", untracked_files.splitlines())
                    self.commit()

    def process_staged_files(self):
        with quiet():
            staged_files = local(self.git("diff --name-only --cached"), capture=True)
            answer = prompt(red("You have staged files. (unstage/add)"), default="unstage")

            if answer == "unstage":
                self.reset(branch="HEAD", files=staged_files.splitlines())
            if answer == "add":
                self.git("add", staged_files.splitlines())
                self.commit()

    def git(self, command, command_arguments=None):
        git_cmd = "git %s" % command
        if command_arguments:
            git_cmd += " " + " ".join(command_arguments)
        return local(git_cmd, capture=True)

    def finish(self):
        self.process_staged_files()
        self.process_untracked_files()

    @property
    def commits_messages(self):
        start = "upstream/master"
        end = self.branch_name
        command, args = 'log', ['--pretty=format:"%s"', '{start}..{end}'.format(start=start, end=end)]
        result = self.git(command, args)

        filter_task_name = lambda i: i.split(", ")[-1]

        result = ". ".join(map(filter_task_name, result.split("\n")))
        return result


class Task(PullRequestMixin, GitMixin):
    @task(alias="s")
    def switch(self, task_id):
        """Switch to task"""
        self.task_id = task_id

    @task(alias="f")
    def finish(self):
        super(Task, self).finish()

add_class_methods_as_module_level_functions_for_fabric(Task(), __name__)