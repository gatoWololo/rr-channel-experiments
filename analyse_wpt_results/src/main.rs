use structopt::StructOpt;
use std::path::PathBuf;
use serde::{Deserialize};
use anyhow::{Result, Context};
use serde_json::Value;

#[derive(Debug, StructOpt)]
struct Opt {
    /// Json input (output of executing ./mach with flag `--log-wptreport`.
    #[structopt(parse(from_os_str))]
    input: PathBuf,
    /// Output file.
    #[structopt(parse(from_os_str))]
    output: PathBuf,
}

#[derive(Deserialize, Debug)]
#[serde(rename_all="UPPERCASE", deny_unknown_fields)]
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
    #[serde(rename="PRECONDITION_FAILED")]
    PreconditionFailed
}

/// Overall structure of Serde log-wptreport output. We're really interested in the `results` field.
/// Which we handle and parse separately.
#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
struct WptLog {
    run_info: Value,
    time_start: usize,
    time_end: usize,
    results: Vec<Test>,
}

/// We leave `Value` (i.e. untyped data) for fields we don't yet handle or don't know what they
/// look like.
#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
struct Test {
    status: TestStatus,
    // TODO
    known_intermittent: Option<Vec<Value>>,
    #[serde(rename="test")]
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

#[derive(Deserialize, Debug)]
#[serde(deny_unknown_fields)]
struct SubTest {
    // TODO
    known_intermittent: Vec<Value>,
    #[serde(rename="name")]
    test_name: String,
   // TODO
    message: Value,
    status: TestStatus,
    expected: Option<TestStatus>,
}

fn main() -> anyhow::Result<()> {
    let opt = Opt::from_args();

    let wpt_log = read_json_file(opt.input)?;

    let mut null_known_intermittent: u32 = 0;
    let mut empty_known_intermittent: u32 = 0;
    let mut contains_known_intermittent: u32 = 0;
    let mut subtest_null_known_intermittent: u32 = 0;
    let mut subtest_empty_known_intermittent: u32 = 0;
    let mut subtest_contains_known_intermittent: u32 = 0;
    let mut total_subtests: u32 = 0;
    let total_tests = wpt_log.results.len();

    for test in wpt_log.results {
        if count_known_intermittents(&mut null_known_intermittent, &mut empty_known_intermittent, &mut contains_known_intermittent, &test.known_intermittent) {
            print!("Found intermittent: {:#?}", test);
        }

        total_subtests += test.subtests.len() as u32;
        for subtest in test.subtests {

            count_known_intermittents(&mut subtest_null_known_intermittent, &mut subtest_empty_known_intermittent, &mut subtest_contains_known_intermittent, &Some(subtest.known_intermittent));
        }
    }

    dbg!(subtest_empty_known_intermittent);
    dbg!(subtest_contains_known_intermittent);
    dbg!(subtest_null_known_intermittent);

    dbg!(empty_known_intermittent);
    dbg!(contains_known_intermittent);
    dbg!(null_known_intermittent);
    dbg!(total_tests);
    dbg!(total_subtests);

    // No writing for now
    // std::fs::write(opt.output, format!("{:#?}", wpt_log))?;

    Ok(())

}

fn count_known_intermittents(null_known_intermittent: &mut u32, empty_known_intermittent: &mut u32, contains_known_intermittent: &mut u32, intermittents: &Option<Vec<Value>>, ) -> bool {
    match intermittents {
        None => {
            *null_known_intermittent += 1;
        }
        Some(ki) => {
            if ki.is_empty() {
                *empty_known_intermittent += 1;
            } else {
                *contains_known_intermittent += 1;
                return true;
            }
        }
    }
    return false;
}

fn read_json_file(path: PathBuf) -> Result<WptLog> {
    let json_input = std::fs::read_to_string(path)
        .with_context(|| "Unable to read json input file.")?;

    let wpt_log = serde_json::from_str(&json_input)
        .with_context(|| "Cannot parse JSON into typed struct.")?;
    Ok(wpt_log)
}