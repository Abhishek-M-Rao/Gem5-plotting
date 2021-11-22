import glob
import json
import logging
import os
import pdb
from collections import defaultdict

import numpy as np
from omegaconf import DictConfig

log = logging.getLogger(__name__)


def stat_translate(
    stat, core=None
):  # the core=None just means it is an optional argument to the function
    if "core" in stat and core is None:
        raise Exception("Tried to translate core stat without core")
    core_prefix = "system.processor.cores"
    llc_prefix = "system.cache_hierarchy.l3cache"
    translator = {
        "core-ipc": f"{core_prefix}{core}.core.ipc",
        "core-insts": f"{core_prefix}{core}.core.numInsts",
        "llc-miss-rate": f"{llc_prefix}.overallMissRate::total",
        "llc-misses": f"{llc_prefix}.overallMisses::total",
        "branch-mispredicts": f"{core_prefix}{core}.core.branchMispredicts",
        "branch-number": f"{core_prefix}{core}.core.numBranches",
    }
    return translator[stat]


def gem5GetStat(stats_string, stat):
    try:
        if len(stats_string) < 10:
            return 0.0
        start = stats_string.find(stat) + len(stat) + 1
        end = stats_string.find("#", start)
        return float(stats_string[start:end])
    except Exception as e:
        print(f"Failed to find {stat}: {e}")
        return None


def get_core_stat(stats_string, stat, core, num_cores):
    core = (
        num_cores - 1
    ) * 4 + core  # gets the detailed cores (12,13,14,15) - usually (kvm, atomic, timing, detailed) from 0-15
    m5_stat_name = stat_translate(stat, core)
    return gem5GetStat(stats_string, m5_stat_name)


def get_val(stats_string, stat):
    m5_stat_name = stat_translate(stat)
    return gem5GetStat(stats_string, m5_stat_name)


def load_stats(path, cfg: DictConfig):
    # samples = 101 #set this to 1 more than the last number of samples so if last sample is "sample-72" then set this to 73
    cores = cfg.sim.cores
    stats = cfg.sim.stats
    cfg = defaultdict(list)
    samples = len(glob.glob(f"{path}/sample-*"))
    log.info(f"Processing stats for {samples} samples")
    for sample in range(samples):
        name = glob.glob(
            f"{path}/sample-{sample}-*"
        )  # glob returns a list so the [0] just gives the first entry (which should be the only one)
        if len(name) == 0:
            continue  # if sample does not exist, move on to the next one
        elif len(name) > 1:
            log.warning(f"Multiple sample dirs for sample {sample}, using first.")
        filename = os.path.join(name[0], "stats.txt")
        with open(filename) as f:
            stats_string = f.read()  # puts whole file on stats_string
            # print(f"Processing sample {sample}")
            if len(stats_string) == 0:
                print(f"Found empty stats file at sample {sample}")
            for stat in stats:
                if "core-ipc" in stat:
                    total = 0
                    for core in range(cores):  # creates a list 0,1,2,3 of cores
                        value = get_core_stat(stats_string, stat, core, cores)
                        if value is None:
                            continue
                        cfg[f"core-{core}-{stat}"].append(value)
                        total = total + value
                    cfg[f"{stat}.avg"].append(
                        total / cores
                    )  # just gets average core-ipc across cores
                elif "branch" in stat:
                    total = 0
                    for core in range(
                        cores
                    ):  # these three instructions just get number of branch-mispredicts for each detailed core
                        value_1 = get_core_stat(
                            stats_string, "branch-mispredicts", core, cores
                        )
                        value_2 = get_core_stat(
                            stats_string, "branch-number", core, cores
                        )
                        if value_1 is None or value_2 is None or value_2 == 0:
                            continue
                        value = value_1 / value_2
                        cfg[f"core-{core}-{stat}"].append(value)
                        total = total + value
                    cfg[f"{stat}.avg"].append(
                        total / cores
                    )  # this gets an average branch-mispredict-rate across cores
                elif "mpki" in stat:
                    value_o = get_val(stats_string, "llc-misses")
                    if value_o is None:
                        continue
                    total_i = 0
                    for core in range(cores):
                        each_i = get_core_stat(stats_string, "core-insts", core, cores)
                        if each_i is None:
                            continue
                        total_i = total_i + each_i
                    total_i = total_i / 1000  # to get to "per kilo instructions"
                    if total_i == 0:
                        continue
                    cfg[stat].append(
                        value_o / total_i
                    )  # appends llc-misses/total number of cycles
                else:  # this else condition handles getting llc-miss-rate which is a singular stat for each sample
                    value = get_val(stats_string, stat)
                    if value is None:
                        continue
                    cfg[stat].append(value)
    avg_cfg = dict()
    for stat, values in cfg.items():
        avg_cfg[f"samples.avg.{stat}"] = np.mean(values)
    cfg.update(avg_cfg)
    return cfg


def get_stats(path, cfg: DictConfig):
    my_dict = load_stats(path, cfg)
    with open("rollup.json", "w") as f:
        json.dump(dict(my_dict), f)
