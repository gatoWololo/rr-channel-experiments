use anyhow::{bail, Context, Result};
use glob::glob;
use rayon::prelude::*;
use serde::Deserialize;
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use structopt::StructOpt;

type TestStatusCounts = HashMap<TestStatus, u32>;

/// We have one command to execute and global flags that apply to all commands. Each command may
/// further have its own parameters and flags.
#[derive(Debug, StructOpt)]
#[structopt(about = "Parsing Script for Servo WPT JSON Logs.")]
struct CmdLineOptions {
    #[structopt(subcommand)]
    command: SubCommands,
    /// Directory containing all files to read in.
    #[structopt(parse(from_os_str))]
    input_dir: PathBuf,
    /// Output file.
    #[structopt(parse(from_os_str))]
    output: PathBuf,
    /// Glob pattern for files to process.
    #[structopt(default_value = "*.json")]
    file_pattern: String,
}

#[derive(StructOpt, Debug)]
enum SubCommands {
    /// Count how many tests returned an unexpected status. This is basically the number of tests
    /// that failed. Does not do anything special with intermittent tests.
    CountUnexpectedTestsStatus,
    /// Return the lists of
    GetIntermittents,
    /// Print all tests with the given specified TestStatus.
    GetLogOutput {
        #[structopt(parse(try_from_str = status_from_str))]
        status: TestStatus,
    },
}

fn status_from_str(status: &str) -> Result<TestStatus> {
    use TestStatus::*;
    let map = vec![
        ("Pass", Pass),
        ("Fail", Fail),
        ("Skip", Skip),
        ("Error", Error),
        ("Ok", Ok),
        ("Timeout", Timeout),
        ("Crash", Crash),
    ];
    let map: HashMap<&str, TestStatus> = map.into_iter().collect();

    map.get(status).map(|s| s.clone()).context(format!(
        "Invalid Status. Possible status are: {:?}",
        map.keys().collect::<Vec<_>>()
    ))
}

#[derive(Deserialize, Debug, Eq, PartialEq, Hash, Copy, Clone)]
#[serde(rename_all = "UPPERCASE", deny_unknown_fields)]
enum TestStatus {
    Pass,
    Fail,
    Skip,
    Error,
    Ok,
    Timeout,
    Crash,
    /// Only seen in subtests.
    NotRun,
    /// Only seen in subtests.
    #[serde(rename = "PRECONDITION_FAILED")]
    PreconditionFailed,
}

/// Overall structure of Serde log-wptreport output. We're really interested in the `results` field.
/// Which we handle and parse separately.
#[derive(Deserialize, Debug, Clone)]
#[serde(deny_unknown_fields)]
struct WptLog {
    run_info: Value,
    time_start: usize,
    time_end: usize,
    results: Vec<Test>,
}

/// We leave `Value` (i.e. untyped data) for fields we don't yet handle or don't know what they
/// look like.
#[derive(Deserialize, Debug, Clone)]
#[serde(deny_unknown_fields)]
struct Test {
    status: TestStatus,
    // TODO
    known_intermittent: Option<Vec<Value>>,
    #[serde(rename = "test")]
    test_name: String,
    // TODO
    subtests: Vec<SubTest>,
    // TODO Is this measured in milliseconds?
    duration: usize,
    // TODO
    message: Value,
    // TODO Skip?
    screenshots: Option<Value>,
    expected: Option<TestStatus>,
}

#[derive(Deserialize, Debug, Clone)]
#[serde(deny_unknown_fields)]
struct SubTest {
    // TODO
    known_intermittent: Vec<Value>,
    #[serde(rename = "name")]
    test_name: String,
    // TODO
    message: Value,
    status: TestStatus,
    expected: Option<TestStatus>,
}

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();
    let opt = CmdLineOptions::from_args();

    println!("Reading input files...");
    let wpt_logs = read_json_file(opt.input_dir, &opt.file_pattern)?;
    println!("Read {:} files.", wpt_logs.len());
    check_test_numbers(&wpt_logs)?;

    match opt.command {
        SubCommands::CountUnexpectedTestsStatus => {
            let counts = count_unexpected_test_statuses(wpt_logs)?;
            println!("Unexpected Tests Status");
            for (status, count) in counts {
                println!("{:?}: {:?}", status, count);
            }
        }
        SubCommands::GetIntermittents => {
            let hm: HashMap<String, TestStatusCounts> = get_intermittents(wpt_logs)?;
            for (name, tests_status) in &hm {
                println!("Test: {}", name);
                println!("{:?}\n", tests_status);
            }
            println!("Total Intermittent Tests: {}", hm.len());
        }
        SubCommands::GetLogOutput { status } => {
            let tests_with_status = get_log_output(wpt_logs, status)?;
            let n = tests_with_status.len();

            let mut f = BufWriter::new(File::create(opt.output)?);
            for t in tests_with_status {
                writeln!(f, "{}", t)?;
            }

            println!("{} tests found with status {:?}", n, status);
        }
    }

    Ok(())
}

/// Return tests which always have status TestStatus. Accounts for intermittent tests as if a test
/// is seen multiple times, it must return the same status on all executions.
fn get_log_output(wpt_logs: Vec<WptLog>, status: TestStatus) -> Result<HashSet<String>> {
    let wpt_tests: HashSet<String> = wpt_logs
        .clone()
        .into_iter()
        .flat_map(|wpt_log| wpt_log.results)
        .filter_map(|t| {
            if t.expected.is_none() && t.status == status {
                return Some(t.test_name);
            }
            None
        })
        .collect();

    let intermittents: HashSet<String> = get_intermittents(wpt_logs)
        .with_context(|| "Unable to get intermittents.")?
        .into_iter()
        .map(|t| t.0)
        .collect();

    let tests = wpt_tests
        .difference(&intermittents)
        .map(|t| t.to_owned())
        .collect();
    Ok(tests)
}

