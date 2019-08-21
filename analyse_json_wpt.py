'''
Given the json output for running
./mach test-wpt --headless --release --log-wptreport ../experiments/baseline_all/results0 (cat ../experiments/intermittent_failures.txt)

Get the fields and data we're interested in.
'''

import json
import os
import sys

class Test:
    status = ""
    duration = -1
    name = ""
    subtests = []
    result = ""

    def __init__(self, status, duration, name, subtests, result):
        self.status = status
        self.duration = duration
        self.name = name
        self.subtests = subtests
        self.result = result
class Result:
    test_name = ""
    duration = -1
    test_name = ""

    def __init__(self, status, duration, test_name):
        self.status = status
        self.duration = duration
        self.test_name = test_name


if len(sys.argv) != 2:
    print("Usage python3 analyse_json_wpt.py path_to_result_dir/")
    sys.exit(1)
baseline_dir = sys.argv[1]
all_results = {}

# Read all the files and aggregate all the tests into all_results.
# Which is a list of all tests indexed by the test name.

for filename in os.listdir(baseline_dir):
# for filename in ["results1.json", "results2.json"]:
    json_file = baseline_dir + "/" + filename
    print("Reading in file", json_file)
    contents = json.load(open(json_file))
    test_results = contents["results"]

    for result in test_results:
        # Append entry to vector for all entries of this specific test.
        test = Test(result["status"], result["duration"], result["test"], result["subtests"], result)

        if test.name not in all_results:
            all_results[test.name] = [test]
        else:
            all_results[test.name].append(test)

print("NAME, EXPECTED, UNEXPECTED, CRASH, TIMEOUT, SKIP, ERROR")

# Iterate over test names where `tests` is a list of test trials.
for (name, tests) in all_results.items():
    expected = 0
    unexpected = 0
    crash = 0
    timeout = 0
    skip = 0
    error = 0

    # Iterate over individual test trials for a given test.
    for test in tests:
        if test.status == "PASS":
            if test.subtests != []:
                print("Exected PASS not to have subtest. This assumption is false")
                sys.exit(1)

            # This may look funny but it is correct. We only see "expected" as a
            # field if we got the wrong status, that is, we saw an unexpected result.
            if "expected" in test.result:
                unexpected += 1
            else:
                expected += 1


        elif test.status == "FAIL":
            # This may look funny but it is correct. We only see "expected" as a
            # field if we got the wrong status, that is, we saw an unexpected result.
            if "expected" in test.result:
                unexpected += 1
            else:
                expected += 1

            if test.subtests != []:
                print("Exected FAIL not to have subtest. This assumption is false")
                sys.exit(1)

        elif test.status == "CRASH":
            if test.subtests != []:
                print("Exected CRASH not to have subtest. This assumption is false")
                sys.exit(1)
            crash += 1

        # OK always has subset tests. That why it reports OK instead of PASS or FAIL
        elif test.status == "OK":
            # Ok means we have subtests use their statuses for aggregation.
            if test.subtests == []:
                print("Exected OK to have subtest. This assumption is false")
                sys.exit(1)

            # all_pass = True
            unexpected_seen = False
            for subtest in test.subtests:
                # This may look funny but it is correct. We only see "expected" as a
                # field if we got the wrong status, that is, we saw an unexpected result.
                if "expected" in subtest:
                    unexpected_seen = True
                    break

            if unexpected_seen:
                unexpected += 1
            else:
                expected += 1
                #     if subtest["status"] == "PASS":
            #         continue
            #     elif subtest["status"] == "FAIL":
            #         all_pass = False
            #         break
            #     elif subtest["status"] == "ERROR":
            #         all_pass = False
            #         break
            #     else:
            #         print("OK: Unexpected subtest result: ", subtest["status"])
            #         sys.exit(1)

            # if all_pass:
            #     pass_total_runtime += float(test.duration)
            #     passes += 1
            # else:
            #     fails += 1

            # This counts individual pass or fails. Instead we count the whole test
            # as pass/fail
            # for subtest in test.subtests:
            #     if subtest["status"] == "PASS":
            #         passes += 1
            #     elif subtest["status"] == "FAIL":
            #         fails += 1
            #     else:
            #         print("OK: Unexpected subtest result: ", subtest["status"])
            #         sys.exit(1)

        # Timeout may, or may not have subtests.
        elif test.status == "TIMEOUT":
            timeout += 1
            # This counts individual subtests. Let's just count the big number.
            # for subtest in test.subtests:
            #     if subtest["status"] == "PASS":
            #         passes += 1
            #     elif subtest["status"] == "FAIL":
            #         fails += 1
            #     elif subtest["status"] == "TIMEOUT":
            #         timeout += 1
            #     else:
            #         print("TIMEOUT: Unexpected subtest result: ", subtest["status"])
            #         sys.exit(1)

            # # No subtests, count this as one failure.
            # if timeout == 0:
            #     timeout = 1

        # Count the whole test as an error. Don't know what else to do.
        elif test.status == "ERROR":
            # Error may have subtests, but we ignore those.
            error += 1

        elif test.status == "SKIP":
            if test.subtests != []:
                print("Exected SKIP not to have subtest. This assumption is false")
                sys.exit(1)
            skip += 1
        else:
            print("Unkown top level status", test.result)
            sys.exit(1)

    # Done interating over this test. Print its results.
    # if passes != 0:
    #     succ_average_runtime = pass_total_runtime / passes
    # else:
    #     succ_average_runtime = 0

    print("{}, {}, {}, {}, {}, {}, {}".format(name, expected, unexpected, crash, timeout, skip, error))
