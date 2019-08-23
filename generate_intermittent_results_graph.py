import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size': 16})
fin = open("intermittent_results_to_graph.txt")
tests = []
for line in fin:
    test_results = line.split()
    tests.append((test_results[0], float(test_results[1]), float(test_results[2])))

# test_names = [test[0] for test in tests]
test_names = list(range(len(tests)))
baseline =  [test[1] for test in tests]
rr =  [test[2] for test in tests]
n_groups = len(test_names)

# create plot
fig, ax = plt.subplots()
index = np.arange(n_groups)
bar_width = 0.35
opacity = 0.8

rects1 = plt.bar(index, baseline, bar_width, alpha=opacity, label='baseline')

rects2 = plt.bar(index + bar_width, rr, bar_width, alpha=opacity, label='rr')

plt.xlabel('Test')
plt.ylabel('Expected Result (%)')
plt.title('Comparison of "Expected" Result Baseline vs. RR')
plt.xticks(index + bar_width, test_names)
plt.legend()

plt.tight_layout()
plt.show()
