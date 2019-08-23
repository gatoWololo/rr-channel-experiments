import subprocess
import sys
import os

usage = """\
Usage: python3 this.py run_baseline         tests_file output_dir/
                       analyse_output     tests_file baseline_results/
                       record_tests         tests_file output_dir/
                       run_replay           tests_file output_dir/ record_dir/
                       analyse_do_not_exist tests_file results/\

run_baseline: Use test_file to run baseline results. Produces `concurrent_processes`
              number of files. Where the file name is `output_dir` + the test's name.
              Where all the '/' are replaced by '_'
              The files can later be analysed via analyse_output.
              Skips any files which have already been generated in previous runs.
              Generates a timeout file in `output_dir`. On `analyse_output` these
              timedout results are treated as "rig_timeout"

analyse_output: Used to crunch number of success, failures, timeout, test does not exit,
                etc. From the output of `run_baseline` or `run_replay`. Errors if a
                specified test in `test_file` is missing. Uses timeout file to
                count some tests executions as "rig_timeout"

record_tests: Loops `test_runs` number of times trying to record a successful execution
              of the test runs. Generates the output file of the record, the record file,
              or gives up after `test_runs` times leaving behind the test output and a
              record_fail file.
"""

mach_command = "./mach test-wpt --headless --release "

# Lower this number if too many processes are being spawned!
concurrent_processes = 1
# Number of times to run each individual test.
test_runs = 100

from enum import Enum
class TestStatus(Enum):
    DOES_NOT_EXIST = 1
    FAILED = 2
    SUCCEEDED = 3
    # The servo test returned with timeout.
    TIMEDOUT = 4
    # Didn't look like a regular fail.
    UNKNOWN = 5

class Results:
    """Result for a given test"""
    name = ""
    total = 0

    does_not_exist = 0
    failed = 0
    succeeded = 0
    # The servo test returned with timeout.
    timedout = 0
    # The testing rig timed out on this test. The test didn't return timeout.
    rig_timeout = 0
    # Didn't look like a regular fail.
    unknown = 0

    def __init__(self, name):
        self.name = name

def main():
    if len(sys.argv) != 4 and len(sys.argv) != 5:
        print(usage)
        sys.exit(1)

    mode = sys.argv[1]
    test_file = sys.argv[2]
    output_dir = sys.argv[3]

    timeout_file = output_dir + "/" + "timeout_file"

    if not os.path.isdir(output_dir):
        print(output_dir + " is not a dir")
        sys.exit(1)
    print("Using output dir" + output_dir)

    print("Using file " + test_file)
    print("")
    fin = open(test_file)
    tests = []
    for line in fin:
        tests.append(line.rstrip())

    if mode == "run_baseline":
        run_baseline(output_dir, timeout_file, tests)
    elif mode == "analyse_output":
        analyse_output(output_dir, timeout_file, tests)
    elif mode == "record_tests":
        record_tests(output_dir, tests)
    elif mode == "analyse_do_not_exist":
        analyse_do_not_exist(output_dir, tests)
    elif mode == "run_replay":
        if len(sys.argv) != 5:
            print(usage)
            sys.exit(1)

        record_dir = sys.argv[4]
        run_replay(output_dir, timeout_file, record_dir, tests)
    else:
        print("Unknown mode: " + mode)
        sys.exit(1)

def run_baseline(output_dir, timeout_file, tests):
    run_tests(output_dir, timeout_file, None, tests, False)

