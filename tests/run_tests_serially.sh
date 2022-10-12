#!/bin/bash

# Run tests in serial.  Invoke from within tests/ directory.

ROOT=..
DOCTEST=0
UNITTEST=0
INTEGRATION=0
FAILURES=0
TESTS_RUN=0
COVERAGE=0
PERF_TESTS=("string_utils_test.py")


if [ -f color_vars.sh ]; then
    source color_vars.sh
fi


dup() {
    if [ $# -ne 2 ]; then
        echo "Usage: dup <string> <count>"
        return
    fi
    local times=$(seq 1 $2)
    for x in ${times}; do
        echo -n "$1"
    done
}

make_header() {
    if [ $# -ne 2 ]; then
        echo "Usage: make_header <required title> <color>"
        return
    fi
    local title="$1"
    local title_len=${#title}
    title_len=$((title_len + 4))
    local width=70
    local left=4
    local right=$(($width-($title_len+$left)))
    local color="$2"
    dup '-' $left
    echo -ne "[ ${color}${title}${NC} ]"
    dup '-' $right
    echo
}

function usage() {
    echo "Usage: $0 [-a]|[-i][-u][-d] [--coverage]"
    echo
    echo "Runs tests under ${ROOT}.  Options control which test types:"
    echo
    echo "    -a | --all . . . . . . . . . . . . Run all types of tests"
    echo "    -d | --doctests  . . . . . . . . . Run doctests"
    echo "    -u | --unittests . . . . . . . . . Run unittests"
    echo "    -i | --integration . . . . . . . . Run integration tests"
    echo
    exit 1
}

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -a|--all)
            DOCTEST=1
            UNITTEST=1
            INTEGRATION=1
            ;;
        -d|--doctests)
            DOCTEST=1
            ;;
        -u|--unittests)
            UNITTEST=1
            ;;
        -i|--integration)
            INTEGRATION=1
            ;;
        --coverage)
            COVERAGE=1
            ;;
        *)    # unknown option
            echo "Argument $key was not recognized."
            echo
            usage
            exit 1
            ;;
    esac
    shift
done

if [ $(expr ${DOCTEST} + ${UNITTEST} + ${INTEGRATION}) -eq 0 ]; then
    usage
    exit 2
fi

if [ ${COVERAGE} -eq 1 ]; then
    coverage erase
fi

FAILED_TESTS=""
if [ ${DOCTEST} -eq 1 ]; then
    for doctest in $(find ${ROOT} -name "*.py" -exec grep -l "import doctest" {} \;); do
        BASE=$(basename ${doctest})
        HDR="${BASE} (doctest)"
        make_header "${HDR}" "${CYAN}"
        if [ ${COVERAGE} -eq 1 ]; then
            OUT=$( coverage run --source ../src ${doctest} >./test_output/${BASE}-output.txt 2>&1 )
        else
            OUT=$( python3 ${doctest} >./test_output/${BASE}-output.txt 2>&1 )
        fi
        TESTS_RUN=$((TESTS_RUN+1))
        FAILED=$( echo "${OUT}" | grep '\*\*\*Test Failed\*\*\*' | wc -l )
        if [ $FAILED == 0 ]; then
            echo "OK"
        else
            echo -e "${FAILED}"
            FAILURES=$((FAILURES+1))
            FAILED_TESTS="${FAILED_TESTS},${BASE} (python3 ${doctest})"
        fi
    done
fi

if [ ${UNITTEST} -eq 1 ]; then
    for test in $(find ${ROOT} -name "*_test.py" -print); do
        BASE=$(basename ${test})
        HDR="${BASE} (unittest)"
        make_header "${HDR}" "${GREEN}"
        if [ ${COVERAGE} -eq 1 ]; then
            coverage run --source ../src ${test} --unittests_ignore_perf >./test_output/${BASE}-output.txt 2>&1
            if [[ " ${PERF_TESTS[*]} " =~ " ${BASE} " ]]; then
                echo "(re-running w/o coverage to record perf results)."
                ${test}
            fi
        else
            ${test} >./test_output/${BASE}-output.txt 2>&1
        fi
        if [ $? -eq 0 ]; then
            echo "OK"
        else
            FAILURES=$((FAILURES+1))
            FAILED_TESTS="${FAILED_TESTS},${BASE} (python3 ${test})"
        fi
        TESTS_RUN=$((TESTS_RUN+1))
    done
fi

if [ ${INTEGRATION} -eq 1 ]; then
    for test in $(find ${ROOT} -name "*_itest.py" -print); do
        BASE=$(basename ${test})
        HDR="${BASE} (integration test)"
        make_header "${HDR}" "${ORANGE}"
        if [ ${COVERAGE} -eq 1 ]; then
            coverage run --source ../src ${test} >./test_output/${BASE}-output.txt 2>&1
        else
            ${test} >./test_output/${BASE}-output.txt 2>&1
        fi
        if [ $? -eq 0 ]; then
            echo "OK"
        else
            FAILURES=$((FAILURES+1))
            FAILED_TESTS="${FAILED_TESTS},${BASE} (python3 ${test})"
        fi
        TESTS_RUN=$((TESTS_RUN+1))
    done
fi

if [ ${COVERAGE} -eq 1 ]; then
    make_header "Code Coverage Report" "${GREEN}"
    coverage combine .coverage*
    coverage report --omit=config-3.9.py,*_test.py,*_itest.py --sort=-cover
    echo
    echo "To recall this report w/o re-running the tests:"
    echo
    echo "  $ coverage report --omit=config-3.8.py,*_test.py,*_itest.py --sort=-cover"
    echo
    echo "...from the 'tests' directory.  Note that subsequent calls to "
    echo "run_tests.sh with --coverage will klobber previous results.  See:"
    echo
    echo "    https://coverage.readthedocs.io/en/6.2/"
    echo
fi

if [ ${FAILURES} -ne 0 ]; then
    FAILED_TESTS=$(echo ${FAILED_TESTS} | sed 's/^,/__/g')
    FAILED_TESTS=$(echo ${FAILED_TESTS} | sed 's/,/\n__/g')
    if [ ${FAILURES} -eq 1 ]; then
        echo -e "${RED}There was ${FAILURES}/${TESTS_RUN} failure:"
    else
        echo -e "${RED}There were ${FAILURES}/${TESTS_RUN} failures:"
    fi
    echo "${FAILED_TESTS}"
    echo -e "${NC}"
    exit ${FAILURES}
else
    echo -e "${BLACK}${ON_GREEN}All (${TESTS_RUN}) test(s) passed.${NC}"
    exit 0
fi
