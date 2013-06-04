# -*- coding: utf-8 -*-

from __future__ import with_statement

import os
import sys
import json
import re
from functools import partial
from pprint import pprint

from requests import get, post, session
from requests.auth import HTTPBasicAuth

from fabric.api import cd, local

try:
    from Skype4Py import Skype
    SKYPE_ENABLED = True
except ImportError:
    SKYPE_ENABLED = False


RUN_DIR = os.getcwd()
sys.path.insert(0, RUN_DIR)

try:
    import settings
    SETTINGS_ENABLED = True
except ImportError:
    SETTINGS_ENABLED = False

from local_settings import GITHUB_PASS, GITHUB_USER, NOTIFICATION_RECEIVERS

GITHUB = {
    'user': GITHUB_USER,
    'password': GITHUB_PASS,
    'urls': {
        'base': 'https://api.github.com',
        'pull_request': '/repos/django-stars/mmp/pulls'
    }
}
PULL_REQUEST_NOTIFICATION_RECEIVERS = NOTIFICATION_RECEIVERS
PULL_REQUEST_NOTIFICATION_MESSAGE = u"Yo, bro, check this out %s, plz"


get = partial(get, auth=(GITHUB['user'], GITHUB['password']))
post = partial(post, auth=(GITHUB['user'], GITHUB['password']))


def skype_notify(pull_request_url=None):
    client = Skype()
    client.Attach()

    msg = PULL_REQUEST_NOTIFICATION_MESSAGE % (pull_request_url or '')

    for receiver in PULL_REQUEST_NOTIFICATION_RECEIVERS:
        client.SendMessage(
            receiver,
            msg
        )


def git_checkout(where):
    local("git checkout %s" % where)


def git_reset(branch="upstream/master"):
    local("git reset --hard %s" % branch)


def git_fetch(remote="upstream"):
    local("git fetch %s" % remote)


def git_new_branch(name):
    local("git branch %s" % name)


def git_rebase(branch="upstream/master"):
    local("git rebase -i %s" % branch)


def git_get_branch_name():
    result = local("git branch", capture=True)
    branch_name = None
    for bn in result.split("\n"):
        if bn.startswith("*"):
            branch_name = bn.split()[-1]
            break

    assert branch_name, "No branch name captured"

    return branch_name


def git_push(where, force=False):
    command = ["git push origin %s" % where]
    if force:
        command.append("-f")
    local(" ".join(command))


def git_collect_commits_messages(start="upstream/master", end=None):
    if not end:
        end = git_get_branch_name()
    command = 'git log --pretty=format:"%s" {start}..{end}'.format(
        start=start,
        end=end
    )
    result = local(
        command,
        capture=True
    )

    filter_task_name = lambda i: i.split(", ")[-1]

    result = ". ".join(map(filter_task_name, result.split("\n")))
    return result


def git_pull_request():
    branch_name = git_get_branch_name()
    pull_request_title = git_collect_commits_messages()
    pull_request_title = ", ".join(
        [branch_name.capitalize(), pull_request_title]
    )
    data = {
        "title": pull_request_title,
        "body": "",
        "head": "{user}:{branch}".format(
            user=GITHUB['user'], branch=branch_name
        ),
        "base": "master"
    }
    url = "".join([GITHUB['urls']['base'], GITHUB['urls']['pull_request']])
    response = post(url=url, data=json.dumps(data))
    if response.status_code != 201:
        pprint(GITHUB)
        pprint(response)

    json_response = json.loads(response.content)
    pull_request_url = json_response.get('html_url')

    if SKYPE_ENABLED:
        skype_notify(pull_request_url)


def migrate(app_name=None):
    command = ["python manage.py migrate"]
    if app_name:
        command.append(app_name)
    local(" ".join(command))


def test():
    command = ["python manage.py test --settings=settings_test"]
    if SETTINGS_ENABLED:
        apps = " ".join(settings.PROJECT_APPS)
        command.append(apps)
    local(" ".join(command))


def new_task(task_number, south=False):
    assert task_number, "No task number given"

    branch_name = "task-%s" % task_number

    with cd(RUN_DIR):
        git_checkout("master")
        git_fetch()
        git_reset()
        git_new_branch(branch_name)
        git_checkout(branch_name)

        if south:
            migrate()


def update_task(south):
    """Should be runned after checkout"""

    git_fetch()
    git_rebase()
    # test()
    if south:
        migrate()


def reopen_task(task_number):
    assert task_number, "No task number given"

    branch_name = "task-%s" % task_number

    with cd(RUN_DIR):
        git_checkout(branch_name)
        update_task()


def switch_to_task(task_number, update=True, south=False):
    assert task_number, "No task number given"

    branch_name = "task-%s" % task_number
    with cd(RUN_DIR):
        git_checkout(branch_name)
        update_task(south)


def finish_task(south=False, force=False):
    with cd(RUN_DIR):
        # test()
        git_fetch()
        git_rebase()

        branch_name = git_get_branch_name()

        if south:
            # don't be stupid, check migration before send
            migrate()

        git_push(branch_name, force)
        git_pull_request()


#Aliases
ft = finish_task
nt = new_task
st = switch_to_task


class Tracker(object):
    URL = 'https://tracker.mymoneypark.com/login'
    ISSUE = 'https://tracker.mymoneypark.com/issues/{issue_id}'
    session = None

    def _get_auth_token(self):
        p = re.compile(r'authenticity_token" type="hidden" value="(.*)"')
        r = get(url=self.URL, verify=False, auth=HTTPBasicAuth('mmp', '2013_mmp'))
        # Max in my head
        assert r.status_code == 200
        assert p.search(r.content)
        return p.search(r.content).groups()[0]

    def login(self):
        token = self._get_auth_token()
        self.session = session()
        data = {
            'utf8': '%E2%9C%93',
            'authenticity_token': token,
            'back_url': 'https://tracker.mymoneypark.com/projects/mmp/issues',
            'username': 'volodymyr.pavlenko',
            'password': 'P_ssw0rd',
            'login': 'Login+%C2%BB'
        }
        r = self.session.post(url=self.URL, data=data, verify=False, auth=HTTPBasicAuth('mmp', '2013_mmp'))

    def issue_detail(self, issue_id):
        r = self.session.get(
            url=self.ISSUE.format(issue_id=issue_id),
            verify=False, auth=HTTPBasicAuth('mmp', '2013_mmp'))
        return r.content

if __name__ == "__main__":
    t = Tracker()
    t.login()
    print t.issue_detail()
