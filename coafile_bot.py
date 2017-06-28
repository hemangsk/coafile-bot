import os
import shutil
import tempfile
import time

from coalib.misc.Shell import run_shell_command
from github3 import GitHub
from github3.models import GitHubError


# configuration

GITHUB_POLL_DELAY = 5
TEMP_DIR = os.getcwd() + '/tmp'
MAX_RETRIES_LIMIT = 3


# Initialize GitHub object

gh = GitHub(token=os.environ['GITHUB_API_TOKEN'])


def parse_issue_num(url):
    """
    Parses issue number from url

    :param url: Url from which issue number is to be parsed
    :return: Issue number
    """
    num_list = url.split('/')
    return num_list[len(num_list) - 1]


def handle_thread(thread):
    """
    Handler for notification thread

    :param thread: Thread object of where coafile mention is made
    :return: coafile string
    """
    post_comment(
        thread, 'Greetings! I\'m the coafile bot and I\'m here to get your coafile ready. Sit Tight!')

    clone_url = 'https://github.com/' + thread.repository.full_name + '.git'
    cmd = ['git', 'clone', '--depth=100', clone_url]

    directory = tempfile.mkdtemp(dir=TEMP_DIR)
    run_shell_command(cmd, cwd=directory)

    quickstart_cmd = ["coala-quickstart", "--ci"]
    run_shell_command(quickstart_cmd, cwd=directory)

    with open(directory + os.sep + '.coafile', 'r') as pointer:
        coafile = pointer.read()
        pointer.close()

    shutil.rmtree(directory)

    return coafile


def post_comment(thread, message):
    """
    Post comment on GitHub thread

    :param thread: Thread on which comment is to be post
    :param message: Message to comment.
    """

    num = parse_issue_num(thread.subject['url'])
    issue = gh.issue(thread.repository.owner.login,
                     thread.repository.name, num)
    issue.create_comment(message)


def create_pr(thread, coafile, retries=0):
    """
    Creates GitHub PR with coafile

    :param thread: Thread object where mention to coafile is done
    :param coafile: coafile string
    :param retries: Attempts done to create the PR
    :return: If successful return PullRequest object
    """

    repo = gh.repository(thread.repository.owner.login, thread.repository.name)
    clone = repo.create_fork()
    coafile_byte = coafile.encode()

    try:
        clone.create_file(
            path='.coafile', message='coafile: Add coafile', content=coafile_byte)
        pr = repo.create_pull(title='Add coafile',
                              base='master', head='coafile:master')
        return pr

    except GitHubError:
        if retries < MAX_RETRIES_LIMIT:
            post_comment(
                thread, "Oops! Looks like there was some problem making the coafile PR! Retrying...")
            clone.delete()
            retries += 1
            create_pr(thread, coafile, retries)
        else:
            post_comment(
                thread, "Sorry! coafile-bot is unable to make the PR.")


if __name__ == "__main__":
    """
    Runs coala-quickstart on a repository and makes a PR
    with the generated coafile.
    """
    while True:
        threads = gh.iter_notifications(all=True)
        for thread in threads:
            if thread.reason == "mention" and thread.is_unread():
                thread.mark()
                thread.delete_subscription()
                coafile = handle_thread(thread)
                coafile_pre = '```' + coafile + '```'
                post_comment(thread, coafile_pre)
                pr = create_pr(thread, coafile)
                if not pr:
                    post_comment(
                        thread, "Oops! Looks like I've already made a coafile PR!")
                else:
                    completion_message = 'coafile creation process Successful! :tada: :tada: :tada:' \
                        + '\n\n\n Next Steps: ' \
                        + '\n\n Step 1: Merge the Pull Request ' + str(pr.html_url) + ' having the .coafile.' \
                        + '\n Step 2: Turn on GitMate Integration on this repository.' \
                        + '\n Step 3: Turn on code analysis for automated code reviews on your PRs' \
                        + '\n\n Happy Linting! :tada:'
                    post_comment(thread, completion_message)

        time.sleep(GITHUB_POLL_DELAY)
