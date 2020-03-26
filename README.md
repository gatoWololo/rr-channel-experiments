## RR Channel Experiments

## Backgroud
Please read Servo's WPT documentation: https://github.com/servo/servo/blob/master/tests/wpt/README.md

## Running a Single Test

We can use `./mach test-wpt` to run tests. Runnig a single test can look like: `./mach test-wpt --headless --release tests/wpt/web-platform-tests/dom/historical.html` where this test is located under the full path from the project's root: `./tests/wpt/web-platform-tests/dom/historical.html`.

`--headless` specifies there is no GUI. We run in `--release` as otherwise some tests fail because of too slow timeouts.

## rr-channel-experiments
Here we document how many files came to be and document scripts.

### Intemittent Tests
`interesting_intermittents.txt` lists all the tests known to have intermittent failures (generated Summer 2019). This file was generated via the `github_scrape_intermittent_failures.py`. This script uses the Github API to fetch all issues labeld "I-intermittent".

Notice not all tests on github issues still exist in the Servo Repository. These are now filtered out into `tests_that_no_longer_exist.txt`.

### Running Experiments
The main script to run experiments is `run_intermittent_failures_tests.py`. This script accepts several subcommands:
- `run_baseline <tests_file> <output_dir/>` Accepts a list of tests to run (like `interesting_intermittents.txt`) and runs all the tests `test_runs` number of times (default is currently 100). Outputs a directory `<output_dir>` containing the raw logs of tests
- `analyse_output <tests_file> <baseline_results/>`: 
                       record_tests         tests_file output_dir/
                       run_replay           tests_file output_dir/ record_dir/
                       analyse_do_not_exist tests_file results/\
