import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size': 16})
fin = open("timing_results_to_graph.txt")
tests = []
for line in fin:
    test_results = line.split()
    tests.append((test_results[0], float(test_results[1]), float(test_results[2])))

# test_names = [test[0] for test in tests]
test_names = list(range(len(tests)))
overheads =  []

for test in tests:
    if test[2] != 0:
        o = abs(test[1] - test[2]) / test[1]
    else:
        o = 0
    overheads.append(o)

n_groups = len(test_names)

# create plot
fig, ax = plt.subplots()
index = np.arange(n_groups)
bar_width = 0.50
opacity = 0.8

y = 34 * [1]
plt.plot(range(-1, len(tests) + 1), y, ':r')
rects1 = plt.bar(index, overheads, bar_width, alpha=opacity)

plt.xlabel('Test')
plt.ylabel('Performance Overhead (X)')
plt.title('Performance Overhead Baseline vs. RR')
plt.xticks(index, test_names)

plt.tight_layout()
plt.show()