def run_tests(output_dir, timeout_file, record_dir, tests, is_replay):
    # Append entries to timeout file
    fout_timeout = open(timeout_file, "a")

    running_procs = []

    for test in tests:
        print("Running test: " + test)
        test_path = test

        for i in range(0, test_runs):
            # Write output to file.
            write_file = output_dir + "/" + test.replace('/', '_') + str(i)

            # File already exists, skip it!
            if os.path.isfile(write_file):
                print("Output file! {} Skipping.".format(write_file))
                continue

            env = os.environ

            if is_replay:
                record_prefix = record_dir + "/" + test.replace('/', '_')
                record_fail_file = record_prefix + ".record_fail"
                record_file = record_prefix + ".record"

                if not os.path.isfile(record_file) and not os.path.isfile(record_fail_file):
                    print("Record files do not exist for {}. Skipping".format(test))
                    continue

                # Set up experiment for replay
                env["RR_CHANNEL"] = "replay"
                env["RR_RECORD_FILE"] = record_file

            fout = open(write_file, "wb")
            print("Command: " + mach_command + test)
            rp = subprocess.Popen(mach_command + test,
                                  shell=True, stdout=fout, env=env)

            print("Spawned {} tests.".format(i))
            running_procs.append((rp, test, write_file, i))

            if len(running_procs) == concurrent_processes:
                print("Switching to waiting for tests to finish...")
                wait_for_procs_finish(running_procs, fout_timeout)

    # Handle tail of tests left over.
    wait_for_procs_finish(running_procs, fout_timeout)

def wait_for_procs_finish(running_procs, fout_timeout):
    '''
    Wait for running tests to finish. Try figuring out why they failed
    based on their output and fill entries in results.
    Clears running_procs after it is done.
    '''
    for (rp, test_name, write_file, test_num) in running_procs:
        # For now just wait. Later we might wanna poll.
        # print(str(test_num) + " " + test_name + "... ", end="")
        # sys.stdout.flush()

        # give up if it takes longer than N seconds.
        try:
            returncode = rp.wait(timeout=30)
        except:
            print("Test timed out: " + test_name + str(test_num))
            if not fout_timeout is None:
                fout_timeout.write(test_name + str(test_num) + "\n")
            continue

    # Remove entries.
    running_procs.clear()

def analyse_output(output_dir, timeout_file, tests):
    if not os.path.isfile(timeout_file):
        print("File " + timeout_file + " does not exist. Have you ran run_baseline?")
        sys.exit(1)

    timeout_fin = open(timeout_file, "r")
    timeouts = set()
    for line in timeout_fin:
        timeouts.add(line.rstrip())

    # Hashmap of results so far.
    results = {}

    for test in tests:
        results[test] = Results(test)

        for i in range(0, test_runs):
            read_file = output_dir + "/" + test.replace('/', '_') + str(i)

            if not os.path.isfile(read_file):
                print("No such file: " + read_file + " skipping!")
                continue

            results[test].total += 1
            # Don't bother analysing if test timed out.
            if test + str(i) in timeouts:
                results[test].rig_timeout += 1
            else:
                status = analyse_file(test, i, read_file)

                if status == TestStatus.DOES_NOT_EXIST:
                    results[test].does_not_exist += 1
                elif status == TestStatus.FAILED:
                    results[test].failed += 1
                elif status == TestStatus.SUCCEEDED:
                    results[test].succeeded += 1
                elif status == TestStatus.TIMEDOUT:
                    results[test].timedout += 1
                elif status == TestStatus.UNKNOWN:
                    results[test].rig_timeout += 1

    # Header
    print("name, does_not_exist, failed, succeeded, timedout, unknown, rig_timeout, total")
    for r in results.values():
        print("{}, {}, {}, {}, {}, {}, {}, {}".format(r.name, r.does_not_exist, r.failed, r.succeeded, r.timedout, r.unknown, r.rig_timeout, r.total))



