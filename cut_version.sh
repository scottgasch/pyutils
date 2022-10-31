#!/usr/bin/env bash

set -e

# Ask a yes or no question
function ask_y_n() {
    local prompt default reply
    if [ "${2:-}" = "Y" ]; then
        prompt="Y/n"
        default=Y
    elif [ "${2:-}" = "N" ]; then
        prompt="y/N"
        default=N
    else
        prompt="y/n"
        default=
    fi
    while true; do
        echo -ne "$1 [$prompt] "
        read -n 1 -t 5 reply </dev/tty
        if [ -z "$reply" ]; then
            echo
            echo "(timeout, assuming $default)"
            reply=$default
        fi
        case "$reply" in
            [Yy]* ) echo && return 0 ;;
            [Nn]* ) echo && return 1 ;;
            * ) echo && echo "Please answer Yes or No." ;;
        esac
    done
}

function pause() {
    read -rsp $'Press any key to continue...' -n1 key
}


if [ $# -ne 1 ]; then
    echo "Usage: $0 <required_version_number>"
    exit 1
fi

VERSION=$1
PREVIOUS_VERSION=$(git tag --sort=-creatordate | head -1)
git tag --format='%(creatordate:short)%09%(refname:strip=2)'
echo
echo "PREVIOUS_VERSION=${PREVIOUS_VERSION}"
echo
if ! ask_y_n "About to cut (build, test, package, give you the command to upload) $VERSION, ok?" "N"; then
    echo "Ok, exiting instead."
    exit 0
fi
LAST_TAG=$(git tag | tail -1)
if [ "${LAST_TAG}" == "${VERSION}" ]; then
    echo "Last tag is the same as ${VERSION}?!  Aborted."
    exit 1
fi
echo

echo "Ok, here are the commit message of changes since the last version..."
git log $LAST_TAG..HEAD
pause
echo
echo

echo "Ok, running pyutils and scottutilz tests including test_some_dependencies.py..."
cd ../scottutilz/tests
./run_tests.py --all --coverage
cd ../../pyutils
pause
echo
echo

echo "Creating a git tag for version ${VERSION}"
git tag -a "${VERSION}" -m "cut_version.sh ${VERSION}"
CHANGES=$(git log --pretty="- %s" $VERSION...$LAST_TAG)
printf "# 🎁 Release notes (\`$VERSION\`)\n\n## Changes\n$CHANGES\n\n## Metadata\n\`\`\`\nThis version -------- $VERSION\nPrevious version ---- $PREVIOUS_VERSION\nTotal commits ------- $(echo "$CHANGES" | wc -l)\n\`\`\`\n" >> release_notes.md

echo "Updating pyproject.toml with this version number"
cat ./pyproject.template | sed s/##VERSION##/$VERSION/g > ./pyproject.toml

echo "Building wheel..."
python -m build

echo "Checking in wheel package under dist/"
WHEEL=dist/pyutils-latest-py3-none-any.whl
if [ ! -f ${WHEEL} ]; then
    echo "Can't find ${WHEEL}?!"
    exit 1
fi
LINK=dist/pyutils-latest-py3-none-any.whl
git rm ${LINK}
ln -s ${WHEEL} dist/pyutils-latest-py3-none-any.whl
git add ${WHEEL}
git add ${LINK}
git commit -a -m "Cut version ${VERSION}" -m "${CHANGES}"

echo "Pushing changes to git"
git push

echo "Done.  To upload, run: \"twine upload --verbose --repository pypi dist/*\""
