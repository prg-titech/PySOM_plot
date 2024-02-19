import glob
import os
import sys
import math
from statistics import geometric_mean, variance, median
from argparse import ArgumentParser

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.style as style
import matplotlib.backends.backend_pdf as backend_pdf

from scipy.stats.mstats import gmean
from pprint import pprint
from numpy.lib import type_check


class PySOMPlot:
    def __init__(self, filename):
        self.filename = filename
        if self.filename.endswith(".data"):
            self.basename = os.path.basename(self.filename.removeprefix(".data"))
        else:
            self.basename = os.path.basename(self.filename)

        self.results_teir1 = None
        self.results_interp = None
        self.resulsts_tier2 = None

        self.max_invocation = 0
        self.max_iteration = 0

        self.benchmarks = []
        self.executors = []

        self.results = {}
        self.results_with_invocations = {}

        try:
            f = open(self.filename, "r")
        except IOError:
            raise Exception("not found", filename)

        while True:
            line = f.readline().rstrip()
            if line.startswith("#"):
                continue
            if len(line) == 0:
                break

            line = line.split("\t")
            try:
                invocation, iteration, elapsed, benchmark, executor = (
                    float(line[0]),
                    float(line[1]),
                    float(line[2]),
                    line[5],
                    line[6],
                )
            except Exception:
                continue

            if executor not in self.executors:
                self.executors.append(executor)

            if benchmark not in self.benchmarks:
                self.benchmarks.append(benchmark)

            if executor not in self.results:
                self.results[executor] = {}

            if benchmark not in self.results[executor]:
                self.results[executor][benchmark] = {}

            if invocation > self.max_invocation:
                self.max_invocation = invocation

            if iteration > self.max_iteration:
                self.max_iteration = iteration

            if not self.results[executor][benchmark]:
                self.results[executor][benchmark] = [{invocation: [elapsed]}]
            else:
                is_existed = False
                for d in self.results[executor][benchmark]:
                    if invocation in d:
                        d[invocation].append(elapsed)
                        is_existed = True
                        break

                if not is_existed:
                    self.results[executor][benchmark].append({invocation: [elapsed]})

        self.benchmarks.sort()
        self.executors.sort()

    def _get_medians_baseline(self, baseline="interp"):
        key = None
        for executor in self.executors:
            if baseline in executor:
                key = executor
                break
        if not key:
            raise KeyError("not found", baseline)

        medians = {}
        for benchmark in self.benchmarks:
            series_with_invocations = self.results[key][benchmark]
            for i, series in enumerate(series_with_invocations):
                arr = np.array(series[i + 1])
                medians[benchmark] = np.median(arr)
        return medians

    def _get_relative_data_series(self, baseline="interp"):
        medians_baseline = self._get_medians_baseline()

        relative_results = {}

        for executor in self.executors:
            relative_results[executor] = {}

            for benchmark in self.benchmarks:
                relative_results[executor][benchmark] = {}

                series_with_invocations = self.results[executor][benchmark]
                for i, series in enumerate(series_with_invocations):
                    # devide by interp's median
                    arr = np.array(series[i + 1]) / medians_baseline[benchmark]
                    relative_results[executor][benchmark][i + 1] = arr

        return relative_results

    def _process_relative_data_with_invocation(self):
        results = {}
        relative_series = self._get_relative_data_series()

        for i in range(1, int(self.max_invocation) + 1):
            results[i] = {}
            for executor in self.executors:
                results[i][executor] = {}
                for benchmark in self.benchmarks:
                    results[i][executor][benchmark] = []

        for executor in self.executors:
            for benchmark in self.benchmarks:
                data_series_with_invokes = relative_series[executor][benchmark]
                for i in range(1, int(self.max_invocation) + 1):
                    data_series = data_series_with_invokes[i]
                    results[i][executor][benchmark] = data_series

        return results

    def _process_data_with_invocation(self):
        self.results_with_invocations = {}

        for i in range(1, int(self.max_invocation) + 1):
            self.results_with_invocations[i] = {}
            for executor in self.executors:
                self.results_with_invocations[i][executor] = {}
                for benchmark in self.benchmarks:
                    self.results_with_invocations[i][executor][benchmark] = []

        for executor in self.executors:
            for benchmark in self.benchmarks:
                for i, data in enumerate(self.results[executor][benchmark]):
                    data_series = data[i + 1]
                    self.results_with_invocations[i + 1][executor][
                        benchmark
                    ] = data_series

        return True

    def _statistics_per_iter(self, series_lists, length_of_element):
        gmeans = []
        vs = []
        for i in range(length_of_element):
            y = []
            for series in series_lists:
                y.append(series[i])

            gmean = median(y)  # geometric_mean(y)
            var = variance(y)
            gmeans.append(gmean)
            vs.append(var)
        return gmeans, vs

    def plot_boxes(self):
        output = self.basename.removesuffix(".data")
        data = self._process_relative_data_with_invocation()

        style.use("seaborn-v0_8-darkgrid")
        figs = []

        for invocation in range(1, int(self.max_invocation) + 1):
            for executor in self.executors:
                globals()["results_{}".format(executor.replace("-", "_"))] = data[
                    invocation
                ][executor]

            ys = []
            gmeans = []
            for i, benchmark in enumerate(self.benchmarks):
                y = results_RPySOM_bc_jit_tier1[benchmark]
                ys.append(y)
                gmean = geometric_mean(y)
                gmeans.append(gmean)

            ys = ys + [geometric_mean(gmeans)]

            fig, ax = plt.subplots(figsize=(8, 6))
            ax.boxplot(ys, labels=self.benchmarks + ["geo_mean"])
            ax.set_ylim([0.675, 1.15])
            ax.set_ylabel("norm. to interp's median")
            plt.xticks(rotation=90)
            plt.suptitle("invocation = {}".format(invocation))
            plt.tight_layout()
            figs.append(fig)

        plt.show()
        pdf = backend_pdf.PdfPages(output + "_box_per_invoke.pdf")
        for fig in figs:
            pdf.savefig(fig)
        pdf.close()

    def plot_line_per_invocation(self):
        output = self.basename.removesuffix(".data")

        self._process_data_with_invocation()

        style.use("seaborn-v0_8-darkgrid")

        figs = []

        for invocation in range(1, int(self.max_invocation) + 1):
            data = self.results_with_invocations[invocation]
            for executor in self.executors:
                globals()["results_{}".format(executor.replace("-", "_"))] = data[
                    executor
                ]

            fig = plt.figure(figsize=(12, 20), tight_layout=True)

            for i, benchmark in enumerate(self.benchmarks):
                plt.subplot(len(self.benchmarks) // 2, 2, i + 1)

                x = [i + 1 for i in range(self.max_iteration)]
                plt.plot(
                    x,
                    list(results_RPySOM_bc_jit_tier1[benchmark]),
                    "b-",
                    label="threaded code",
                )
                plt.plot(
                    x,
                    list(results_RPySOM_bc_interp[benchmark]),
                    "r-",
                    label="interpreter",
                )
                plt.title(benchmark)
                plt.ylabel("ms")

            plt.legend(["threaded code", "interpreter"])
            fig.suptitle("invocation = {}".format(invocation))

            plt.tight_layout()
            # plt.show()

            figs.append(fig)

        pdf = backend_pdf.PdfPages(output + "_per_invoke.pdf")
        for fig in figs:
            pdf.savefig(fig)
        pdf.close()

    def plot_line(self):
        d_gmean = {}
        d_var = {}

        for executor in self.executors:
            d_gmean[executor] = {}
            d_var[executor] = {}
            for benchmark in self.benchmarks:
                data_series_with_invokes = self.results[executor][benchmark]
                data = []
                for i, series in enumerate(data_series_with_invokes):
                    data.append(series[i + 1])
                (gmeans, var) = self._statistics_per_iter(data, self.max_iteration)
                d_gmean[executor][benchmark] = gmeans
                d_var[executor][benchmark] = var

        tot = len(self.benchmarks)
        cols = 4

        for executor in self.executors:
            globals()["results_gmean_{}".format(executor.replace("-", "_"))] = d_gmean[
                executor
            ]
            globals()["results_vars_{}".format(executor.replace("-", "_"))] = d_var[
                executor
            ]

        # print(results_gmean_RPySOM_bc_jit_tier1)
        # print(results_gmean_RPySOM_bc_interp)

        style.use("seaborn-v0_8-darkgrid")
        fig = plt.figure(figsize=(12, 28))

        for i, benchmark in enumerate(self.benchmarks):
            plt.subplot(len(self.benchmarks) // 2, 2, i + 1)

            x = np.array([i for i in range(100)])
            y_tier1 = np.array(results_gmean_RPySOM_bc_jit_tier1[benchmark])
            y_err_tier1 = np.array(results_vars_RPySOM_bc_jit_tier1[benchmark])
            y_interp = np.array(results_gmean_RPySOM_bc_interp[benchmark])
            y_err_interp = np.array(results_vars_RPySOM_bc_interp[benchmark])

            plt.plot(x, y_tier1, "b-", label="threaded code")
            plt.fill_between(
                x, y_tier1 - y_err_tier1, y_tier1 + y_err_tier1, color="b", alpha=0.2
            )
            plt.plot(x, y_interp, "r-", label="interp")
            plt.fill_between(
                x,
                y_interp - y_err_interp,
                y_interp + y_err_interp,
                color="r",
                alpha=0.2,
            )

            plt.xlabel("#iteration")
            plt.ylabel("ms")
            plt.title(benchmark)

        plt.legend(["threaded code", "interpreter"])
        plt.tight_layout()
        plt.show()

    def plot_line_with_invocation(self):
        output = self.basename.removesuffix(".data")
        executor_var_names = []
        for executor in self.executors:
            executor_var_name = executor.replace("-", "_")
            executor_var_names.append(executor_var_name)
            globals()["results_{}".format(executor_var_name)] = self.results[executor]

        figs = []

        style.use("seaborn-v0_8-darkgrid")
        bbox = (0, -0.15)

        label = []
        for i in range(1, int(self.max_invocation) + 1):
            label.append("invocation {}".format(i))

        result_median = {}

        for executor_var_name in executor_var_names:
            fig = plt.figure(figsize=(12, 24))
            for i, benchmark in enumerate(self.benchmarks):
                # results_tier1 = results_RPySOM_bc_jit_tier1[benchmark]
                results = globals()["results_{}".format(executor_var_name)][benchmark]
                ax = plt.subplot(len(self.benchmarks) // 2, 2, i + 1)
                plt.title(benchmark)

                for j, data_with_invokes in enumerate(results):
                    l = "invocation={}".format(j + 1)
                    plt.plot(data_with_invokes[j + 1], label=l)
                    plt.ylabel("ms")
                    plt.xlabel("#iteration")

            plt.suptitle(executor_var_name)
            plt.legend(label, bbox_to_anchor=bbox, loc="upper left", ncol=3)
            plt.tight_layout()
            figs.append(fig)

        pdf = backend_pdf.PdfPages(output + "_with_invoke.pdf")
        for fig in figs:
            pdf.savefig(fig)
        pdf.close()

        plt.show()

    def plot_invocations(self, experiment_name="Experiment4"):
        output = self.basename.removesuffix(".data")
        fig = plt.figure(figsize=(9, 6))

        style.use("seaborn-v0_8-darkgrid")
        bbox = (0, -0.15)

        for i, executor in enumerate(self.executors):
            r = self.results[executor][experiment_name]
            l = [ x[i+1][0] for i, x in enumerate(r) ]
            plt.plot(l)

        plt.legend(self.executors)
        plt.tight_layout()
        plt.savefig(output + ".pdf")
        plt.show()


class PySOMPlotExperiment:
    def __init__(self, dirname):
        self.dirname = dirname
        self.experiment_name = set()
        self.executor_names = set()
        self.max_trial = -1
        self.geomeans_vars = {}
        self.geomeans = {}
        self.variances = {}
        self.medians = {}

        filenames = glob.glob(self.dirname + "/*.data")
        for i, filename in enumerate(filenames):
            with open(filename) as f:
                while True:
                    line = f.readline()

                    if line.startswith("#"):
                        continue

                    if len(line) == 0:
                        break

                    line = line.split("\t")
                    try:
                        invocation, iteration, elapsed, benchmark, executor = (
                            float(line[0]),
                            float(line[1]),
                            float(line[2]),
                            line[5],
                            line[6],
                        )
                    except Exception:
                        continue

                    self.experiment_name.add(benchmark)
                    self.max_trial = i+1 if i+1 > self.max_trial else self.max_trial

                    exec_name = executor + "-exp"
                    self.executor_names.add(exec_name)

                    if exec_name not in globals():
                        globals()[exec_name] = {}

                    if i+1 not in globals()[exec_name]:
                        globals()[exec_name][i+1] = []

                    globals()[exec_name][i+1].append(elapsed)

        for executor in self.executor_names:
            data = globals()[executor]
            for i in range(self.max_trial):
                l = data[i+1]
                gmean = geometric_mean(l)
                var = variance(l)
                med = median(l)
                if executor not in self.geomeans_vars:
                    self.geomeans_vars[executor] = []
                    self.geomeans[executor] = []
                    self.variances[executor] = []
                    self.medians[executor] = []
                self.geomeans[executor].append(gmean)
                self.variances[executor].append(var)
                self.medians[executor].append(med)

    def plot_invocations_subplots(self):
        fig = plt.figure(figsize=(10,10), tight_layout=True)
        style.use("seaborn-v0_8-darkgrid")
        for i, executor in enumerate(self.executor_names):
            ax = fig.add_subplot(2, 2, i+1)
            data = globals()[executor]

            trials = set()
            for j in range(self.max_trial):
                l = data[j+1]
                ax.plot(l)
                ax.set_xlabel("Invocations")
                ax.set_ylabel("Elapsed time (ms)")
                ax.set_title(executor)
                ax.set_ylim((320, 750))

                trials.add(j+1)
            # ax.legend(trials, loc='best', ncol=5)

        plt.savefig(self.dirname + "/invocations.pdf")
        plt.show()

    def plot_average(self):
        fig = plt.figure(figsize=(8,8), tight_layout=True)
        style.use("seaborn-v0_8-darkgrid")
        pallets = ['b', 'g', 'r', 'c']
        for i, executor in enumerate(self.executor_names):
            # ax = fig.add_subplot(2, 2, i+1)
            x = [x for x in range(self.max_trial)]
            c = pallets[i]
            plt.plot(self.geomeans[executor], '--bo', color=c, label=executor)
            y1s = [x + y for x, y in zip(self.geomeans[executor], self.variances[executor])]
            y2s = [x - y for x, y in zip(self.geomeans[executor], self.variances[executor])]
            plt.fill_between(x, y1s, y2s, alpha=0.15, color=c)

        plt.xlabel("#Trial")
        plt.legend()
        plt.savefig(self.dirname + "/gmean_w_var.pdf")
        plt.show()

if __name__ == "__main__":
    parser = ArgumentParser(description="A plotting script for PySOM")
    parser.add_argument('--peak', action='store_true',
                        help='Plot the peak performance of threaded code')
    parser.add_argument('--exp', action='store_true',
                        help='Plot expriment of hybrid compilation')
    parser.add_argument('target',
                        help='Target dir/file that contain(s) data produced from ReBench')
    args = parser.parse_args()
    target = args.target
    if args.peak:
        assert os.path.isfile(target), "Add path to file"
        pysom_plot = PySOMPlot(target)
        pysom_plot.plot_line_with_invocation()
        pysom_plot.plot_boxes()
    elif args.exp:
        assert os.path.isdir(target), "Add path to dir"
        pysom_plot_exp = PySOMPlotExperiment(target)
        pysom_plot_exp.plot_invocations_subplots()
        pysom_plot_exp.plot_average()
