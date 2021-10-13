## Script to scrape all github issues from Servo containing "I-intermittent" in its label.
## These results created the /intermittent_failures.txt file.

## No longer used as we experimentally test which tests we can get failing instead.

In [1]: from github import Github

In [2]: g = Github("gatowololo", "mypassword...")

In [7]: repo = g.get_repo("servo/servo")

In [26]: intermittent_failures = []

In [27]: for issue in issues:
    ...:     for label in issue.labels:
    ...:         if label.name == "I-intermittent":
    ...:             intermittent_failures.append(issue)
    ...:
    ...:
    ...:
    ...:

In [28]: len(intermittent_failures)
Out[28]: 468

In [33]: for issue in intermittent_failures:
    ...:     print(issue.title)

In [39]: titles = []

In [40]: for issue in intermittent_failures:
    ...:     titles.append(issue.title)

In [46]: for t in titles:
    ...:     path = t.split()[-1]
    ...:     if path.startswith('/'):
    ...:         print(path)
