import os
from datetime import datetime
import subprocess
import json
import sys

def get_describe_tag():
    return subprocess.check_output(['git', 'describe', '--tags']).strip().decode('utf-8')

def make_version_file(basedir):
    rev = os.environ.get('APPVEYOR_REPO_COMMIT',
                         subprocess.check_output(['git', 'rev-list', '--max-count=1', 'HEAD']).strip().decode('utf-8'))
    basedir = os.path.abspath(basedir)
    git_desc = get_describe_tag()
    version_json = {'date': datetime.now().isoformat(),
                    'dirty': False,
                    'error': None,
                    'full-revisionid': rev,
                    'version': git_desc}
    data = """
import json

version_json = '''
%s'''  # END VERSION_JSON


def get_versions():
    return json.loads(version_json)

""" % (json.dumps(version_json))
    with open(os.path.join(basedir, 'pssh', '_version.py'), 'w') as fh:
        fh.write(data)


if __name__ == "__main__":
    if not len(sys.argv) > 1:
        sys.stderr.write("Need basedir of repo" + os.linesep)
        sys.exit(1)
    make_version_file(sys.argv[1])
