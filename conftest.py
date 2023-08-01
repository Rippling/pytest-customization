def pytest_addoption(parser):
    parser.addoption("--skiplist", default="", help="location of input file containing the list of tests to skip")
    parser.addoption(
        "--passlist",
        default="",
        help="location of output file containing the list of passed tests",
    )

def flush_lists(session: Session) -> None:
    flush_list(session, "pass", session.passlist_set)


def flush_list(session: Session, list_name: str, test_set: set[str]) -> None:
    output_file = session.config.getoption(f"--{list_name}list", "")
    if output_file == "":
        return

    with open(output_file, "a+") as f:
        for nodeid in test_set:
            f.write(f"{nodeid}\n")
    test_set.clear()


# Called to create a TestReport for each of the setup, call and teardown runtest phases of a test item.
# We use it to generate the files containing the list of passed tests.
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: CallInfo) -> None:
    report = (yield).get_result()

    has_list_output = item.session.config.getoption("--passlist", "") != ""
    if not has_list_output:
        return None

    # this code is similar to pytest main code to determine the test outcome
    excinfo = call.excinfo
    if report.outcome == "failed":
        outcome = "failed"
    elif not excinfo:
        outcome = "passed"
    elif excinfo.errisinstance(pytest.skip.Exception) or excinfo.typename == "Skipped":
        outcome = "skipped"
    else:
        outcome = "failed"

    if call.when == "call" and outcome == "passed" :
        time_since_last_flush = real_time() - item.session.last_flush_time
        item.session.passlist_set.add(item.nodeid)
        if time_since_last_flush > 90:
            flush_lists(item.session)
            item.session.last_flush_time = real_time()


# Called after the Session object has been created and before performing collection and entering the run test loop
def pytest_sessionstart(session: Session) -> None:
    session.passlist_set = set()
    session.last_flush_time = real_time()


# Called after whole test run finished, right before returning the exit status to the system.
def pytest_sessionfinish(session: Session, exitstatus: Union[int, ExitCode]):
    flush_lists(session)


# Called after collection has been performed. May filter or re-order the items in-place.
# we use it to dynamically skip the tests defined in the skiplist file if set.
def pytest_collection_modifyitems(session: Session, config: Config, items: list[Item]) -> None:
    skiplist_file = config.getoption("--skiplist", "")
    if skiplist_file == "":
        return
    if not os.path.exists(skiplist_file):
        raise Exception(f"Skiplist file {skiplist_file} not found")
    with open(skiplist_file, "r") as f:
        skiplist_string = f.read()
    skiplist_set = set()
    for line in skiplist_string.split("\n"):
        skiplist_set.add(line)
    skip_already_seen = pytest.mark.skip(reason="Already passed in previous run")
    for item in items:
        if item.nodeid in skiplist_set:
            item.add_marker(skip_already_seen)