/// Ensure all test-runs have the same number of tests.
/// TODO: We checked and they do, probably not worth checking every time?
fn check_test_numbers(wpt_logs: &Vec<WptLog>) -> Result<()> {
    let mut tests_per_run: Option<usize> = None;

    for log in wpt_logs {
        let this_tests_runs = log.results.len();
        // Init.
        match tests_per_run {
            None => {
                tests_per_run = Some(this_tests_runs);
            }
            Some(n) => {
                if this_tests_runs != n {
                    bail!(
                        "Different amount of tests found. Expected {}, found {}",
                        n,
                        this_tests_runs
                    );
                }
            }
        }
    }
    Ok(())
}

fn get_intermittents(wpt_logs: Vec<WptLog>) -> Result<HashMap<String, TestStatusCounts>> {
    let hm: HashMap<String, TestStatusCounts> = status_per_tests(wpt_logs);
    // I tried doing a map filter over the original hashmap and it was even uglier... So.
    let mut only_intermittents = HashMap::new();

    for (test_name, status_counts) in hm {
        match status_counts.len() {
            0 => bail!(
                "We should never see a test with no test status entries?! Test: {:?}",
                test_name
            ),
            // Only a single status was found across all executions of this test. Not an
            // intermittent.
            1 => {}
            _ => {
                only_intermittents.insert(test_name, status_counts);
            }
        }
    }

    Ok(only_intermittents)
}

/// Tests status only makes sense when comparing their actual test status vs their unexpected test
/// status. For example an actual test status of "Crash" could actual be Ok if we expected a Crash
/// for a test.
fn count_unexpected_test_statuses(wpt_logs: Vec<WptLog>) -> Result<HashMap<TestStatus, u32>> {
    let hm: HashMap<String, TestStatusCounts> = unexpected_status_per_tests(wpt_logs);

    // For non-intermittent tests, counts how many total of each status we had.
    let mut test_results: HashMap<TestStatus, u32> = HashMap::new();

    for (test_name, test_status_counts) in &hm {
        match test_status_counts.len() {
            0 => {
                bail!(
                    "We should never see a test with no test status entries?! Test: {:?}",
                    test_name
                );
            }
            _ => {
                for (status, count) in test_status_counts {
                    let counter = test_results.entry(*status).or_insert(0);
                    *counter += count;
                }
            }
        }
    }

    Ok(test_results)
}

/// Given a list of wpt_logs, representing possibly many Servo executions. Return a hashmap of
/// test names to all the unexpected statuses seen for that test.
/// Returns only the unexpected status. The expected test status doesn't really matter?
fn unexpected_status_per_tests(wpt_logs: Vec<WptLog>) -> HashMap<String, TestStatusCounts> {
    let mut hm: HashMap<String, TestStatusCounts> = HashMap::new();
    for log in wpt_logs {
        for test in &log.results {
            if let Some(_expected_status) = test.expected {
                let test_status_counter =
                    hm.entry(test.test_name.clone()).or_insert(HashMap::new());
                let counter: &mut u32 = test_status_counter.entry(test.status).or_insert(0);
                *counter += 1;
            }
        }
    }
    hm
}

fn status_per_tests(wpt_logs: Vec<WptLog>) -> HashMap<String, TestStatusCounts> {
    let mut hm: HashMap<String, TestStatusCounts> = HashMap::new();
    for log in wpt_logs {
        for test in &log.results {
            let test_status_counter = hm.entry(test.test_name.clone()).or_insert(HashMap::new());
            let counter: &mut u32 = test_status_counter.entry(test.status).or_insert(0);
            *counter += 1;
        }
    }
    hm
}

fn write_intermittent_tests(
    hm: &HashMap<String, HashMap<TestStatus, u32>>,
    write_file: &Path,
) -> Result<()> {
    let mut fd = std::fs::File::create(write_file)?;

    for (test, test_status) in hm {
        if test_status.len() > 1 {
            writeln!(fd, "Test: {}, {:#?}", test, test_status)?;
        }
    }

    Ok(())
}

fn read_json_file(input_dir: PathBuf, file_pattern: &str) -> Result<Vec<WptLog>> {
    let pattern: String = input_dir.to_string_lossy().into_owned() + "/" + file_pattern;
    let files: Vec<PathBuf> = glob(&pattern)
        .with_context(|| "Failed to glob()")?
        // Turns a Vec<Result<_, _>> into a Result<Vec<_>, _>
        .collect::<Result<Vec<PathBuf>, _>>()?;

    let logs: Vec<WptLog> = files
        .par_chunks(5)
        .map::<_, Vec<WptLog>>(|files| {
            let mut v: Vec<WptLog> = Vec::with_capacity(5);

            for file in files {
                println!("Reading {:?}", file);
                let input = std::fs::read_to_string(&file).unwrap();
                let wpt_log: WptLog = serde_json::from_str(&input).unwrap();
                v.push(wpt_log);
            }

            v
        })
        .flatten()
        .collect::<Vec<WptLog>>();

    Ok(logs)
}