def analyse_file(test_name, test_num, read_file):
    contents = open(read_file, "rb").read().rstrip().split(b'\n')
    try:
        no_such_test_line = contents[1]
    except:
        print("File probably empty: ", read_file)
        sys.exit(1)
    # based on what the input looks like AFAICT
    result_line = contents[-3].strip()

    if b"ERROR Unable to find any tests at the path" in no_such_test_line:
        return TestStatus.DOES_NOT_EXIST
    elif result_line == b"OK":
        return TestStatus.SUCCEEDED
    elif result_line == b"TIMEOUT " + test_name.encode('utf-8'):
        return TestStatus.TIMEDOUT
    elif result_line.startswith(b"FAIL"):
        return TestStatus.FAILED

    # Fall back to finding slower method. Sometimes there is a lot of output
    # after the "Unexpected Results" line.
    for line in contents:
        line.startswith(b"FAIL")
        return TestStatus.FAILED

    # Assume it is unknown.
    print("Unknown status in: " + read_file)
    return TestStatus.UNKNOWN

def record_tests(output_dir, tests):

    # Break up all tests into N size chunks to run at a time.
    test_chunks = chunks(tests, concurrent_processes)

    for chunk in test_chunks:
        run_until_record_or_fail(set(chunk), output_dir)


def run_until_record_or_fail(test_batch, output_dir):
    """
    Warning! This function will spawn as many processes as tests passed in.
    Ensure you're not passing too many...

    Runs all the passed tests until they all succeed or fail 10 times.
    Creates a test_name + .record file on success, or .record_fail file on failure.
    """
    test_batch_temp = test_batch.copy()
    for test in test_batch_temp:
        write_file = output_dir + "/" + test.replace('/', '_')
        record_file = write_file + ".record"
        record_fail_file = write_file + ".record_fail"
        if os.path.isfile(record_file) or os.path.isfile(record_fail_file):
            print("Skipping ", test)
            test_batch.remove(test)

    test_batch = test_batch.copy()

    # Try to record a test N times.
    for i in range(test_runs):
        live_procs = []

        print("[{}] Trying to run {} tests".format(i, len(test_batch)))

        # Spawn a process per test.
        for test in test_batch:
            # Write output to file.
            write_file = output_dir + "/" + test.replace('/', '_')
            record_file = write_file + ".record"
            record_fail_file = write_file + ".record_fail"

            env = os.environ
            env["RR_CHANNEL"] = "record"
            env["RR_RECORD_FILE"] = record_file

            fout = open(write_file, "wb")
            test_path = test
            rp = subprocess.Popen(mach_command + test_path, shell=True, stdout=fout, env=env)
            live_procs.append((test, rp))

        # Wait for processes to finish. And if they succeeded, removed them from test_batch.
        for (test_name, rp) in live_procs:
            print("Waiting for {} to finish... ".format(test_name), end="")
            sys.stdout.flush()

            try:
                returncode = rp.wait(timeout=20)
            except:
                print("Test timed out: " + test_name + " ", end="")
                returncode = 1

            if returncode == 0:
                print("Record succeeded.")
                # careful not to remove entries while iterating over test_batch
                test_batch.remove(test_name)
                # Remove record fail file if previous iteration failed.
                remove_file(record_fail_file)

            else:
                print("Record failed.")
                # Remove record file. It is garbage.
                remove_file(record_file)
                fout = open(record_fail_file, "w")
                fout.write("failed")

        # We're all done!
        if len(test_batch) == 0:
            return

    # These entries where never successfully recorded.
    for t in test_batch:
        print("Unable to record after {} tries {}".format(test_runs, t))


def analyse_do_not_exist(output_dir, tests):
    """
    Check the output files and find all tests that do not exist.
    """
    for test in tests:
        read_file = output_dir + "/" + test.replace('/', '_') + str(0)
        if os.path.isfile(read_file):
            if analyse_file(test, 0, read_file) == TestStatus.DOES_NOT_EXIST:
                print("Does not exist: ", test)
        else:
            print("This test has never been run", test)

def run_replay(output_dir, timeout_file, record_dir, tests):
    run_tests(output_dir, timeout_file, record_dir, tests, True)

# https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

def remove_file(path):
    if os.path.isfile(path):
        os.remove(path)

main()

