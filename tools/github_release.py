"""Maintainer release helper using Git credentials, without printing secrets.

Read status/runs, inspect a release, or publish an already uploaded draft.
GitHub Actions builds and uploads release assets; publication remains explicit.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

REPO = 'caotu-dev/avatar3x-auto-tool'
API = 'https://api.github.com/repos/' + REPO


def token():
    saved = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if saved:
        return saved
    result = subprocess.run(['git', 'credential', 'fill'],
                            input='protocol=https\nhost=github.com\n\n',
                            capture_output=True, text=True, check=True)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if not values.get('password'):
        raise RuntimeError('No GitHub credential available; sign in with Git Credential Manager.')
    return values['password']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'runs', 'release', 'publish'])
    parser.add_argument('--tag', default='v2.0.0')
    parser.add_argument('--sha')
    parser.add_argument('--notes', type=Path)
    args = parser.parse_args()
    credential = token()

    def api(path, data=None, method=None):
        headers = {'Authorization': 'Bearer ' + credential,
                   'Accept': 'application/vnd.github+json', 'User-Agent': 'Avatools-release',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(API + path, headers=headers,
                    data=json.dumps(data).encode() if data is not None else None, method=method)
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    if args.command == 'status':
        repo = api('')
        releases = api('/releases?per_page=5')
        print(json.dumps(dict(default_branch=repo['default_branch'], private=repo['private'],
                              can_push=repo.get('permissions', {}).get('push'),
                              releases=[dict(tag=x['tag_name'], draft=x['draft'], url=x['html_url']) for x in releases]), indent=2))
    elif args.command == 'runs':
        suffix = ('&head_sha=' + args.sha) if args.sha else ''
        runs = api('/actions/runs?per_page=5' + suffix)['workflow_runs']
        print(json.dumps([dict(id=x['id'], sha=x['head_sha'], status=x['status'],
                               conclusion=x['conclusion'], url=x['html_url']) for x in runs], indent=2))
        for run in runs[:1]:
            if run['conclusion'] == 'failure':
                jobs = api('/actions/runs/' + str(run['id']) + '/jobs')['jobs']
                print(json.dumps([dict(name=j['name'], conclusion=j['conclusion'],
                                       failed_steps=[s['name'] for s in j['steps'] if s.get('conclusion') == 'failure']) for j in jobs], indent=2))
    else:
        release = api('/releases/tags/' + args.tag)
        assets = release['assets']
        if args.command == 'publish':
            if not args.notes:
                raise RuntimeError('--notes is required before publishing.')
            names = {asset['name'] for asset in assets}
            if not {'Avatools-3x-windows-x64.zip', 'SHA256SUMS.txt'}.issubset(names):
                raise RuntimeError('Draft is missing required portable assets.')
            # A release must point to the reviewed commit, not an unexpected tag.
            ref = api('/git/ref/tags/' + args.tag)['object']
            if ref['type'] == 'tag':
                ref = api('/git/tags/' + ref['sha'])['object']
            if not args.sha or ref['sha'] != args.sha:
                raise RuntimeError('Tag commit does not match --sha.')
            release = api('/releases/' + str(release['id']),
                          dict(name='Avatools 3x v2.0.0', body=args.notes.read_text(encoding='utf-8-sig'),
                               draft=False, prerelease=False, make_latest='true'), 'PATCH')
        print(json.dumps(dict(tag=release['tag_name'], draft=release['draft'], url=release['html_url'],
                              assets=[dict(name=a['name'], bytes=a['size'], url=a['browser_download_url']) for a in release['assets']]), indent=2))


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as exc:
        # Do not emit request headers or credential subprocess output.
        print('GitHub API failed: HTTP ' + str(exc.code), file=sys.stderr)
        sys.exit(1)
