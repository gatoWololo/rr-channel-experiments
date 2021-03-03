import sys
from typing import List, Any


def main():
    if len(sys.argv) < 2:
        print("usage: python3 scrape_logs.pyt input_file.log")
        return

    f = open(sys.argv[1])

    all_errors: List[str] = []
    # Keeps track if we're currently reading an error message from log.
    on_error = False
    # List of lines (strings) representing the current error.
    current_error = []
    for line in f:
        if on_error:
            # In the middle of error...
            if line.startswith("  │ "):
                current_error.append(line)
            # This is the end! We read the error all the way.
            elif line.startswith("  └ "):
                current_error.append(line)
                on_error = False
                error_msg = "".join(current_error)
                # Clear out list for next error.
                all_errors.append(error_msg)
                current_error.clear()
        else:
            # We found the beginning of the error save it!
            if line.startswith("  ▶ CRASH"):
                if current_error:
                    print("Error, current_error list not empty!")
                on_error = True
                current_error.append(line)

    for e in all_errors:
        print(e)
        print("")


if __name__ == "__main__":
    main()
