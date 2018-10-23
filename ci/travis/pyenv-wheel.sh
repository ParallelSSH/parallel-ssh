#!/bin/bash -xe

brew install pyenv || brew outdated pyenv || brew upgrade pyenv

export PYENV_VERSION=${PYENV:-3.6.4}
if [[ ! -d "$HOME/.pyenv/versions/$PYENV_VERSION" ]]; then
    pyenv install $PYENV_VERSION
fi
pyenv global $PYENV_VERSION
pyenv versions

set +x
eval "$(pyenv init -)"
set -x

which python
python -m pip install -U virtualenv
python -m virtualenv -p "$(which python)" venv

set +x
source venv/bin/activate
set -x

python -V
python -m pip install -U setuptools pip
pip install -U delocate wheel
pip install -r requirements.txt
pip wheel --no-deps .
delocate-listdeps --all *.whl
delocate-wheel -v *.whl
delocate-listdeps --all *.whl

ls -l *.whl
pip install -v *.whl
pwd; mkdir -p temp; cd temp; pwd
python -c "import pssh.clients" && echo "Import successfull"
cd ..; pwd
set +x
deactivate
set -x

mv -f *.whl wheels/
ls -lh wheels/
