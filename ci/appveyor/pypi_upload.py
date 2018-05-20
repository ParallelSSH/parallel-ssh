import sys
import subprocess
import os


def upload_pypi(files):
    repo_tag = os.environ['APPVEYOR_REPO_TAG']
    if repo_tag == 'false':
        sys.stderr.write("Not a tagged release, skipping upload" + os.linesep)
        return
    _user, _pass = os.environ['PYPI_USER'], os.environ['PYPI_PASS']
    try:
        subprocess.check_call(['twine', 'upload', '-u', _user,
                               '-p', _pass, files])
    except Exception:
        sys.stderr.write("Error uploading to PyPi" + os.linesep)


if __name__ == "__main__":
    if not len(sys.argv) > 1:
        sys.stderr.write("Need files to upload argument" + os.linesep)
        sys.exit(1)
    upload_pypi(os.path.abspath(sys.argv[1]))
