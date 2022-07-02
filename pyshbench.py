#!/usr/bin/python3
import subprocess
import re
import statistics
import math
import sys
import platform
import os.path
import psutil
import copy
from datetime import datetime


def erf_inv(x):
    """Inverse of math.erf()"""
    a = 8 * (math.pi - 3) / (3 * math.pi * (4 - math.pi))
    y = math.log(1 - x * x)
    z = 2 / (math.pi * a) + y / 2
    return math.copysign(math.sqrt(math.sqrt(z * z - y / a) - z), x)


def CDF(q):
    """CDF of the standard Gaussian law"""
    return 0.5 * (1 + math.erf(q / math.sqrt(2)))


def Quantile(p):
    """Quantile function of the standard Gaussian law"""
    assert 0 <= p and p <= 1
    return math.sqrt(2) * erf_inv(2 * p - 1)


def rightstr(s, l):
    if len(s) > l:
        return "..." + s[3 - l :]
    else:
        return s


def print_results(
    baseP, testP, diffP, argvP, runs, argv_index, done_trial, file_id=None
):
    base = copy.deepcopy(baseP)
    test = copy.deepcopy(testP)
    diff = copy.deepcopy(diffP)
    argv = copy.deepcopy(argvP)

    base_mean = statistics.mean(base)
    test_mean = statistics.mean(test)
    diff_mean = statistics.mean(diff)

    base_sdev = statistics.stdev(base, base_mean) / math.sqrt(runs)
    test_sdev = statistics.stdev(test, test_mean) / math.sqrt(runs)
    diff_sdev = statistics.stdev(diff, diff_mean) / math.sqrt(runs)

    output = (
        "\nResult of {:3n} runs\n------------------".format(runs)
        + "\n"
        + "base ({:<15s}) = {:>10n}  +/- {:n}".format(
            rightstr(argv[argv_index], 15),
            round(base_mean),
            round(Quantile(0.975) * base_sdev),
        )
        + "\n"
        + "test ({:<15s}) = {:>10n}  +/- {:n}".format(
            rightstr(argv[argv_index + 1], 15),
            round(test_mean),
            round(Quantile(0.975) * test_sdev),
        )
        + "\n"
        + "{:22s} = {:>+10n}  +/- {:n}".format(
            "diff", round(diff_mean), round(Quantile(0.975) * diff_sdev)
        )
        + "\n"
        + "\nspeedup        = {:>+6.4f}".format(diff_mean / base_mean)
        + "\n"
        + "P(speedup > 0) = {:>7.4f}".format(CDF(diff_mean / diff_sdev))
        + "\n\n"
    )

    print(output)
    if done_trial:
        with open(("results " + file_id + ".txt"), "a") as the_file:
            the_file.write(output)


if int(sys.argv[3]) < 2 or len(sys.argv) % 4 != 1:
    exit("Bad input")

for argv_index in range(1, len(sys.argv), 4):
    base, test, diff = [], [], []
    runs = int(sys.argv[argv_index + 2])
    exp = re.compile(b"Nodes/second\s*: (\d+)")
    file_id = datetime.today().strftime("%Y-%m-%d")

    # determine CPU sets to run on
    # this assumes that logical cpus on the same core are numbered sequentially
    num_cores = psutil.cpu_count(logical=False)
    num_cpus = psutil.cpu_count()
    cpu_step = int(num_cpus / num_cores)
    cpuset = []
    cpuset.append(list())
    cpuset.append(list())
    for i in range(0, cpu_step):
        cpuset[0].extend(list(range(i, num_cpus, cpu_step * 2)))
        cpuset[1].extend(list(range(i + cpu_step, num_cpus, cpu_step * 2)))
    print("{:>3} {:>10} {:>10} {:>8}".format("run", "base", "test", "diff"))

    for i in range(runs):
        # Start both processes. This is non-blocking.
        
        bench_command = "bench"
        if int(sys.argv[argv_index+3]) > 1:
            bench_command += (" 16 " + sys.argv[argv_index+3] + " 13 default depth mixed")

        base_process = subprocess.Popen(
            [
                (
                    r"/mnt/c/Users/johnd/Documents/Coding Projects/pyshbench/"
                    + sys.argv[argv_index]
                ),
                bench_command,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        psutil.Process(base_process.pid).cpu_affinity(cpuset[i % 2])
        
        test_process = subprocess.Popen(
            [
                (
                    r"/mnt/c/Users/johnd/Documents/Coding Projects/pyshbench/"
                    + sys.argv[argv_index + 1]
                ),
                bench_command,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        psutil.Process(test_process.pid).cpu_affinity(cpuset[(i + 1) % 2])

        # Wait for processes to finish and grep nps results in their stderr output
        base.append(int(exp.search(base_process.stderr.read()).group(1)))
        test.append(int(exp.search(test_process.stderr.read()).group(1)))

        diff.append(test[i] - base[i])
        print("{:>3} {:>10n} {:>10n} {:>+8n}".format(i + 1, base[i], test[i], diff[i]))

        if (i + 1) % 5 == 0 and i > 1 and i < runs - 1:
            print_results(base, test, diff, sys.argv, i + 1, argv_index, False)
    # for loop

    print_results(base, test, diff, sys.argv, runs, argv_index, True, file_id=file_id)
    cpu = str()
    if os.path.exists("/proc/cpuinfo"):
        exp = re.compile("^model name\s+:\s+(.*)$")
        with open("/proc/cpuinfo", "r") as infile:
            for line in infile:
                m = exp.match(line)
                if m:
                    cpu = m.group(1)
                    break
    if cpu == "":
        cpu = platform.processor()
    if cpu == "":
        cpu = "unknown"
    print("\nCPU:", num_cores, "x", cpu)
    print("Hyperthreading:", "off" if num_cpus == num_cores else "on", "\n")
